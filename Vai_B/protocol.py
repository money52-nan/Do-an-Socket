"""protocol.py — Dong goi & giai ma giao thuc tang Ung dung (UDP & TCP Framing).

[CHUNG — Vai A & Vai B dung chung, mo ta chi tiet trong Bao cao]

DINH DANG GOI TIN:
- UDP Discovery : HELLO|<name>|<tcp_port>|<status>
- TCP Handshake : HI|<name>|<tcp_port>|
- TCP Chat Msg  : MSG|<utf8_byte_length>|<utf8_payload>
- TCP File      : FILE|<filename>|<size_bytes>|<raw_bytes>
- TCP Leave/Quit: BYE|
"""

import socket
import select
from typing import Optional, Tuple

from config import MAX_HEADER_FIELD_BYTES, MAX_MESSAGE_BYTES, HANDSHAKE_TIMEOUT, VALID_STATUSES


class ProtocolError(Exception):
    """Nem ra khi goi tin sai dinh dang hoac vuot gioi han cho phep."""


# ==============================================================================
# 1. UDP PROTOCOL (HELLO) — Vai A su dung
# ==============================================================================
def build_hello(name: str, tcp_port: int, status: str) -> bytes:
    """Tao datagram UDP: HELLO|<name>|<tcp_port>|<status>"""
    return f"HELLO|{name}|{tcp_port}|{status}".encode("utf-8")


def parse_hello(data: bytes) -> Optional[Tuple[str, int, str]]:
    """
    Phan tich datagram UDP HELLO.
    Tra ve (name, tcp_port, status) neu hop le, nguoc lai tra ve None.
    """
    try:
        text = data.decode("utf-8").strip()
        parts = text.split("|")
        if len(parts) != 4 or parts[0] != "HELLO":
            return None
        name = parts[1].strip()
        tcp_port = int(parts[2])
        status = parts[3].strip().lower()
        if not name or not (1 <= tcp_port <= 65535) or status not in VALID_STATUSES:
            return None
        return (name, tcp_port, status)
    except (UnicodeDecodeError, ValueError):
        return None


# ==============================================================================
# 2. TCP FRAMING HELPERS — Vai B su dung
# ==============================================================================
def recv_exact(sock: socket.socket, num_bytes: int, idle_timeout=None) -> bytes:
    """
    Doc CHINH XAC `num_bytes` byte tu TCP stream (chong nhan thieu goi).
    Nem EOFError neu ket noi dong giua chung truoc khi du byte.
    """
    if num_bytes < 0:
        raise ProtocolError("Negative payload length.")
    chunks = bytearray()
    while len(chunks) < num_bytes:
        if idle_timeout is not None and not select.select([sock], [], [], idle_timeout)[0]:
            raise TimeoutError("Payload stalled.")
        chunk = sock.recv(num_bytes - len(chunks))
        if not chunk:
            raise EOFError("Peer closed connection unexpectedly while reading payload.")
        chunks.extend(chunk)
    return bytes(chunks)


def recv_until(sock: socket.socket, delimiter: bytes = b"|", max_bytes: int = MAX_HEADER_FIELD_BYTES, idle_timeout=None, wait_first=False) -> Optional[bytes]:
    """
    Doc tung byte cho den khi gap `delimiter` (khong bao gom delimiter).
    - Tra ve None neu peer dong ket noi sach se truoc khi doc duoc byte nao.
    - Nem ProtocolError neu vuot qua `max_bytes` (chong goi rac nhu 'nc' gui 'abc').
    - Nem EOFError neu dut ket noi giua chung khi dang doc header.
    """
    buf = bytearray()
    while True:
        if idle_timeout is not None and (buf or wait_first) and not select.select([sock], [], [], idle_timeout)[0]:
            raise TimeoutError("Header stalled.")
        byte = sock.recv(1)
        if not byte:
            if len(buf) == 0:
                return None
            raise EOFError("Peer closed connection mid-header.")
        if byte == delimiter:
            return bytes(buf)
        buf.extend(byte)
        if len(buf) > max_bytes:
            raise ProtocolError("Header field exceeded maximum length.")


def send_hi(sock: socket.socket, name: str, tcp_port: int) -> None:
    """Gui goi dinh danh dau ket noi TCP: HI|<name>|<tcp_port>|"""
    if not name.strip() or any(c in name for c in "|\r\n") or len(name.encode("utf-8")) > MAX_HEADER_FIELD_BYTES or not 1 <= tcp_port <= 65535:
        raise ProtocolError("Invalid HI fields.")
    payload = f"HI|{name}|{tcp_port}|".encode("utf-8")
    sock.sendall(payload)


def recv_hi(sock: socket.socket) -> Tuple[str, int]:
    """
    Doc va xac thuc goi HI dau tien cua moi ket noi TCP den.
    Tra ve (peer_name, peer_tcp_port). Nem ProtocolError neu goi sai dinh dang.
    """
    cmd_bytes = recv_until(sock, b"|")
    if cmd_bytes is None:
        raise EOFError("Connection closed before HI.")
    try:
        cmd = cmd_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("Invalid UTF-8 in command.") from exc

    if cmd != "HI":
        raise ProtocolError(f"Expected HI frame, got: {cmd!r}")

    name_bytes = recv_until(sock, b"|")
    port_bytes = recv_until(sock, b"|")
    if name_bytes is None or port_bytes is None:
        raise EOFError("Incomplete HI frame.")

    try:
        name = name_bytes.decode("utf-8").strip()
        tcp_port = int(port_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProtocolError("Invalid fields in HI frame.") from exc

    if not name or any(c in name for c in "\r\n") or not (1 <= tcp_port <= 65535):
        raise ProtocolError("Out-of-range fields in HI frame.")

    return (name, tcp_port)


def send_msg(sock: socket.socket, text: str) -> None:
    """Gui khung tin nhan chat: MSG|<utf8_byte_length>|<utf8_bytes>"""
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise ProtocolError("Message too large.")
    header = f"MSG|{len(encoded)}|".encode("utf-8")
    sock.sendall(header + encoded)


def send_file_header(sock: socket.socket, filename: str, size_bytes: int) -> None:
    """Gui phan header khung FILE: FILE|<filename>|<size_bytes>| (raw bytes gui theo chunk sau)."""
    safe_name = filename.replace("|", "_")
    if not safe_name or len(safe_name.encode("utf-8")) > MAX_HEADER_FIELD_BYTES or size_bytes < 0:
        raise ProtocolError("Invalid FILE header.")
    header = f"FILE|{safe_name}|{size_bytes}|".encode("utf-8")
    sock.sendall(header)


def send_bye(sock: socket.socket) -> None:
    """Gui khung ket thuc chat: BYE|"""
    sock.sendall(b"BYE|")


def read_field(sock: socket.socket) -> bytes:
    value = recv_until(sock, idle_timeout=HANDSHAKE_TIMEOUT, wait_first=True)
    if value is None:
        raise EOFError("Incomplete header.")
    return value


def read_size(sock: socket.socket, maximum: Optional[int] = None) -> int:
    raw = read_field(sock)
    if not raw.isdigit():
        raise ProtocolError("Invalid size field.")
    size = int(raw)
    if maximum is not None and size > maximum:
        raise ProtocolError("Payload too large.")
    return size
