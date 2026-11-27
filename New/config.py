"""
config.py — Cau hinh hang so dung chung cho toan bo du an (Buoc 0).
Ca nhom thong nhat file nay truoc khi bat dau code tung vai.
"""

# --- Mang & Cong ---
UDP_PORT = 9999                 # Cong UDP co dinh cho Peer Discovery & Status
DEFAULT_TCP_PORT = 5000         # Cong TCP mac dinh cho Chat & File
BROADCAST_ADDR_LAN = "255.255.255.255"      # Dung khi chay 2+ may cung LAN/Wi-Fi
BROADCAST_ADDR_LOCAL = "127.255.255.255"    # Dung khi test offline nhieu instance tren 1 may

# --- Thoi gian (giay) ---
HELLO_INTERVAL = 3.0            # Chu ky gui goi UDP HELLO (giay)
PEER_TIMEOUT = 10.0             # Qua 10s khong nghe HELLO -> xoa peer & bao offline
SOCKET_TIMEOUT = 1.0            # Timeout cho accept()/recvfrom() de kiem tra stop_event
CONNECT_TIMEOUT = 5.0           # Timeout khi goi TCP connect() toi peer

# --- Truyen file & Framing ---
CHUNK_SIZE = 65536              # 64 KB moi chunk khi doc/ghi file nhi phan
MAX_HEADER_FIELD_BYTES = 256    # Gioi han do dai 1 truong header (chong goi rac/DoS)
PROGRESS_MILESTONES = (25, 50, 75, 100)  # Cac moc % in tien do truyen file
DOWNLOAD_DIR = "downloads"      # Thu muc luu file nhan duoc

# --- Trang thai hop le ---
VALID_STATUSES = ("online", "away")
