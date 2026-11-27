# """
# discovery.py — [VAI A] Kham pha Peer & Quan ly Trang thai qua UDP Broadcast.

# NHIEM VU VAI A:
# 1. Luong UDPBroadcaster: phat goi HELLO dinh ky moi 3s va phat ngay khi /status doi.
# 2. Luong UDPListener: lang nghe cong UDP 9999 (bat SO_REUSEADDR & SO_REUSEPORT),
#    bo qua goi do chinh minh gui, cap nhat bang peer va xu ly timeout 10s.
# 3. Ham xu ly lenh /list va /status.
# 4. Chup anh Wireshark phan UDP (bo loc: udp.port == 9999).
# """

# import socket
# import threading
# from typing import TYPE_CHECKING

# from config import HELLO_INTERVAL, PEER_TIMEOUT, SOCKET_TIMEOUT, UDP_PORT, VALID_STATUSES
# from protocol import build_hello, parse_hello

# if TYPE_CHECKING:
#     from state import SharedState
#     from ui import ConsoleUI


# def get_local_ips() -> set:
#     """
#     Thu thap danh sach IP cua may hien tai de ho tro loc goi UDP cua chinh minh.
#     """
#     ips = {"127.0.0.1"}
#     try:
#         hostname = socket.gethostname()
#         for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
#             ips.add(info[4][0])
#     except OSError:
#         pass
#     try:
#         # Trick khong gui goi that: tim IP ra LAN
#         with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as tmp:
#             tmp.connect(("8.8.8.8", 80))
#             ips.add(tmp.getsockname()[0])
#     except OSError:
#         pass
#     return ips


# class UDPBroadcaster(threading.Thread):
#     """Luong dinh ky broadcast goi HELLO moi 3 giay."""

#     def __init__(self, state: "SharedState", ui: "ConsoleUI") -> None:
#         super().__init__(name="UDPBroadcaster", daemon=True)
#         self.state = state
#         self.ui = ui

#     def run(self) -> None:
#         # TODO [Vai A]:
#         # 1. Tao socket UDP: socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         # 2. Bat quyen broadcast: sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
#         # 3. Vong lap while not self.state.stop_event.is_set():
#         #    a) Lay trang thai hien tai = self.state.get_my_status()
#         #    b) Tao goi tin = build_hello(self.state.my_name, self.state.my_tcp_port, status)
#         #    c) Gui sock.sendto(packet, (self.state.broadcast_addr, UDP_PORT))
#         #       (boc try/except OSError de khong crash khi mat mang)
#         #    d) Cho HELLO_INTERVAL giay HOAC thuc day som neu status_changed_event duoc set:
#         #       self.state.status_changed_event.wait(timeout=HELLO_INTERVAL)
#         #       self.state.status_changed_event.clear()
#         # 4. Dong socket trong khoi finally.
#         pass


# class UDPListener(threading.Thread):
#     """Luong lang nghe goi UDP HELLO tu mang LAN va kiem tra timeout 10s."""

#     def __init__(self, state: "SharedState", ui: "ConsoleUI") -> None:
#         super().__init__(name="UDPListener", daemon=True)
#         self.state = state
#         self.ui = ui
#         self.local_ips = get_local_ips()

#     def _is_self_packet(self, sender_ip: str, name: str, tcp_port: int) -> bool:
#         """Kiem tra xem goi HELLO nay co phai do chinh chuong trinh minh phat ra khong."""
#         return (
#             sender_ip in self.local_ips
#             and tcp_port == self.state.my_tcp_port
#             and name == self.state.my_name
#         )

#     def run(self) -> None:
#         # TODO [Vai A]:
#         # 1. Tao socket UDP (AF_INET, SOCK_DGRAM)
#         # 2. Bat SO_REUSEADDR va kiem tra hasattr(socket, "SO_REUSEPORT") de bat SO_REUSEPORT
#         #    (giup chay nhieu instance tren cung 1 may khong bi loi Address already in use)
#         # 3. Bind vao ("", UDP_PORT) va dat sock.settimeout(SOCKET_TIMEOUT)
#         # 4. Vong lap while not self.state.stop_event.is_set():
#         #    a) try: data, addr = sock.recvfrom(1024)
#         #       except socket.timeout: (bo qua, van tiep tuc kiem tra peer timeout o buoc c)
#         #       except OSError: break
#         #    b) Neu co data:
#         #       - Goi parsed = parse_hello(data); neu None thi bo qua
#         #       - Tach name, tcp_port, status = parsed; sender_ip = addr[0]
#         #       - Neu self._is_self_packet(sender_ip, name, tcp_port) -> continue
#         #       - Goi is_new = self.state.update_peer((sender_ip, tcp_port), name, status)
#         #       - Neu is_new -> self.ui.safe_print(f"[*] {name} ({sender_ip}:{tcp_port}) is online")
#         #    c) Kiem tra timeout:
#         #       - Goi expired = self.state.pop_expired_peers(PEER_TIMEOUT)
#         #       - Voi moi (peer_key, name) trong expired:
#         #         self.ui.safe_print(f"[*] {name} is offline")
#         # 5. Dong socket trong khoi finally.
#         pass


# # ==============================================================================
# # HAM XU LY LENH CLI CHO VAI A (duoc goi tu ui.py)
# # ==============================================================================

# def handle_list_command(state: "SharedState", ui: "ConsoleUI") -> None:
#     """Xu ly lenh /list: in danh sach peer dang online kem STT, ten, IP, cong, trang thai."""
#     # TODO [Vai A]:
#     # 1. Lay snapshot = state.get_peers_snapshot()
#     # 2. Neu rong -> ui.safe_print("[*] No other peers online.")
#     # 3. Nguoc lai -> in tung dong theo dinh dang:
#     #    1. Minh   (192.168.1.12:6000)  online
#     pass


# def handle_status_command(args: str, state: "SharedState", ui: "ConsoleUI") -> None:
#     """Xu ly lenh /status <online|away>."""
#     # TODO [Vai A]:
#     # 1. Kiem tra new_status = args.strip().lower() co thuoc VALID_STATUSES khong.
#     # 2. Neu khong hop le -> ui.safe_print("[!] Usage: /status <online|away>")
#     # 3. Neu hop le -> state.set_my_status(new_status) va bao da doi trang thai.
#     pass
"""
discovery.py — [VAI A] Kham pha Peer & Quan ly Trang thai qua UDP Broadcast.
"""

import socket
import threading
from typing import TYPE_CHECKING

from config import (
    BROADCAST_ADDR_LAN,
    BROADCAST_ADDR_LOCAL,
    HELLO_INTERVAL,
    PEER_TIMEOUT,
    SOCKET_TIMEOUT,
    UDP_PORT,
    VALID_STATUSES,
)
from protocol import build_hello, parse_hello

if TYPE_CHECKING:
    from state import SharedState
    from ui import ConsoleUI


def get_local_ips() -> set:
    """
    Thu thap danh sach IP cua may hien tai de ho tro loc goi UDP cua chinh minh.
    """
    ips = {"127.0.0.1"}
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:
        # Trick khong gui goi that: tim IP ra LAN
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as tmp:
            tmp.connect(("8.8.8.8", 80))
            ips.add(tmp.getsockname()[0])
    except OSError:
        pass
    return ips


class UDPBroadcaster(threading.Thread):
    """Luong dinh ky broadcast goi HELLO moi 3 giay."""

    def __init__(self, state: "SharedState", ui: "ConsoleUI") -> None:
        super().__init__(name="UDPBroadcaster", daemon=True)
        self.state = state
        self.ui = ui

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while not self.state.stop_event.is_set():
                status = self.state.get_my_status()
                packet = build_hello(self.state.my_name, self.state.my_tcp_port, status)
                try:
                    sock.sendto(packet, (self.state.broadcast_addr, UDP_PORT))
                except OSError:
                    # Fallback cho macOS khi lo0 khong ho tro broadcast 127.255.255.255
                    if self.state.broadcast_addr == BROADCAST_ADDR_LOCAL:
                        try:
                            sock.sendto(packet, (BROADCAST_ADDR_LAN, UDP_PORT))
                        except OSError:
                            pass

                self.state.status_changed_event.wait(timeout=HELLO_INTERVAL)
                self.state.status_changed_event.clear()
        finally:
            sock.close()


class UDPListener(threading.Thread):
    """Luong lang nghe goi UDP HELLO tu mang LAN va kiem tra timeout 10s."""

    def __init__(self, state: "SharedState", ui: "ConsoleUI") -> None:
        super().__init__(name="UDPListener", daemon=True)
        self.state = state
        self.ui = ui
        self.local_ips = get_local_ips()

    def _is_self_packet(self, sender_ip: str, name: str, tcp_port: int) -> bool:
        """Kiem tra xem goi HELLO nay co phai do chinh chuong trinh minh phat ra khong."""
        return (
            sender_ip in self.local_ips
            and tcp_port == self.state.my_tcp_port
            and name == self.state.my_name
        )

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    pass

            try:
                sock.bind(("", UDP_PORT))
            except OSError as exc:
                self.ui.safe_print(f"[!] UDPListener failed to bind port {UDP_PORT}: {exc}")
                return

            sock.settimeout(SOCKET_TIMEOUT)

            while not self.state.stop_event.is_set():
                data = None
                addr = None
                try:
                    data, addr = sock.recvfrom(1024)
                except socket.timeout:
                    pass
                except OSError:
                    break

                if data is not None and addr is not None:
                    parsed = parse_hello(data)
                    if parsed is not None:
                        name, tcp_port, status = parsed
                        sender_ip = addr[0]
                        if not self._is_self_packet(sender_ip, name, tcp_port):
                            is_new = self.state.update_peer((sender_ip, tcp_port), name, status)
                            if is_new:
                                self.ui.safe_print(f"[*] {name} ({sender_ip}:{tcp_port}) is online")

                expired = self.state.pop_expired_peers(PEER_TIMEOUT)
                for _peer_key, expired_name in expired:
                    self.ui.safe_print(f"[*] {expired_name} is offline")
        finally:
            sock.close()


# ==============================================================================
# HAM XU LY LENH CLI CHO VAI A (duoc goi tu ui.py)
# ==============================================================================

def handle_list_command(state: "SharedState", ui: "ConsoleUI") -> None:
    """Xu ly lenh /list: in danh sach peer dang online kem STT, ten, IP, cong, trang thai."""
    snapshot = state.get_peers_snapshot()
    if not snapshot:
        ui.safe_print("[*] No other peers online.")
        return

    lines = []
    for idx, ((ip, port), info) in enumerate(snapshot, start=1):
        lines.append(f"  {idx}. {info['name']:<12} ({ip}:{port})  {info['status']}")
    ui.safe_print("\n".join(lines))


def handle_status_command(args: str, state: "SharedState", ui: "ConsoleUI") -> None:
    """Xu ly lenh /status <online|away>."""
    new_status = args.strip().lower()
    if new_status not in VALID_STATUSES:
        ui.safe_print("[!] Usage: /status <online|away>")
        return

    state.set_my_status(new_status)
    ui.safe_print(f"[*] Status changed to '{new_status}'.")