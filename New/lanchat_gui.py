"""
lanchat_gui.py — Giao dien Desktop (PySide6) cho ung dung LAN Chat & File Sharing.
Tai su dung toan bo lop mang (discovery, tcp_manager, file_transfer, state).

Cach chay:
  python lanchat_gui.py --name Quan --port 5001 --local
  python lanchat_gui.py --name Minh --port 5002 --local
"""

import argparse
import html
import os
import queue
import subprocess
import sys
import threading
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import (
    BROADCAST_ADDR_LAN,
    BROADCAST_ADDR_LOCAL,
    DEFAULT_TCP_PORT,
    DOWNLOAD_DIR,
    UDP_PORT,
    VALID_STATUSES,
)
from discovery import UDPBroadcaster, UDPListener, handle_status_command
from state import PeerKey, SharedState
from tcp_manager import (
    TCPAcceptor,
    close_all_chats,
    handle_chat_command,
    handle_leave_command,
    handle_send_file_command,
    handle_send_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LAN Chat & File Sharing (GUI)")
    parser.add_argument("--name", help="Display name (no '|' character)")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_TCP_PORT, help="Local TCP listening port"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Offline multi-instance testing on 1 PC",
    )
    return parser.parse_args()


class StartupDialog(QDialog):
    """Hop thoai nhap ten, cong TCP va che do mang khi chay khong truyen --name."""

    def __init__(self, default_port: int = DEFAULT_TCP_PORT, default_local: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("LAN Chat — Khởi động")
        self.setFixedWidth(360)
        self.chosen: Optional[Tuple[str, int, bool]] = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Tên hiển thị:"))
        self.name_input = QLineEdit("Quan")
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Cổng TCP (1024–65535):"))
        self.port_input = QLineEdit(str(default_port))
        layout.addWidget(self.port_input)

        self.local_checkbox = QCheckBox("Test nhiều cửa sổ trên cùng 1 máy (--local)")
        self.local_checkbox.setChecked(default_local)
        layout.addWidget(self.local_checkbox)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Hủy")
        ok_btn = QPushButton("Vào LAN Chat")
        ok_btn.setDefault(True)
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self.name_input.selectAll()
        self.name_input.setFocus()

    def _on_submit(self) -> None:
        name = self.name_input.text().strip()
        if not name or "|" in name or "\n" in name or "\r" in name:
            QMessageBox.critical(
                self, "Tên không hợp lệ", "Tên không được để trống và không chứa ký tự '|'."
            )
            return
        try:
            port = int(self.port_input.text().strip())
        except ValueError:
            QMessageBox.critical(self, "Cổng không hợp lệ", "Cổng TCP phải là số nguyên.")
            return
        if not (1024 <= port <= 65535):
            QMessageBox.critical(
                self, "Cổng không hợp lệ", "Vui lòng chọn cổng TCP từ 1024 đến 65535."
            )
            return

        self.chosen = (name, port, self.local_checkbox.isChecked())
        self.accept()


class ChatWindow(QMainWindow):
    """Cua so chinh PySide6 thay the ConsoleUI, cung cap safe_print() thread-safe."""

    def __init__(self, state: SharedState) -> None:
        super().__init__()
        self.state = state
        self.log_queue: "queue.Queue[str]" = queue.Queue()

        self._peer_keys: List[PeerKey] = []
        self._peer_names: List[str] = []
        self._last_peer_rows: List[Tuple[PeerKey, str]] = []
        self._last_partner: Optional[PeerKey] = None
        self._last_msg_count: int = -1

        self.setWindowTitle(f"LAN Chat — {state.my_name} (TCP:{state.my_tcp_port})")
        self.resize(920, 620)
        self.setMinimumSize(720, 480)

        self._build_ui()
        self._apply_styles()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_updates)
        self.timer.start(150)

    def safe_print(self, message: str) -> None:
        """Ham thread-safe nhan thong bao tu cac luong UDP/TCP/File."""
        self.log_queue.put(message)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # ==================== COT TRAI: TAI KHOAN & PEERS ====================
        left_panel = QFrame()
        left_panel.setObjectName("sidebar")
        left_panel.setFixedWidth(260)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)

        me_title = QLabel(f"{self.state.my_name}  (Port {self.state.my_tcp_port})")
        me_title.setObjectName("meTitle")
        left_layout.addWidget(me_title)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Trạng thái:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(list(VALID_STATUSES))
        self.status_combo.setCurrentText(self.state.get_my_status())
        self.status_combo.currentTextChanged.connect(self._on_status_change)
        status_row.addWidget(self.status_combo, 1)
        left_layout.addLayout(status_row)

        peers_heading = QLabel("Đang trực tuyến (nhấn để chat):")
        peers_heading.setObjectName("sectionTitle")
        left_layout.addWidget(peers_heading)

        self.peer_list = QListWidget()
        self.peer_list.itemClicked.connect(self._on_peer_clicked)
        left_layout.addWidget(self.peer_list, 1)

        left_btns = QHBoxLayout()
        self.leave_btn = QPushButton("Rời chat")
        self.leave_btn.clicked.connect(self._on_leave_chat)
        self.downloads_btn = QPushButton("Thư mục tải")
        self.downloads_btn.clicked.connect(self._on_open_downloads)
        left_btns.addWidget(self.leave_btn)
        left_btns.addWidget(self.downloads_btn)
        left_layout.addLayout(left_btns)

        main_layout.addWidget(left_panel)

        # ==================== COT PHAI: KHUNG CHAT & LOG ====================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        header_row = QHBoxLayout()
        self.partner_label = QLabel("Chưa chọn người chat — chọn ở danh sách bên trái")
        self.partner_label.setObjectName("partnerTitle")
        header_row.addWidget(self.partner_label, 1)

        self.send_file_btn = QPushButton("Gửi file...")
        self.send_file_btn.setEnabled(False)
        self.send_file_btn.clicked.connect(self._on_send_file)
        header_row.addWidget(self.send_file_btn)
        right_layout.addLayout(header_row)

        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setObjectName("chatView")
        right_layout.addWidget(self.chat_view, 3)

        input_row = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Nhập tin nhắn rồi nhấn Enter...")
        self.msg_input.returnPressed.connect(self._on_send_text)
        input_row.addWidget(self.msg_input, 1)

        self.send_btn = QPushButton("Gửi")
        self.send_btn.setObjectName("primaryBtn")
        self.send_btn.clicked.connect(self._on_send_text)
        input_row.addWidget(self.send_btn)
        right_layout.addLayout(input_row)

        log_heading = QLabel("Nhật ký kết nối & truyền file:")
        log_heading.setObjectName("sectionTitle")
        right_layout.addWidget(log_heading)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(130)
        self.log_view.setObjectName("logView")
        right_layout.addWidget(self.log_view, 1)

        main_layout.addWidget(right_panel, 1)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background-color: #f3f4f6; }
            QLabel { color: #111827; font-size: 13px; }
            #sidebar {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 10px;
            }
            #meTitle { font-size: 15px; font-weight: bold; color: #1d4ed8; }
            #sectionTitle { font-size: 12px; font-weight: bold; color: #4b5563; }
            #partnerTitle { font-size: 15px; font-weight: bold; color: #111827; }
            QListWidget {
                background-color: #ffffff;
                color: #111827;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 4px;
                font-size: 13px;
            }
            QListWidget::item { padding: 8px; border-radius: 6px; }
            QListWidget::item:selected { background-color: #2563eb; color: #ffffff; }
            #chatView {
                background-color: #ffffff;
                color: #111827;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 8px;
                font-size: 14px;
            }
            #logView {
                background-color: #f9fafb;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 6px;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                background-color: #ffffff;
                color: #111827;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 7px 10px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #e5e7eb;
                color: #111827;
                border: none;
                border-radius: 8px;
                padding: 7px 14px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #d1d5db; }
            QPushButton:disabled { background-color: #f3f4f6; color: #9ca3af; }
            #primaryBtn { background-color: #2563eb; color: #ffffff; }
            #primaryBtn:hover { background-color: #1d4ed8; }
            """
        )

    # ==================== XU LY SU KIEN NGUOI DUNG ====================

    def _on_status_change(self, new_status: str) -> None:
        handle_status_command(new_status, self.state, self)

    def _on_peer_clicked(self, item) -> None:
        idx = self.peer_list.row(item)
        if idx < 0 or idx >= len(self._peer_keys):
            return

        target_key = self._peer_keys[idx]
        if target_key == self.state.current_partner:
            return

        name = self._peer_names[idx]
        target_arg = str(idx + 1) if self._peer_names.count(name) > 1 else name

        threading.Thread(
            target=handle_chat_command,
            args=(target_arg, self.state, self),
            daemon=True,
        ).start()

    def _on_send_text(self) -> None:
        text = self.msg_input.text().strip()
        if not text:
            return
        self.msg_input.clear()
        handle_send_text(text, self.state, self)
        self._refresh_chat_view()

    def _on_send_file(self) -> None:
        if self.state.current_partner is None:
            self.safe_print("[!] Chọn một người ở danh sách bên trái trước khi gửi file.")
            return
        filepath, _ = QFileDialog.getOpenFileName(self, "Chọn file cần gửi")
        if filepath:
            handle_send_file_command(filepath, self.state, self)

    def _on_leave_chat(self) -> None:
        handle_leave_command(self.state, self)
        self._refresh_chat_view()

    def _on_open_downloads(self) -> None:
        abs_dir = os.path.abspath(DOWNLOAD_DIR)
        os.makedirs(abs_dir, exist_ok=True)
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", abs_dir])
            elif os.name == "nt":
                os.startfile(abs_dir)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", abs_dir])
        except OSError as exc:
            self.safe_print(f"[!] Không mở được thư mục tải: {exc}")

    def closeEvent(self, event) -> None:
        self.timer.stop()
        self.state.stop_event.set()
        self.state.status_changed_event.set()
        close_all_chats(self.state)
        event.accept()

    # ==================== CAP NHAT GIAO DIEN DINH KY ====================

    def _drain_logs(self) -> None:
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if msg.startswith("[*]") or msg.startswith("[!]"):
                color = "#b91c1c" if msg.startswith("[!]") else "#374151"
                safe = html.escape(msg)
                self.log_view.append(f'<span style="color:{color};">{safe}</span>')

    def _refresh_peers(self) -> None:
        snapshot = self.state.get_peers_snapshot()
        with self.state.state_lock:
            unread_map = dict(self.state.unread_counts)
            active_partner = self.state.current_partner

        new_rows: List[Tuple[PeerKey, str]] = []
        new_keys: List[PeerKey] = []
        new_names: List[str] = []

        for key, info in snapshot:
            unread = unread_map.get(key, 0)
            badge = f"  ({unread} mới)" if unread > 0 else ""
            dot = "● " if key == active_partner else "  "
            label = f"{dot}{info['name']} [{info['status']}]{badge}"
            new_rows.append((key, label))
            new_keys.append(key)
            new_names.append(info["name"])

        if new_rows != self._last_peer_rows:
            self._last_peer_rows = new_rows
            self._peer_keys = new_keys
            self._peer_names = new_names

            self.peer_list.clear()
            for _key, label in new_rows:
                self.peer_list.addItem(label)

            if active_partner in new_keys:
                self.peer_list.setCurrentRow(new_keys.index(active_partner))

    def _refresh_chat_view(self) -> None:
        with self.state.state_lock:
            partner = self.state.current_partner
            history = list(self.state.chat_history.get(partner, [])) if partner else []

        partner_changed = partner != self._last_partner
        if partner_changed:
            self._last_partner = partner
            self._last_msg_count = -1
            if partner is None:
                self.partner_label.setText(
                    "Chưa chọn người chat — chọn ở danh sách bên trái"
                )
                self.send_file_btn.setEnabled(False)
            else:
                partner_name = self.state.get_peer_name(partner)
                self.partner_label.setText(
                    f"Đang chat với: {partner_name} ({partner[0]}:{partner[1]})"
                )
                self.send_file_btn.setEnabled(True)
                self.msg_input.setFocus()

        if partner_changed or len(history) != self._last_msg_count:
            self._last_msg_count = len(history)
            if partner is None:
                body = (
                    '<p style="color:#6b7280;">Chọn một người dùng đang trực tuyến ở cột bên trái '
                    "để bắt đầu trò chuyện hoặc gửi file.</p>"
                )
            elif not history:
                body = '<p style="color:#6b7280;">Đã kết nối. Hãy gửi tin nhắn đầu tiên!</p>'
            else:
                my_prefix = f"[{self.state.my_name}] "
                parts = []
                for line in history:
                    safe = html.escape(line)
                    if line.startswith(my_prefix):
                        parts.append(
                            f'<div style="margin:4px 0; color:#1d4ed8;"><b>{safe}</b></div>'
                        )
                    else:
                        parts.append(f'<div style="margin:4px 0; color:#111827;">{safe}</div>')
                body = "".join(parts)

            self.chat_view.setHtml(body)
            bar = self.chat_view.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _poll_updates(self) -> None:
        if self.state.stop_event.is_set():
            return
        self._drain_logs()
        self._refresh_peers()
        self._refresh_chat_view()


def main() -> None:
    args = parse_args()
    app = QApplication(sys.argv)

    if args.name:
        name = args.name.strip()
        if not name or "|" in name or "\n" in name or "\r" in name:
            print("[!] Invalid --name. Must be non-empty and cannot contain '|'.")
            sys.exit(1)
        if not (1024 <= args.port <= 65535):
            print("[!] Please choose a TCP port between 1024 and 65535.")
            sys.exit(1)
        port = args.port
        is_local = args.local
    else:
        dlg = StartupDialog(default_port=args.port, default_local=True)
        if dlg.exec() != QDialog.Accepted or dlg.chosen is None:
            return
        name, port, is_local = dlg.chosen

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    broadcast_addr = BROADCAST_ADDR_LOCAL if is_local else BROADCAST_ADDR_LAN
    state = SharedState(my_name=name, my_tcp_port=port, broadcast_addr=broadcast_addr)
    win = ChatWindow(state)

    UDPListener(state, win).start()
    UDPBroadcaster(state, win).start()
    TCPAcceptor(state, win).start()

    win.safe_print(
        f"[*] Started as '{name}' | TCP port: {port} | UDP broadcast: {broadcast_addr}:{UDP_PORT}"
    )

    win.show()
    try:
        sys.exit(app.exec())
    finally:
        state.stop_event.set()
        state.status_changed_event.set()
        close_all_chats(state)


if __name__ == "__main__":
    main()