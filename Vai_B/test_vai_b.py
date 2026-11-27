import argparse
import threading
import os
import file_transfer
import tcp_manager
from state import SharedState
from tcp_manager import TCPAcceptor, close_all_chats, handle_chat_command, handle_leave_command, handle_send_file_command, handle_send_text


class SimpleUI:
    def __init__(self):
        self.ui_lock = threading.Lock()

    def safe_print(self, msg):
        with self.ui_lock:
            print(msg, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("port", type=int)
    parser.add_argument("friend_port", type=int, nargs="?")
    parser.add_argument("--peer", action="append", default=[])
    parser.add_argument("--downloads", default="downloads")
    parser.add_argument("--slow", type=float, default=0.0)
    parser.add_argument("--explicit-chat", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or args.slow < 0 or not args.name.strip() or any(c in args.name for c in "|\r\n") or len(args.name.encode("utf-8")) > 256:
        parser.error("Invalid name, port or delay.")
    state = SharedState(args.name, args.port, "127.255.255.255")
    ui = SimpleUI()
    if args.friend_port is not None:
        state.update_peer(("127.0.0.1", args.friend_port), "Ban_B", "online")
    for entry in args.peer:
        try:
            name, address = entry.split("=", 1)
            ip, port = address.rsplit(":", 1)
            port = int(port)
            if not name or not ip or not 1 <= port <= 65535:
                raise ValueError()
            state.update_peer((ip, port), name, "online")
        except ValueError:
            parser.error("Use --peer NAME=IP:PORT")
    file_transfer.DOWNLOAD_DIR = os.path.abspath(args.downloads)
    file_transfer.DEMO_CHUNK_DELAY = args.slow
    tcp_manager.EXPLICIT_CHAT_OPEN = args.explicit_chat
    acceptor = TCPAcceptor(state, ui)
    acceptor.start()
    if not acceptor.ready.wait(5) or acceptor.error:
        state.stop_event.set()
        return
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout
    except ImportError:
        from contextlib import nullcontext
        prompt = input
        patch_stdout = nullcontext
    else:
        prompt = PromptSession().prompt
    help_text = "/list | /chat <name|number> | /send <path> | /leave | /quit | /help"
    print(f"[*] {args.name} listening on TCP {args.port}; static peers, no UDP")
    print(help_text)
    try:
        with patch_stdout():
            while True:
                line = prompt("> ")
                if not line.strip():
                    continue
                cmd, _, arg = line.partition(" ")
                if cmd == "/chat":
                    handle_chat_command(arg, state, ui)
                elif cmd == "/send":
                    handle_send_file_command(arg, state, ui)
                elif cmd == "/leave":
                    handle_leave_command(state, ui)
                elif cmd == "/quit":
                    break
                elif cmd == "/list":
                    for i, (key, info) in enumerate(state.get_peers_snapshot(), 1):
                        ui.safe_print(f"{i}. {info['name']} {key[0]}:{key[1]} (static)")
                elif cmd == "/help":
                    ui.safe_print(help_text)
                elif cmd.startswith("/"):
                    ui.safe_print("[!] Unknown command. Use /help.")
                else:
                    handle_send_text(line, state, ui)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        state.stop_event.set()
        close_all_chats(state)
        acceptor.join(2)


if __name__ == "__main__":
    main()
