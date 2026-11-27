# """
# file_transfer.py — [VAI B] Truyen & Nhan File qua ket noi TCP rieng biet.

# NHIEM VU VAI B (Phan File):
# 1. FileSender (1 luong/lan gui): mo ket noi TCP rieng -> gui HI -> gui header FILE
#    -> doc file nhi phan ('rb') theo chunk 64KB -> gui + in % tien do theo bac 25/50/75/100%.
# 2. receive_file (chay trong TCPReceiver khi nhan khung FILE): ghi vao downloads/<name>.part,
#    doi ten sang file that khi du 100% (xu ly trung ten), xoa file .part neu dut mang/loi.
# """

# import os
# import socket
# import threading
# from typing import TYPE_CHECKING

# from config import CHUNK_SIZE, CONNECT_TIMEOUT, DOWNLOAD_DIR, PROGRESS_MILESTONES
# from protocol import send_file_header, send_hi

# if TYPE_CHECKING:
#     from state import PeerKey, SharedState
#     from ui import ConsoleUI


# def _get_unique_filepath(directory: str, filename: str) -> str:
#     """
#     Tao duong dan luu file an toan trong `downloads/`:
#     - Loai bo duong dan doc hai (path traversal) bang os.path.basename.
#     - Neu trung ten file co san -> tu dong doi thanh name_(1).ext, name_(2).ext...
#     """
#     clean_name = os.path.basename(filename) or "received_file"
#     base, ext = os.path.splitext(clean_name)
#     candidate = os.path.join(directory, clean_name)
#     counter = 1
#     while os.path.exists(candidate):
#         candidate = os.path.join(directory, f"{base}_({counter}){ext}")
#         counter += 1
#     return candidate


# class FileSender(threading.Thread):
#     """Luong doc lap gui 1 file toi doi tac ma khong chan luong chat."""

#     def __init__(
#         self,
#         peer_key: "PeerKey",
#         peer_name: str,
#         filepath: str,
#         state: "SharedState",
#         ui: "ConsoleUI",
#     ) -> None:
#         super().__init__(name=f"FileSender-{os.path.basename(filepath)}", daemon=True)
#         self.peer_key = peer_key
#         self.peer_name = peer_name
#         self.filepath = filepath
#         self.state = state
#         self.ui = ui

#     def run(self) -> None:
#         # TODO [Vai B]:
#         # 1. Kiem tra os.path.isfile(self.filepath). Neu khong ton tai:
#         #    self.ui.safe_print(f"[!] File not found: {self.filepath}") va return.
#         # 2. Lay filename = os.path.basename(self.filepath), file_size = os.path.getsize(self.filepath)
#         # 3. Mo ket noi TCP rieng toi self.peer_key (dung socket.create_connection(..., timeout=CONNECT_TIMEOUT))
#         #    (boc try/except OSError de bao loi neu peer offline / tu choi ket noi)
#         # 4. Goi send_hi(sock, self.state.my_name, self.state.my_tcp_port)
#         # 5. Goi send_file_header(sock, filename, file_size)
#         # 6. Mo file o che do 'rb' va doc/gui tung CHUNK_SIZE byte bang sock.sendall(chunk):
#         #    - Tinh percent = int(sent_bytes * 100 / file_size) (xu ly rieng file 0 byte -> 100%)
#         #    - Khi vuot qua tung moc trong PROGRESS_MILESTONES (25, 50, 75, 100):
#         #      in qua self.ui.safe_print(f"[*] Sending {filename} to {self.peer_name}: {milestone}%")
#         # 7. Khi xong 100%: in "[*] File sent successfully." va dong socket (sinh FIN).
#         # 8. Neu loi mang giua chung (BrokenPipeError, ConnectionResetError, OSError):
#         #    in "[!] File transfer interrupted: ..." va dong socket trong finally.
#         pass


# def receive_file(
#     sock: socket.socket,
#     filename: str,
#     size_bytes: int,
#     sender_name: str,
#     ui: "ConsoleUI",
# ) -> None:
#     """
#     Nhan luong byte nhi phan cua 1 file tren ket noi TCP rieng va luu vao downloads/.
#     Duoc goi boi TCPReceiver ngay sau khi doc xong header FILE|<filename>|<size>|.
#     """
#     # TODO [Vai B]:
#     # 1. Dam bao thu muc DOWNLOAD_DIR ton tai: os.makedirs(DOWNLOAD_DIR, exist_ok=True)
#     # 2. Xac dinh final_path = _get_unique_filepath(DOWNLOAD_DIR, filename)
#     #    va temp_path = final_path + ".part"
#     # 3. Thong bao bat dau nhan: ui.safe_print(f"[*] Receiving {filename} ({size_bytes} bytes) from {sender_name}...")
#     # 4. Mo temp_path o che do 'wb':
#     #    - Lap khi received < size_bytes:
#     #      chunk = sock.recv(min(CHUNK_SIZE, size_bytes - received))
#     #      if not chunk: raise EOFError("Connection lost during file transfer.")
#     #      f.write(chunk); received += len(chunk)
#     # 5. Sau khi nhan du 100% va dong file tam -> os.replace(temp_path, final_path)
#     #    Thong bao: ui.safe_print(f"[*] Received {filename} from {sender_name} -> saved to {final_path}")
#     # 6. Trong khoi except (EOFError, OSError):
#     #    - Xoa file tam neu ton tai (if os.path.exists(temp_path): os.remove(temp_path))
#     #    - Bao loi: ui.safe_print(f"[!] Failed to receive {filename} from {sender_name} (partial file deleted).")
#     pass

"""
file_transfer.py — [VAI B] Truyen & Nhan File qua ket noi TCP rieng biet.
"""

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
    """
    Tao duong dan luu file an toan trong `downloads/`:
    - Loai bo duong dan doc hai (path traversal) bang os.path.basename.
    - Neu trung ten file co san -> tu dong doi thanh name_(1).ext, name_(2).ext...
    """
    clean_name = os.path.basename(filename) or "received_file"
    base, ext = os.path.splitext(clean_name)
    candidate = os.path.join(directory, clean_name)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base}_({counter}){ext}")
        counter += 1
    return candidate


class FileSender(threading.Thread):
    """Luong doc lap gui 1 file toi doi tac ma khong chan luong chat."""

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
        if not os.path.isfile(self.filepath):
            self.ui.safe_print(f"[!] File not found: {self.filepath}")
            return

        filename = os.path.basename(self.filepath)
        file_size = os.path.getsize(self.filepath)
        sock = None

        try:
            sock = socket.create_connection(self.peer_key, timeout=CONNECT_TIMEOUT)
            sock.settimeout(None)

            send_hi(sock, self.state.my_name, self.state.my_tcp_port)
            send_file_header(sock, filename, file_size)

            sent_bytes = 0
            milestone_idx = 0

            with open(self.filepath, "rb") as f:
                if file_size == 0:
                    self.ui.safe_print(f"[*] Sending {filename} to {self.peer_name}: 100%")
                else:
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
                            self.ui.safe_print(
                                f"[*] Sending {filename} to {self.peer_name}: "
                                f"{PROGRESS_MILESTONES[milestone_idx]}%"
                            )
                            milestone_idx += 1

            self.ui.safe_print("[*] File sent successfully.")
        except OSError as exc:
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
    """
    Nhan luong byte nhi phan cua 1 file tren ket noi TCP rieng va luu vao downloads/.
    Duoc goi boi TCPReceiver ngay sau khi doc xong header FILE|<filename>|<size>|.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    final_path = _get_unique_filepath(DOWNLOAD_DIR, filename)
    temp_path = final_path + ".part"

    ui.safe_print(f"[*] Receiving {filename} ({size_bytes} bytes) from {sender_name}...")

    received = 0
    try:
        with open(temp_path, "wb") as f:
            while received < size_bytes:
                chunk = sock.recv(min(CHUNK_SIZE, size_bytes - received))
                if not chunk:
                    raise EOFError("Connection lost during file transfer.")
                f.write(chunk)
                received += len(chunk)

        os.replace(temp_path, final_path)
        ui.safe_print(f"[*] Received {filename} from {sender_name} -> saved to {final_path}")
    except (EOFError, OSError):
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        ui.safe_print(
            f"[!] Failed to receive {filename} from {sender_name} (partial file deleted)."
        )