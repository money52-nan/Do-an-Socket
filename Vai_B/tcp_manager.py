import socket
import threading
from typing import Optional, TYPE_CHECKING

from config import CONNECT_TIMEOUT, SOCKET_TIMEOUT, HANDSHAKE_TIMEOUT, MAX_MESSAGE_BYTES, EXPLICIT_CHAT_OPEN
from file_transfer import FileSender, receive_file
from protocol import ProtocolError, recv_exact, recv_hi, recv_until, read_field, read_size, send_bye, send_hi, send_msg

if TYPE_CHECKING:
    from state import PeerKey, SharedState
    from ui import ConsoleUI


def _close_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    sock.close()


def _offer_chat(state, peer_key, sock):
    rank = tuple(sorted((sock.getsockname()[:2], sock.getpeername()[:2])))
    accepted, old = state.offer_chat_conn(peer_key, sock, rank)
    if old is not None:
        _close_socket(old)
    return accepted


class TCPAcceptor(threading.Thread):
    def __init__(self, state, ui):
        super().__init__(name="TCPAcceptor", daemon=True)
        self.state = state
        self.ui = ui
        self.ready = threading.Event()
        self.error = None

    def run(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(("0.0.0.0", self.state.my_tcp_port))
                srv.listen(10)
                srv.settimeout(SOCKET_TIMEOUT)
                self.ready.set()
                while not self.state.stop_event.is_set():
                    try:
                        conn, addr = srv.accept()
                    except socket.timeout:
                        continue
                    if not self.state.track_socket(conn):
                        _close_socket(conn)
                        break
                    TCPReceiver(conn, addr[0], self.state, self.ui).start()
        except OSError as exc:
            self.error = exc
            if not self.state.stop_event.is_set():
                self.ui.safe_print(f"[!] TCP listener error: {exc}")
        finally:
            self.ready.set()


class TCPReceiver(threading.Thread):
    def __init__(self, sock, peer_ip, state, ui, is_incoming=True, known_peer_key=None, known_peer_name=""):
        super().__init__(daemon=True)
        self.sock = sock
        self.peer_ip = peer_ip
        self.state = state
        self.ui = ui
        self.is_incoming = is_incoming
        self.peer_key = known_peer_key
        self.peer_name = known_peer_name

    def run(self):
        is_chat = not self.is_incoming
        reason = None
        try:
            if self.is_incoming:
                self.sock.settimeout(HANDSHAKE_TIMEOUT)
                self.peer_name, port = recv_hi(self.sock)
                self.peer_key = (self.peer_ip, port)
                self.sock.settimeout(None)
            while not self.state.stop_event.is_set():
                cmd = recv_until(self.sock, idle_timeout=HANDSHAKE_TIMEOUT)
                if cmd is None:
                    reason = "Connection lost"
                    break
                if cmd == b"CHAT" and not is_chat and self.is_incoming:
                    if not _offer_chat(self.state, self.peer_key, self.sock):
                        break
                    is_chat = True
                elif cmd == b"MSG":
                    length = read_size(self.sock, MAX_MESSAGE_BYTES)
                    text = recv_exact(self.sock, length, idle_timeout=HANDSHAKE_TIMEOUT).decode("utf-8")
                    if not is_chat:
                        if not _offer_chat(self.state, self.peer_key, self.sock):
                            break
                        is_chat = True
                    result = self.state.record_incoming_for_socket(self.peer_key, self.sock, self.peer_name, text)
                    if result is None:
                        break
                    active, unread, backlog = result
                    if active:
                        for line in backlog:
                            self.ui.safe_print(line)
                        self.ui.safe_print(f"[{self.peer_name}] {text}")
                    else:
                        self.ui.safe_print(f"[*] New message from {self.peer_name} ({unread} unread)")
                elif cmd == b"FILE" and not is_chat:
                    filename = read_field(self.sock).decode("utf-8")
                    size = read_size(self.sock)
                    receive_file(self.sock, filename, size, self.peer_name, self.ui)
                    break
                elif cmd == b"BYE":
                    reason = "left the chat"
                    if not is_chat:
                        self.ui.safe_print(f"[*] {self.peer_name}: {reason}")
                    break
                else:
                    raise ProtocolError(f"Unexpected frame: {cmd!r}")
        except (ProtocolError, EOFError, ValueError, OSError) as exc:
            reason = f"Disconnected: {exc}"
            if not is_chat and not self.state.stop_event.is_set():
                self.ui.safe_print(f"[!] Rejected TCP connection: {exc}")
        finally:
            if is_chat and self.peer_key is not None:
                with self.state.state_lock:
                    owned = self.state.chat_conns.get(self.peer_key) is self.sock
                was_current = self.state.remove_chat_conn(self.peer_key, expected_sock=self.sock)
                if owned and not self.state.stop_event.is_set():
                    if reason:
                        self.ui.safe_print(f"[*] {self.peer_name}: {reason}")
                    if was_current:
                        self.ui.safe_print("[*] Returned to main prompt.")
            self.state.untrack_socket(self.sock)
            _close_socket(self.sock)


def handle_chat_command(target, state, ui):
    target = target.strip()
    if not target:
        ui.safe_print("[!] Usage: /chat <name|number>")
        return
    resolved = state.resolve_peer(target)
    if resolved is None:
        ui.safe_print(f"[!] Peer not found: {target}")
        return
    key, info = resolved
    name = info["name"]
    if state.get_chat_conn(key) is None:
        sock = None
        try:
            sock = socket.create_connection(key, timeout=CONNECT_TIMEOUT)
            if not state.track_socket(sock):
                _close_socket(sock)
                return
            send_hi(sock, state.my_name, state.my_tcp_port)
            sock.settimeout(None)
            if _offer_chat(state, key, sock):
                if EXPLICIT_CHAT_OPEN:
                    sock.sendall(b"CHAT|")
                TCPReceiver(sock, key[0], state, ui, False, key, name).start()
            else:
                state.untrack_socket(sock)
                _close_socket(sock)
        except (OSError, ProtocolError) as exc:
            if sock is not None:
                state.remove_chat_conn(key, expected_sock=sock)
                state.untrack_socket(sock)
                _close_socket(sock)
            if state.get_chat_conn(key) is None:
                ui.safe_print(f"[!] Cannot connect to {name}: {exc}")
                return
    unread = state.activate_chat(key)
    if unread is None:
        ui.safe_print(f"[!] Chat connection lost with {name}.")
        return
    ui.safe_print(f"[*] Connected/Switched to {name}")
    for msg in unread:
        ui.safe_print(msg)


def handle_send_text(text, state, ui):
    with state.state_lock:
        partner = state.current_partner
        sock = state.chat_conns.get(partner)
    if partner is None:
        ui.safe_print("[!] Not in a chat. Use /chat <name|number> first.")
        return
    if sock is None:
        ui.safe_print("[!] Chat connection lost.")
        return
    try:
        send_msg(sock, text)
        state.record_outgoing_message(partner, text)
    except ProtocolError as exc:
        ui.safe_print(f"[!] {exc}")
    except OSError as exc:
        state.remove_chat_conn(partner, expected_sock=sock)
        _close_socket(sock)
        ui.safe_print(f"[!] Failed to send message: {exc}")


def handle_leave_command(state, ui):
    with state.state_lock:
        partner = state.current_partner
        sock = state.chat_conns.get(partner)
    if partner is None:
        ui.safe_print("[!] You are not in a chat.")
        return
    state.remove_chat_conn(partner, expected_sock=sock)
    if sock is not None:
        try:
            send_bye(sock)
        except OSError:
            pass
        _close_socket(sock)
    ui.safe_print("[*] Chat closed.")


def handle_send_file_command(filepath, state, ui):
    with state.state_lock:
        partner = state.current_partner
    if partner is None:
        ui.safe_print("[!] Not in a chat. Use /chat <name|number> first.")
        return
    path = filepath.strip()
    if len(path) >= 2 and path[0] == path[-1] and path[0] in ("'", '"'):
        path = path[1:-1]
    if not path:
        ui.safe_print("[!] Usage: /send <file_path>")
        return
    sender = FileSender(partner, state.get_peer_name(partner), path, state, ui)
    sender.start()
    return sender


def close_all_chats(state):
    for key, sock in state.get_all_chat_conns():
        state.remove_chat_conn(key, expected_sock=sock)
        try:
            send_bye(sock)
        except OSError:
            pass
        _close_socket(sock)
    for sock in state.get_active_sockets():
        _close_socket(sock)
    state.wait_for_socket_cleanup(2.0)
