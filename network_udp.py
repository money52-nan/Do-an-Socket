import socket
import time
import threading

UDP_PORT = 9999
BROADCAST_INTERVAL = 3.0  # Gửi gói HELLO mỗi 3 giây
PEER_TIMEOUT = 10.0       # Quá 10 giây không nhận được gói -> coi như offline

class UDPDiscovery:
    def __init__(self, my_name: str, my_tcp_port: int, safe_print):
        self.my_name = my_name
        self.my_tcp_port = my_tcp_port
        self.safe_print = safe_print

        self.status = "online"
        self.peers = {}  # { "Tên": {"ip": ..., "port": ..., "status": ..., "last_seen": ...} }
        self.peers_lock = threading.Lock()

        self.stop_event = threading.Event()
        self.broadcast_wakeup = threading.Event()  # Dùng để gửi gói ngay khi đổi /status

    def set_status(self, new_status: str):
        """Đổi trạng thái (online/away) và phát sóng ngay lập tức."""
        if new_status not in ("online", "away"):
            self.safe_print("[!] Trạng thái không hợp lệ. Chỉ dùng: online hoặc away.")
            return
        self.status = new_status
        self.broadcast_wakeup.set()  # Đánh thức luồng broadcast để gửi ngay
        self.safe_print(f"[*] Đã đổi trạng thái của bạn thành: {new_status}")

    def get_peers_snapshot(self) -> list:
        """Trả về danh sách peer đang online dưới dạng list các tuple (tên, info) để đánh STT."""
        with self.peers_lock:
            return [(name, info.copy()) for name, info in self.peers.items()]

    def find_peer(self, identifier: str):
        """Tìm peer theo tên hoặc số thứ tự trong lệnh /list."""
        snapshot = self.get_peers_snapshot()
        # 1. Thử tìm theo số thứ tự (bắt đầu từ 1)
        if identifier.isdigit():
            idx = int(identifier) - 1
            if 0 <= idx < len(snapshot):
                return snapshot[idx]
            return None

        # 2. Tìm theo tên (không phân biệt hoa thường)
        for name, info in snapshot:
            if name.lower() == identifier.lower():
                return (name, info)
        return None

    def _broadcaster_loop(self):
        """Luồng gửi gói HELLO|<tên>|<tcp_port>|<status> định kỳ 3s."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while not self.stop_event.is_set():
            payload = f"HELLO|{self.my_name}|{self.my_tcp_port}|{self.status}".encode('utf-8')
            try:
                sock.sendto(payload, ('255.255.255.255', UDP_PORT))
            except Exception as e:
                self.safe_print(f"[!] Lỗi gửi UDP broadcast: {e}")

            # Chờ 3s hoặc thức dậy sớm nếu người dùng vừa đổi /status
            self.broadcast_wakeup.wait(BROADCAST_INTERVAL)
            self.broadcast_wakeup.clear()

        sock.close()

    def _listener_loop(self):
        """Luồng lắng nghe gói HELLO từ các máy khác trong LAN."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Hỗ trợ chạy nhiều cửa sổ trên cùng 1 máy (Linux/macOS)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass

        sock.bind(('', UDP_PORT))
        sock.settimeout(1.0)  # Timeout 1s để vòng lặp có thể kiểm tra stop_event

        while not self.stop_event.is_set():
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except Exception:
                break

            sender_ip = addr[0]
            try:
                msg = data.decode('utf-8').strip()
                parts = msg.split('|')
                if len(parts) != 4 or parts[0] != "HELLO":
                    continue

                _, name, tcp_port_str, status = parts
                tcp_port = int(tcp_port_str)

                # Bỏ qua gói tin do chính mình phát ra
                if name == self.my_name and tcp_port == self.my_tcp_port:
                    continue

                with self.peers_lock:
                    is_new = name not in self.peers
                    self.peers[name] = {
                        "ip": sender_ip,
                        "port": tcp_port,
                        "status": status,
                        "last_seen": time.time()
                    }

                if is_new:
                    self.safe_print(f"[*] {name} is online ({sender_ip}:{tcp_port})")

            except Exception:
                # Bỏ qua các gói UDP rác không đúng định dạng
                continue

        sock.close()

    def _timeout_checker_loop(self):
        """Luồng kiểm tra peer nào quá 10s không gửi HELLO thì xóa khỏi danh sách."""
        while not self.stop_event.is_set():
            time.sleep(1.0)
            now = time.time()
            offline_list = []

            with self.peers_lock:
                for name, info in list(self.peers.items()):
                    if now - info["last_seen"] > PEER_TIMEOUT:
                        offline_list.append(name)
                        del self.peers[name]

            for name in offline_list:
                self.safe_print(f"[*] {name} is offline")

    def start(self):
        """Khởi chạy cả 3 luồng UDP."""
        threading.Thread(target=self._broadcaster_loop, daemon=True).start()
        threading.Thread(target=self._listener_loop, daemon=True).start()
        threading.Thread(target=self._timeout_checker_loop, daemon=True).start()

    def stop(self):
        """Dừng các luồng UDP."""
        self.stop_event.set()
        self.broadcast_wakeup.set()