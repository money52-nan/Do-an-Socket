import os
import socket
import threading
import time

from config import CHUNK_SIZE, CONNECT_TIMEOUT, DOWNLOAD_DIR, FILE_IDLE_TIMEOUT, PROGRESS_MILESTONES
from protocol import ProtocolError, send_file_header, send_hi

_path_lock = threading.Lock()
_reserved = set()
DEMO_CHUNK_DELAY = 0.0


def _reserve_filepath(directory, filename):
    clean = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if clean in ("", ".", "..") or "\x00" in clean or any(c in clean for c in "\r\n"):
        raise ProtocolError("Invalid filename.")
    base, ext = os.path.splitext(clean)
    with _path_lock:
        n = 0
        while True:
            name = clean if n == 0 else f"{base}_({n}){ext}"
            final = os.path.abspath(os.path.join(directory, name))
            part = final + ".part"
            if not any(x in _reserved or os.path.lexists(x) for x in (final, part)):
                _reserved.update((final, part))
                return final, part
            n += 1


def _release_filepath(final, part):
    with _path_lock:
        _reserved.discard(final)
        _reserved.discard(part)


class FileSender(threading.Thread):
    def __init__(self, peer_key, peer_name, filepath, state, ui):
        super().__init__(name=f"FileSender-{os.path.basename(filepath)}", daemon=True)
        self.peer_key = peer_key
        self.peer_name = peer_name
        self.filepath = filepath
        self.state = state
        self.ui = ui

    def run(self):
        sock = None
        filename = os.path.basename(self.filepath)
        try:
            if not os.path.isfile(self.filepath):
                self.ui.safe_print(f"[!] File not found: {self.filepath}")
                return
            with open(self.filepath, "rb") as f:
                size = os.fstat(f.fileno()).st_size
                sock = socket.create_connection(self.peer_key, timeout=CONNECT_TIMEOUT)
                if not self.state.track_socket(sock):
                    return
                sock.settimeout(FILE_IDLE_TIMEOUT)
                send_hi(sock, self.state.my_name, self.state.my_tcp_port)
                send_file_header(sock, filename, size)
                sent = 0
                idx = 0
                while sent < size:
                    if self.state.stop_event.is_set():
                        raise OSError("Application stopping.")
                    chunk = f.read(min(CHUNK_SIZE, size - sent))
                    if not chunk:
                        raise EOFError("Source file was truncated.")
                    sock.sendall(chunk)
                    sent += len(chunk)
                    while idx < len(PROGRESS_MILESTONES) and sent * 100 >= PROGRESS_MILESTONES[idx] * size:
                        m = PROGRESS_MILESTONES[idx]
                        self.ui.safe_print(f"[*] Sending {filename} to {self.peer_name}: {m}%")
                        idx += 1
                    if DEMO_CHUNK_DELAY:
                        time.sleep(DEMO_CHUNK_DELAY)
                if size == 0:
                    self.ui.safe_print(f"[*] Sending {filename} to {self.peer_name}: 100%")
                sock.shutdown(socket.SHUT_WR)
                self.ui.safe_print("[*] File bytes sent (receiver save not confirmed).")
        except (OSError, EOFError, ProtocolError, ValueError) as exc:
            self.ui.safe_print(f"[!] File transfer interrupted: {exc}")
        finally:
            if sock is not None:
                self.state.untrack_socket(sock)
                sock.close()


def receive_file(sock, filename, size_bytes, sender_name, ui):
    final = part = None
    created = False
    try:
        if size_bytes < 0:
            raise ProtocolError("Negative file size.")
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        final, part = _reserve_filepath(DOWNLOAD_DIR, filename)
        ui.safe_print(f"[*] Receiving {filename} ({size_bytes} bytes) from {sender_name}...")
        sock.settimeout(FILE_IDLE_TIMEOUT)
        received = 0
        with open(part, "xb") as f:
            created = True
            while received < size_bytes:
                chunk = sock.recv(min(CHUNK_SIZE, size_bytes - received))
                if not chunk:
                    raise EOFError("Connection lost during file transfer.")
                f.write(chunk)
                received += len(chunk)
        os.replace(part, final)
        created = False
        ui.safe_print(f"[*] Received {filename} from {sender_name} -> saved to {final}")
        return True
    except (EOFError, OSError, ProtocolError, ValueError) as exc:
        if created:
            try:
                os.remove(part)
            except OSError as cleanup_error:
                ui.safe_print(f"[!] Cannot delete partial file: {cleanup_error}")
        ui.safe_print(f"[!] Failed to receive {filename} from {sender_name}: {exc}")
        return False
    finally:
        if final is not None:
            _release_filepath(final, part)
