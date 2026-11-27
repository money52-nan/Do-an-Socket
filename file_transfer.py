import os
import socket
import threading
from typing import TYPE_CHECKING

from config import CHUNK_SIZE, CONNECT_TIMEOUT, DOWNLOAD_DIR, PROGRESS_MILESTONES
from protocol import send_file_header, send_hi

if TYPE_CHECKING:
    from state import PeerKey, SharedState
    from ui import ConsoleUI


def _get_unique_filepath(directory: str, filename: str) -> str:
    clean_name = os.path.basename(filename) or "received_file"
    base, ext = os.path.splitext(clean_name)
    candidate = os.path.join(directory, clean_name)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base}_({counter}){ext}")
        counter += 1
    return candidate


class FileSender(threading.Thread):
    def __init__(
        self,
        peer_key: "PeerKey",
        peer_name: str,
        filepath: str,
        state: "SharedState",
        ui: "ConsoleUI",
    ) -> None:
        super().__init__(name=f"FileSender-{os.path.basename(filepath)}", daemon=True)
        self.peer_key = peer_key
        self.peer_name = peer_name
        self.filepath = filepath
        self.state = state
        self.ui = ui

    def run(self) -> None:
        # 1. Kiểm tra file có tồn tại trên máy không
        if not os.path.isfile(self.filepath):
            self.ui.safe_print(f"[!] File not found: {self.filepath}")
            return

        filename = os.path.basename(self.filepath)
        file_size = os.path.getsize(self.filepath)
        sock = None

        try:
            # 2. Kết nối tới máy bạn bè và chào hỏi
            sock = socket.create_connection(self.peer_key, timeout=CONNECT_TIMEOUT)
            send_hi(sock, self.state.my_name, self.state.my_tcp_port)
            send_file_header(sock, filename, file_size)

            # 3. Nếu file rỗng 0 byte thì báo 100% luôn
            if file_size == 0:
                self.ui.safe_print(f"[*] Sending {filename} to {self.peer_name}: 100%")
                self.ui.safe_print("[*] File sent successfully.")
                return

            # 4. Đọc từng cục 64KB và gửi đi
            sent_bytes = 0
            milestone_idx = 0
            with open(self.filepath, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    sock.sendall(chunk)
                    sent_bytes += len(chunk)

                    percent = int(sent_bytes * 100 / file_size)
                    while (
                        milestone_idx < len(PROGRESS_MILESTONES)
                        and percent >= PROGRESS_MILESTONES[milestone_idx]
                    ):
                        m = PROGRESS_MILESTONES[milestone_idx]
                        self.ui.safe_print(
                            f"[*] Sending {filename} to {self.peer_name}: {m}%"
                        )
                        milestone_idx += 1

            self.ui.safe_print("[*] File sent successfully.")

        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            self.ui.safe_print(f"[!] File transfer interrupted: {exc}")
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


def receive_file(
    sock: socket.socket,
    filename: str,
    size_bytes: int,
    sender_name: str,
    ui: "ConsoleUI",
) -> None:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    final_path = _get_unique_filepath(DOWNLOAD_DIR, filename)
    temp_path = final_path + ".part"

    ui.safe_print(
        f"[*] Receiving {filename} ({size_bytes} bytes) from {sender_name}..."
    )

    try:
        received = 0
        with open(temp_path, "wb") as f:
            while received < size_bytes:
                to_read = min(CHUNK_SIZE, size_bytes - received)
                chunk = sock.recv(to_read)
                if not chunk:
                    raise EOFError("Connection lost during file transfer.")
                f.write(chunk)
                received += len(chunk)

        # Nhận đủ 100% -> đổi tên file .part thành file thật
        os.replace(temp_path, final_path)
        ui.safe_print(
            f"[*] Received {filename} from {sender_name} -> saved to {final_path}"
        )

    except (EOFError, OSError):
        # Lỗi giữa chừng -> xóa ngay file .part
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        ui.safe_print(
            f"[!] Failed to receive {filename} from {sender_name} (partial file deleted)."
        )