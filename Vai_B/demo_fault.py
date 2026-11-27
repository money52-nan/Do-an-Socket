import argparse
import socket
import struct
import time
from protocol import send_hi, send_msg


def main():
    p = argparse.ArgumentParser()
    p.add_argument("host")
    p.add_argument("port", type=int)
    p.add_argument("--mode", choices=("partial", "stall", "reset", "bad-header"), default="partial")
    args = p.parse_args()
    with socket.create_connection((args.host, args.port), timeout=5) as sock:
        if args.mode == "bad-header":
            sock.sendall(b"abc\n")
            time.sleep(6)
            return
        send_hi(sock, "Probe", 65000)
        if args.mode == "reset":
            send_msg(sock, "Test abrupt reset")
            time.sleep(.3)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            return
        sock.sendall(b"FILE|interrupted.bin|1048576|" + b"x" * 65536)
        time.sleep(12 if args.mode == "stall" else 2)


if __name__ == "__main__":
    main()
