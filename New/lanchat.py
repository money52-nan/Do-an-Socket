"""
lanchat.py — Diem khoi chay chinh cua ung dung LAN Chat & File Sharing (P2P).
[TICH HOP CHUNG — Ca nhom cung tich hop tu Buoc 3]

Cach chay:
  # Chay tren mang LAN that (2+ may):
  python lanchat.py --name Quan --port 5000

  # Test nhieu cua so tren cung 1 may (khong can mang LAN):
  python lanchat.py --name Quan --port 5001 --local
  python lanchat.py --name Minh --port 5002 --local
"""

import argparse
import os
import sys

from config import (
    BROADCAST_ADDR_LAN,
    BROADCAST_ADDR_LOCAL,
    DEFAULT_TCP_PORT,
    DOWNLOAD_DIR,
    UDP_PORT,
)
from discovery import UDPBroadcaster, UDPListener
from state import SharedState
from tcp_manager import TCPAcceptor
from ui import ConsoleUI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LAN Chat & File Sharing (P2P Socket)")
    parser.add_argument("--name", required=True, help="Display name (no '|' character)")
    parser.add_argument("--port", type=int, default=DEFAULT_TCP_PORT, help="Local TCP listening port")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Broadcast to 127.255.255.255 for offline multi-instance testing on 1 PC",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Kiem tra ten hop le (tranh ky tu '|' lam hong giao thuc)
    name = args.name.strip()
    if not name or "|" in name or "\n" in name or "\r" in name:
        print("[!] Invalid --name. Must be non-empty and cannot contain '|'.")
        sys.exit(1)

    if not (1024 <= args.port <= 65535):
        print("[!] Please choose a TCP port between 1024 and 65535.")
        sys.exit(1)

    # Dam bao thu muc downloads/ ton tai
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    broadcast_addr = BROADCAST_ADDR_LOCAL if args.local else BROADCAST_ADDR_LAN
    state = SharedState(my_name=name, my_tcp_port=args.port, broadcast_addr=broadcast_addr)
    ui = ConsoleUI(state)

    # Khoi chay 3 luong nen co dinh: UDP Listener, UDP Broadcaster, TCP Acceptor
    udp_listener = UDPListener(state, ui)
    udp_broadcaster = UDPBroadcaster(state, ui)
    tcp_acceptor = TCPAcceptor(state, ui)

    udp_listener.start()
    udp_broadcaster.start()
    tcp_acceptor.start()

    ui.safe_print(f"[*] Started as '{name}' | TCP port: {args.port} | UDP broadcast: {broadcast_addr}:{UDP_PORT}")
    ui.safe_print("[*] Type /help to view available commands.")

    # Chay vong lap nhap lenh tren Main Thread
    try:
        ui.run_input_loop()
    finally:
        state.stop_event.set()
        state.status_changed_event.set()
        ui.safe_print("[*] Exiting LAN Chat. Goodbye!")


if __name__ == "__main__":
    main()
