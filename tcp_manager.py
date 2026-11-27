import socket
import threading
from typing import Optional, TYPE_CHECKING

from config import CONNECT_TIMEOUT, SOCKET_TIMEOUT
from file_transfer import FileSender, receive_file
from protocol import (
    ProtocolError,
    recv_exact,
    recv_hi,
    recv_until,
    send_bye,
    send_hi,
    send_msg,
)

if TYPE_CHECKING:
    from state import PeerKey, SharedState
    from ui import ConsoleUI


class TCPAcceptor(threading.Thread):
    def __init__(self, state: "SharedState", ui: "ConsoleUI") -> None:
        super().__init__(name="TCPAcceptor", daemon=True)
        self.state = state
        self.ui = ui

    def run(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("0.0.0.0", self.state.my_tcp_port))
            srv.listen(10)
            srv.settimeout(SOCKET_TIMEOUT)

            while not self.state.stop_event.is_set():
                try:
                    conn, addr = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                receiver = TCPReceiver(
                    conn, addr[0], self.state, self.ui, is_incoming=True
                )
                receiver.start()
        finally:
            try:
                srv.close()
            except OSError:
                pass


class TCPReceiver(threading.Thread):
    def __init__(
        self,
        sock: socket.socket,
        peer_ip: str,
        state: "SharedState",
        ui: "ConsoleUI",
        is_incoming: bool = True,
        known_peer_key: Optional["PeerKey"] = None,
        known_peer_name: str = "",
    ) -> None:
        super().__init__(daemon=True)
        self.sock = sock
        self.peer_ip = peer_ip
        self.state = state
        self.ui = ui
        self.is_incoming = is_incoming
        self.peer_key = known_peer_key
        self.peer_name = known_peer_name

    def run(self) -> None:
        is_chat_conn = not self.is_incoming
        try:
            # 1. Nếu là người khác kết nối tới mình -> phải đọc gói chào HI trước
            if self.is_incoming:
                self.peer_name, peer_tcp_port = recv_hi(self.sock)
                self.peer_key = (self.peer_ip, peer_tcp_port)

            # 2. Vòng lặp đọc tin nhắn / file / lệnh rời đi
            while not self.state.stop_event.is_set():
                cmd_bytes = recv_until(self.sock, b"|")
                if cmd_bytes is None:
                    if is_chat_conn and self.peer_name:
                        self.ui.safe_print(
                            f"[!] Connection lost with {self.peer_name}."
                        )
                    break

                cmd = cmd_bytes.decode("utf-8")

                if cmd == "MSG":
                    if not is_chat_conn and self.peer_key is not None:
                        is_chat_conn = True
                        old_sock = self.state.register_chat_conn(
                            self.peer_key, self.sock
                        )
                        if old_sock is not None and old_sock is not self.sock:
                            try:
                                old_sock.close()
                            except OSError:
                                pass

                    len_bytes = recv_until(self.sock, b"|")
                    if len_bytes is None:
                        raise EOFError("Incomplete MSG length.")
                    length = int(len_bytes.decode("utf-8"))

                    raw = recv_exact(self.sock, length)
                    text = raw.decode("utf-8")

                    if self.peer_key is not None:
                        is_active, unread = self.state.record_incoming_message(
                            self.peer_key, self.peer_name, text
                        )
                        if is_active:
                            self.ui.safe_print(f"[{self.peer_name}] {text}")
                        else:
                            self.ui.safe_print(
                                f"[*] New message from {self.peer_name} ({unread} unread)"
                            )

                elif cmd == "FILE":
                    fn_bytes = recv_until(self.sock, b"|")
                    sz_bytes = recv_until(self.sock, b"|")
                    if fn_bytes is None or sz_bytes is None:
                        raise EOFError("Incomplete FILE header.")
                    filename = fn_bytes.decode("utf-8")
                    size = int(sz_bytes.decode("utf-8"))

                    receive_file(self.sock, filename, size, self.peer_name, self.ui)
                    break

                elif cmd == "BYE":
                    self.ui.safe_print(f"[*] {self.peer_name} left the chat.")
                    break

                else:
                    raise ProtocolError(f"Unknown frame command: {cmd}")

        except (
            ProtocolError,
            EOFError,
            ValueError,
            UnicodeDecodeError,
            ConnectionResetError,
            OSError,
        ):
            if is_chat_conn and self.peer_name and not self.state.stop_event.is_set():
                self.ui.safe_print(f"[!] Disconnected from {self.peer_name}.")
        finally:
            if is_chat_conn and self.peer_key is not None:
                was_current = self.state.remove_chat_conn(
                    self.peer_key, expected_sock=self.sock
                )
                if was_current and not self.state.stop_event.is_set():
                    self.ui.safe_print("[*] Returned to main prompt.")
            try:
                self.sock.close()
            except OSError:
                pass


def handle_chat_command(target: str, state: "SharedState", ui: "ConsoleUI") -> None:
    target = target.strip()
    if not target:
        ui.safe_print("[!] Usage: /chat <name|number>")
        return

    resolved = state.resolve_peer(target)
    if resolved is None:
        ui.safe_print(f"[!] Peer not found: {target}")
        return

    peer_key, peer_info = resolved
    peer_name = peer_info["name"]

    sock = state.get_chat_conn(peer_key)
    if sock is None:
        try:
            sock = socket.create_connection(peer_key, timeout=CONNECT_TIMEOUT)
            sock.settimeout(None)
            send_hi(sock, state.my_name, state.my_tcp_port)
        except OSError as exc:
            ui.safe_print(f"[!] Cannot connect to {peer_name}: {exc}")
            return

        old_sock = state.register_chat_conn(peer_key, sock)
        if old_sock is not None and old_sock is not sock:
            try:
                old_sock.close()
            except OSError:
                pass

        receiver = TCPReceiver(
            sock,
            peer_key[0],
            state,
            ui,
            is_incoming=False,
            known_peer_key=peer_key,
            known_peer_name=peer_name,
        )
        receiver.start()

    unread_msgs = state.switch_to_partner(peer_key)
    ui.safe_print(f"[*] Connected/Switched to {peer_name}")
    for msg in unread_msgs:
        ui.safe_print(msg)


def handle_send_text(text: str, state: "SharedState", ui: "ConsoleUI") -> None:
    with state.state_lock:
        partner = state.current_partner

    if partner is None:
        ui.safe_print("[!] Not in a chat. Use /chat <name|number> first.")
        return

    sock = state.get_chat_conn(partner)
    if sock is None:
        state.remove_chat_conn(partner)
        ui.safe_print("[!] Chat connection lost.")
        return

    try:
        send_msg(sock, text)
        state.record_outgoing_message(partner, text)
    except OSError as exc:
        state.remove_chat_conn(partner, expected_sock=sock)
        try:
            sock.close()
        except OSError:
            pass
        ui.safe_print(f"[!] Failed to send message: {exc}")


def handle_leave_command(state: "SharedState", ui: "ConsoleUI") -> None:
    with state.state_lock:
        partner = state.current_partner

    if partner is None:
        ui.safe_print("[!] You are not in a chat.")
        return

    sock = state.get_chat_conn(partner)
    if sock is not None:
        try:
            send_bye(sock)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    state.remove_chat_conn(partner)
    ui.safe_print("[*] Chat closed.")


def handle_send_file_command(
    filepath: str, state: "SharedState", ui: "ConsoleUI"
) -> None:
    with state.state_lock:
        partner = state.current_partner

    if partner is None:
        ui.safe_print("[!] Not in a chat. Use /chat <name|number> first.")
        return

    clean_path = filepath.strip()
    if not clean_path:
        ui.safe_print("[!] Usage: /send <file_path>")
        return

    peer_name = state.get_peer_name(partner)
    sender = FileSender(partner, peer_name, clean_path, state, ui)
    sender.start()


def close_all_chats(state: "SharedState") -> None:
    for _, sock in state.get_all_chat_conns():
        try:
            send_bye(sock)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass