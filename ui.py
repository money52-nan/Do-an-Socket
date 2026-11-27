"""
ui.py — [VAI C] Giao dien Console khong vo dong (prompt_toolkit) & Bo phan tich lenh.

NHIEM VU VAI C:
1. Bao ve dau ra man hinh bang `ui_lock` + `patch_stdout()` de tin nhan den khong lam mat chu dang go.
2. Xay dung vong lap nhap lenh `run_input_loop()` voi `PromptSession`.
3. Phan tich cac lenh bat dau bang "/" (/list, /chat, /send, /leave, /status, /help, /quit)
   va van ban thuong (gui tin nhan chat); bao tro giup ngan khi go sai lenh.
4. Hoan thien README, kich ban kiem thu 5 nhanh loi va Bao cao 5-10 trang.
"""

import threading
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from discovery import handle_list_command, handle_status_command
from tcp_manager import (
    close_all_chats,
    handle_chat_command,
    handle_leave_command,
    handle_send_file_command,
    handle_send_text,
)

if TYPE_CHECKING:
    from state import SharedState


HELP_TEXT = """Commands:
  /list                  Show online peers
  /chat <name|number>    Open or switch chat with a peer
  <text>                 Send chat message to current partner
  /send <file>           Send a file to current partner
  /leave                 Close the current chat
  /status <online|away>  Change your online status
  /help                  Show this help message
  /quit                  Exit the application"""


class ConsoleUI:
    def __init__(self, state: "SharedState") -> None:
        self.state = state
        self.ui_lock = threading.Lock()
        self.session = PromptSession()

    def safe_print(self, message: str) -> None:
        """
        Ham in DUY NHAT cho moi luong (UDP, TCP, File, Main).
        Co ui_lock de 2 luong khong bao gio in de len nhau.
        """
        with self.ui_lock:
            print(message, flush=True)

    def _get_prompt(self) -> str:
        """Hien thi dau nhac dong lenh (vi du '> ' hoac '[Minh] > ')."""
        partner = self.state.current_partner
        if partner is not None:
            name = self.state.get_peer_name(partner)
            return f"[{name}] > "
        return "> "

    def _dispatch_line(self, line: str) -> bool:
        """
        Phan tich 1 dong nguoi dung nhap.
        Tra ve False neu nguoi dung go /quit, nguoc lai tra ve True.
        """
        # TODO [Vai C]:
        # 1. Bo qua neu line.strip() == "" -> return True
        # 2. Neu khong bat dau bang "/" -> goi handle_send_text(line, self.state, self), return True
        # 3. Tach lenh: parts = line.strip().split(maxsplit=1)
        #    cmd = parts[0].lower(); args = parts[1] if len(parts) > 1 else ""
        # 4. Dieu phoi:
        #    - "/list"   -> handle_list_command(self.state, self)
        #    - "/chat"   -> handle_chat_command(args, self.state, self)
        #    - "/send"   -> handle_send_file_command(args, self.state, self)
        #    - "/leave"  -> handle_leave_command(self.state, self)
        #    - "/status" -> handle_status_command(args, self.state, self)
        #    - "/help"   -> self.safe_print(HELP_TEXT)
        #    - "/quit"   -> self.state.stop_event.set(); close_all_chats(self.state); return False
        #    - Khac      -> self.safe_print(f"[!] Unknown command: {cmd}. Type /help for commands.")
        # 5. return True
        return True

    def run_input_loop(self) -> None:
        """Vong lap doc ban phim tren Main Thread voi patch_stdout()."""
        # TODO [Vai C]:
        # 1. Boc trong `with patch_stdout():`
        # 2. while not self.state.stop_event.is_set():
        #    try:
        #        line = self.session.prompt(self._get_prompt)
        #    except (EOFError, KeyboardInterrupt):
        #        self.state.stop_event.set()
        #        close_all_chats(self.state)
        #        break
        #    if not self._dispatch_line(line):
        #        break
        pass
