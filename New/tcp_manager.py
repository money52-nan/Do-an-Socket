# """
# tcp_manager.py — [VAI B] Quan ly ket noi TCP, Chat hai chieu da Peer & Dieu phoi File.

# NHIEM VU VAI B (Phan TCP Chat):
# 1. TCPAcceptor: lang nghe tren cong TCP cua may minh, tao 1 TCPReceiver cho moi ket noi den.
# 2. TCPReceiver:
#    - Doc goi HI dau tien de dinh danh (peer_name, peer_tcp_port).
#    - Phan loai ket noi: neu khung tiep theo la FILE -> goi file_transfer.receive_file() roi dong.
#    - Neu la MSG/BYE -> vong lap nhan tin chat, luu lich su & cap nhat unread_counts.
#    - Xu ly gon khi peer crash (recv tra ve rong / ConnectionResetError) hoac goi sai dinh dang.
# 3. Cac ham lenh: handle_chat_command (/chat), handle_send_text, handle_leave_command (/leave),
#    handle_send_file_command (/send), close_all_chats (/quit).
# 4. Chup anh Wireshark phan TCP (bat tay 3 buoc, Follow TCP Stream, FIN vs RST).
# """

# import socket
# import threading
# from typing import TYPE_CHECKING

# from config import CONNECT_TIMEOUT, SOCKET_TIMEOUT
# from file_transfer import FileSender, receive_file
# from protocol import ProtocolError, recv_exact, recv_hi, recv_until, send_bye, send_hi, send_msg

# if TYPE_CHECKING:
#     from state import PeerKey, SharedState
#     from ui import ConsoleUI


# class TCPAcceptor(threading.Thread):
#     """Luong lang nghe ket noi TCP den tu cac peer khac."""

#     def __init__(self, state: "SharedState", ui: "ConsoleUI") -> None:
#         super().__init__(name="TCPAcceptor", daemon=True)
#         self.state = state
#         self.ui = ui

#     def run(self) -> None:
#         # TODO [Vai B]:
#         # 1. Tao socket TCP (AF_INET, SOCK_STREAM), bat SO_REUSEADDR.
#         # 2. bind(("0.0.0.0", self.state.my_tcp_port)), listen(10), settimeout(SOCKET_TIMEOUT).
#         # 3. Vong lap while not self.state.stop_event.is_set():
#         #    a) try: conn, addr = srv.accept()
#         #       except socket.timeout: continue
#         #       except OSError: break
#         #    b) Tao va khoi chay luong TCPReceiver(conn, addr[0], self.state, self.ui, is_incoming=True)
#         # 4. Dong srv trong finally.
#         pass


# class TCPReceiver(threading.Thread):
#     """Luong doc du lieu tu 1 ket noi TCP (co the la ket noi chat hoac ket noi nhan file)."""

#     def __init__(
#         self,
#         sock: socket.socket,
#         peer_ip: str,
#         state: "SharedState",
#         ui: "ConsoleUI",
#         is_incoming: bool = True,
#         known_peer_key: "PeerKey | None" = None,
#         known_peer_name: str = "",
#     ) -> None:
#         super().__init__(daemon=True)
#         self.sock = sock
#         self.peer_ip = peer_ip
#         self.state = state
#         self.ui = ui
#         self.is_incoming = is_incoming
#         self.peer_key = known_peer_key
#         self.peer_name = known_peer_name

#     def run(self) -> None:
#         # TODO [Vai B]:
#         # 1. Neu self.is_incoming == True:
#         #    - Goi self.peer_name, peer_tcp_port = recv_hi(self.sock)
#         #    - Dat self.peer_key = (self.peer_ip, peer_tcp_port)
#         #    - (Luu y: chua dang ky vao chat_conns voi, cho xem khung dau tien la FILE hay MSG;
#         #       hoac neu la ket noi chat thi dang ky vao state.register_chat_conn)
#         # 2. Vong lap doc tung khung lenh bang cmd_bytes = recv_until(self.sock, b"|"):
#         #    - Neu cmd_bytes is None -> peer dong ket noi dot ngot (crash) -> bao mat ket noi, break.
#         #    - Giai ma cmd = cmd_bytes.decode("utf-8"):
#         #      * "MSG":
#         #          - Dang ky self.sock vao chat_conns neu chua co.
#         #          - Doc length = int(recv_until(self.sock, b"|"))
#         #          - Doc raw = recv_exact(self.sock, length); text = raw.decode("utf-8")
#         #          - Goi is_active, unread = self.state.record_incoming_message(self.peer_key, self.peer_name, text)
#         #          - Neu is_active: self.ui.safe_print(f"[{self.peer_name}] {text}")
#         #          - Nguoc lai: self.ui.safe_print(f"[*] New message from {self.peer_name} ({unread} unread)")
#         #      * "FILE":
#         #          - Doc filename = recv_until(self.sock, b"|").decode("utf-8")
#         #          - Doc size = int(recv_until(self.sock, b"|"))
#         #          - Goi receive_file(self.sock, filename, size, self.peer_name, self.ui)
#         #          - break (dong ket noi file rieng ngay sau khi nhan xong)
#         #      * "BYE":
#         #          - self.ui.safe_print(f"[*] {self.peer_name} left the chat.")
#         #          - break
#         #      * Khac: raise ProtocolError(f"Unknown frame command: {cmd}")
#         # 3. Bat ngoai le (ProtocolError, EOFError, ValueError, ConnectionResetError, OSError):
#         #    - Khong lam crash chuong trinh chinh; in thong bao phu hop neu la ket noi chat.
#         # 4. Trong finally:
#         #    - Neu day la ket noi chat -> goi self.state.remove_chat_conn(self.peer_key, expected_sock=self.sock)
#         #    - Dong self.sock an toan.
#         pass


# # ==============================================================================
# # CAC HAM LENH CHAT & FILE CHO VAI B (duoc goi tu ui.py)
# # ==============================================================================

# def handle_chat_command(target: str, state: "SharedState", ui: "ConsoleUI") -> None:
#     """Xu ly lenh /chat <ten|so>."""
#     # TODO [Vai B]:
#     # 1. Kiem tra target rong -> in "[!] Usage: /chat <name|number>"
#     # 2. Goi resolved = state.resolve_peer(target); neu None -> bao khong tim thay peer.
#     # 3. Lay peer_key, peer_info = resolved; peer_name = peer_info["name"]
#     # 4. Kiem tra state.get_chat_conn(peer_key):
#     #    - Neu DA CO ket noi mo san -> tai su dung, khong mo socket moi!
#     #    - Neu CHUA CO -> mo TCP socket toi peer_key (timeout=CONNECT_TIMEOUT),
#     #      gui send_hi(sock, state.my_name, state.my_tcp_port),
#     #      luu vao state.register_chat_conn(peer_key, sock),
#     #      va khoi chay TCPReceiver(..., is_incoming=False, known_peer_key=peer_key, known_peer_name=peer_name).
#     #      (Neu ket noi that bai / peer vua offline -> bao loi, khong crash!)
#     # 5. Goi unread_msgs = state.switch_to_partner(peer_key)
#     # 6. In "[*] Connected/Switched to <peer_name>" va in toan bo unread_msgs (neu co).
#     pass


# def handle_send_text(text: str, state: "SharedState", ui: "ConsoleUI") -> None:
#     """Gui 1 dong tin nhan chat toi current_partner."""
#     # TODO [Vai B]:
#     # 1. Lay partner = state.current_partner; neu None -> bao "[!] Not in a chat. Use /chat <name|number> first."
#     # 2. Lay sock = state.get_chat_conn(partner); neu None -> bao mat ket noi.
#     # 3. Goi send_msg(sock, text) (boc try/except OSError -> xoa ket noi hong & bao loi).
#     # 4. Luu lich su: state.record_outgoing_message(partner, text).
#     pass


# def handle_leave_command(state: "SharedState", ui: "ConsoleUI") -> None:
#     """Xu ly lenh /leave: gui BYE| va dong ket noi chat hien tai."""
#     # TODO [Vai B]:
#     # 1. Lay partner = state.current_partner; neu None -> bao "[!] You are not in a chat."
#     # 2. Lay sock = state.get_chat_conn(partner), gui send_bye(sock) (bo qua loi neu peer da tat), dong sock.
#     # 3. Goi state.remove_chat_conn(partner) va bao "[*] Chat closed."
#     pass


# def handle_send_file_command(filepath: str, state: "SharedState", ui: "ConsoleUI") -> None:
#     """Xu ly lenh /send <file>: khoi tao luong FileSender rieng cho doi tac hien tai."""
#     # TODO [Vai B]:
#     # 1. Kiem tra state.current_partner (neu None -> bao chua chon doi tac).
#     # 2. Kiem tra filepath rong -> in "[!] Usage: /send <file_path>".
#     # 3. Khoi chay FileSender(partner, peer_name, filepath.strip(), state, ui).start()
#     pass


# def close_all_chats(state: "SharedState") -> None:
#     """Gui BYE| va dong toan bo ket noi chat khi nguoi dung go /quit."""
#     # TODO [Vai B]:
#     # Lap qua state.get_all_chat_conns(), gui send_bye(sock) (try/except) roi sock.close().
#     pass

"""
tcp_manager.py — [VAI B] Quan ly ket noi TCP, Chat hai chieu da Peer & Dieu phoi File.
"""

import socket
import threading
from typing import TYPE_CHECKING

from config import CONNECT_TIMEOUT, SOCKET_TIMEOUT
from file_transfer import FileSender, receive_file
from protocol import ProtocolError, recv_exact, recv_hi, recv_until, send_bye, send_hi, send_msg

if TYPE_CHECKING:
    from state import PeerKey, SharedState
    from ui import ConsoleUI


class TCPAcceptor(threading.Thread):
    """Luong lang nghe ket noi TCP den tu cac peer khac."""

    def __init__(self, state: "SharedState", ui: "ConsoleUI") -> None:
        super().__init__(name="TCPAcceptor", daemon=True)
        self.state = state
        self.ui = ui

    def run(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                srv.bind(("0.0.0.0", self.state.my_tcp_port))
                srv.listen(10)
            except OSError as exc:
                self.ui.safe_print(
                    f"[!] TCPAcceptor failed to bind port {self.state.my_tcp_port}: {exc}"
                )
                return

            srv.settimeout(SOCKET_TIMEOUT)

            while not self.state.stop_event.is_set():
                try:
                    conn, addr = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                receiver = TCPReceiver(
                    sock=conn,
                    peer_ip=addr[0],
                    state=self.state,
                    ui=self.ui,
                    is_incoming=True,
                )
                receiver.start()
        finally:
            srv.close()


class TCPReceiver(threading.Thread):
    """Luong doc du lieu tu 1 ket noi TCP (co the la ket noi chat hoac ket noi nhan file)."""

    def __init__(
        self,
        sock: socket.socket,
        peer_ip: str,
        state: "SharedState",
        ui: "ConsoleUI",
        is_incoming: bool = True,
        known_peer_key: "PeerKey | None" = None,
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

    def _is_still_registered(self) -> bool:
        return (
            self.peer_key is not None
            and self.state.get_chat_conn(self.peer_key) is self.sock
        )

    def run(self) -> None:
        is_chat_conn = not self.is_incoming
        try:
            if self.is_incoming:
                self.peer_name, peer_tcp_port = recv_hi(self.sock)
                self.peer_key = (self.peer_ip, peer_tcp_port)

            while not self.state.stop_event.is_set():
                cmd_bytes = recv_until(self.sock, b"|")
                if cmd_bytes is None:
                    if is_chat_conn and self._is_still_registered():
                        self.ui.safe_print(f"[*] Connection lost with {self.peer_name}.")
                    break

                try:
                    cmd = cmd_bytes.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ProtocolError("Invalid UTF-8 command.") from exc

                if cmd == "MSG":
                    if not is_chat_conn and self.peer_key is not None:
                        is_chat_conn = True
                        old_sock = self.state.register_chat_conn(self.peer_key, self.sock)
                        if old_sock is not None and old_sock is not self.sock:
                            try:
                                old_sock.close()
                            except OSError:
                                pass

                    len_bytes = recv_until(self.sock, b"|")
                    if len_bytes is None:
                        raise EOFError("Incomplete MSG frame.")
                    length = int(len_bytes.decode("utf-8"))
                    if length < 0:
                        raise ProtocolError("Negative message length.")

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
                    name_bytes = recv_until(self.sock, b"|")
                    size_bytes_raw = recv_until(self.sock, b"|")
                    if name_bytes is None or size_bytes_raw is None:
                        raise EOFError("Incomplete FILE header.")
                    filename = name_bytes.decode("utf-8")
                    size_bytes = int(size_bytes_raw.decode("utf-8"))
                    if size_bytes < 0:
                        raise ProtocolError("Negative file size.")
                    receive_file(self.sock, filename, size_bytes, self.peer_name, self.ui)
                    break

                elif cmd == "BYE":
                    if self.peer_name:
                        self.ui.safe_print(f"[*] {self.peer_name} left the chat.")
                    break

                else:
                    raise ProtocolError(f"Unknown frame command: {cmd!r}")

        except (ProtocolError, EOFError, ValueError, UnicodeDecodeError, ConnectionResetError, OSError) as exc:
            if (
                is_chat_conn
                and not self.state.stop_event.is_set()
                and self._is_still_registered()
            ):
                if isinstance(exc, ProtocolError):
                    self.ui.safe_print(f"[!] Protocol error from {self.peer_name}: {exc}")
                else:
                    self.ui.safe_print(f"[*] Connection lost with {self.peer_name}.")
        finally:
            if is_chat_conn and self.peer_key is not None:
                self.state.remove_chat_conn(self.peer_key, expected_sock=self.sock)
            try:
                self.sock.close()
            except OSError:
                pass


# ==============================================================================
# CAC HAM LENH CHAT & FILE CHO VAI B (duoc goi tu ui.py)
# ==============================================================================

def handle_chat_command(target: str, state: "SharedState", ui: "ConsoleUI") -> None:
    """Xu ly lenh /chat <ten|so>."""
    target = target.strip()
    if not target:
        ui.safe_print("[!] Usage: /chat <name|number>")
        return

    resolved = state.resolve_peer(target)
    if resolved is None:
        ui.safe_print(f"[!] Peer not found: {target}. Use /list to see online peers.")
        return

    peer_key, peer_info = resolved
    peer_name = peer_info["name"]

    existing_sock = state.get_chat_conn(peer_key)
    if existing_sock is None:
        sock = None
        try:
            sock = socket.create_connection(peer_key, timeout=CONNECT_TIMEOUT)
            sock.settimeout(None)
            send_hi(sock, state.my_name, state.my_tcp_port)
        except OSError as exc:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
            ui.safe_print(f"[!] Could not connect to {peer_name}: {exc}")
            return

        old_sock = state.register_chat_conn(peer_key, sock)
        if old_sock is not None and old_sock is not sock:
            try:
                old_sock.close()
            except OSError:
                pass

        receiver = TCPReceiver(
            sock=sock,
            peer_ip=peer_key[0],
            state=state,
            ui=ui,
            is_incoming=False,
            known_peer_key=peer_key,
            known_peer_name=peer_name,
        )
        receiver.start()
        action = "Connected to"
    else:
        action = "Switched to"

    unread_msgs = state.switch_to_partner(peer_key)
    ui.safe_print(f"[*] {action} {peer_name}")
    for msg in unread_msgs:
        ui.safe_print(msg)


def handle_send_text(text: str, state: "SharedState", ui: "ConsoleUI") -> None:
    """Gui 1 dong tin nhan chat toi current_partner."""
    partner = state.current_partner
    if partner is None:
        ui.safe_print("[!] Not in a chat. Use /chat <name|number> first.")
        return

    sock = state.get_chat_conn(partner)
    if sock is None:
        state.remove_chat_conn(partner)
        ui.safe_print("[!] Chat connection lost. Use /chat <name|number> to reconnect.")
        return

    try:
        send_msg(sock, text)
    except OSError as exc:
        state.remove_chat_conn(partner, expected_sock=sock)
        try:
            sock.close()
        except OSError:
            pass
        ui.safe_print(f"[!] Failed to send message: {exc}")
        return

    state.record_outgoing_message(partner, text)


def handle_leave_command(state: "SharedState", ui: "ConsoleUI") -> None:
    """Xu ly lenh /leave: gui BYE| va dong ket noi chat hien tai."""
    partner = state.current_partner
    if partner is None:
        ui.safe_print("[!] You are not in a chat.")
        return

    sock = state.get_chat_conn(partner)
    state.remove_chat_conn(partner)
    if sock is not None:
        try:
            send_bye(sock)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    ui.safe_print("[*] Chat closed.")


def handle_send_file_command(filepath: str, state: "SharedState", ui: "ConsoleUI") -> None:
    """Xu ly lenh /send <file>: khoi tao luong FileSender rieng cho doi tac hien tai."""
    partner = state.current_partner
    if partner is None:
        ui.safe_print("[!] Not in a chat. Use /chat <name|number> first.")
        return

    clean_path = filepath.strip().strip('"').strip("'")
    if not clean_path:
        ui.safe_print("[!] Usage: /send <file_path>")
        return

    peer_name = state.get_peer_name(partner)
    FileSender(partner, peer_name, clean_path, state, ui).start()


def close_all_chats(state: "SharedState") -> None:
    """Gui BYE| va dong toan bo ket noi chat khi nguoi dung go /quit."""
    for peer_key, sock in state.get_all_chat_conns():
        state.remove_chat_conn(peer_key, expected_sock=sock)
        try:
            send_bye(sock)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass