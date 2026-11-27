"""state.py — Quan ly du lieu dung chung & Lock dong bo giua cac luong.

[CHUNG — Hop dong du lieu giua Vai A, Vai B, Vai C]

QUY TAC VANG TRANH DEADLOCK:
1. Khong bao gio giu `state_lock` trong luc goi recv() hoac sendall() tren mang.
2. Chi giu `state_lock` trong thoi gian cuc ngan de doc/cap nhat dict/list.
3. Moi lenh in ra console phai di qua `ui.safe_print()` (su dung `ui_lock` doc lap).
"""

import socket
import threading
import time
from typing import Dict, List, Optional, Tuple

PeerKey = Tuple[str, int]  # (ip, tcp_port) — dinh danh duy nhat 1 peer


class SharedState:
    def __init__(self, my_name: str, my_tcp_port: int, broadcast_addr: str) -> None:
        # Thong tin cua chinh peer nay
        self.my_name: str = my_name
        self.my_tcp_port: int = my_tcp_port
        self.my_status: str = "online"
        self.broadcast_addr: str = broadcast_addr

        # Co dieu khien vong doi chuong trinh
        self.stop_event = threading.Event()
        self.status_changed_event = threading.Event()  # Danh thuc UDPBroadcaster gui ngay

        # Lock bao ve du lieu dung chung
        self.state_lock = threading.Lock()

        # Bang peer online:
        # { (ip, tcp_port): {"name": str, "status": str, "last_seen": float} }
        self.peers: Dict[PeerKey, dict] = {}

        # Ket noi TCP chat dang mo (toi da 1 ket noi/cap peer):
        # { (ip, tcp_port): socket.socket }
        self.chat_conns: Dict[PeerKey, socket.socket] = {}
        self._chat_ranks = {}
        self._active_sockets = set()
        self._socket_condition = threading.Condition(self.state_lock)
        self._unread_messages: Dict[PeerKey, List[str]] = {}

        # Lich su tin nhan theo tung peer:
        # { (ip, tcp_port): ["[Quan] hello", "[Minh] hi", ...] }
        self.chat_history: Dict[PeerKey, List[str]] = {}

        # Bo dem tin nhan chua doc theo tung peer:
        # { (ip, tcp_port): int }
        self.unread_counts: Dict[PeerKey, int] = {}

        # Doi tac hien tai dang mo cua so chat (None neu dang ranh)
        self.current_partner: Optional[PeerKey] = None

    # ------------------------------------------------------------------
    # Cac ham tien ich thread-safe (Vai A, B, C goi chung)
    # ------------------------------------------------------------------
    def get_my_status(self) -> str:
        with self.state_lock:
            return self.my_status

    def set_my_status(self, new_status: str) -> None:
        with self.state_lock:
            self.my_status = new_status
        # Bao hieu cho luong UDPBroadcaster gui goi HELLO ngay lap tuc
        self.status_changed_event.set()

    def update_peer(self, peer_key: PeerKey, name: str, status: str) -> bool:
        """
        Cap nhat thong tin peer khi nhan goi UDP HELLO.
        Tra ve True neu day la peer MOI xuat hien (de in thong bao online).
        """
        now = time.time()
        with self.state_lock:
            is_new = peer_key not in self.peers
            self.peers[peer_key] = {
                "name": name,
                "status": status,
                "last_seen": now,
            }
            return is_new

    def pop_expired_peers(self, timeout: float) -> List[Tuple[PeerKey, str]]:
        """
        Tim va xoa cac peer qua han `timeout` giay khong thay HELLO.
        Tra ve danh sach [(peer_key, name), ...] de in thong bao offline.
        """
        now = time.time()
        expired: List[Tuple[PeerKey, str]] = []
        with self.state_lock:
            for key, info in list(self.peers.items()):
                if now - info["last_seen"] > timeout:
                    expired.append((key, info["name"]))
                    del self.peers[key]
        return expired

    def get_peers_snapshot(self) -> List[Tuple[PeerKey, dict]]:
        """
        Tra ve ban sao danh sach peer da sap xep on dinh theo (name, ip, port)
        de lenh /list va /chat <so> luon khop chi so.
        """
        with self.state_lock:
            items = [(k, dict(v)) for k, v in self.peers.items()]
        items.sort(key=lambda x: (x[1]["name"].lower(), x[0][0], x[0][1]))
        return items

    def resolve_peer(self, target: str) -> Optional[Tuple[PeerKey, dict]]:
        """
        Tim peer theo so thu tu (1, 2, 3...) hoac theo ten (khong phan biet hoa/thuong).
        Tra ve (peer_key, peer_info) hoac None neu khong tim thay.
        """
        snapshot = self.get_peers_snapshot()
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(snapshot):
                return snapshot[idx]
            return None
        target_lower = target.lower()
        for key, info in snapshot:
            if info["name"].lower() == target_lower:
                return (key, info)
        return None

    def get_peer_name(self, peer_key: PeerKey) -> str:
        with self.state_lock:
            info = self.peers.get(peer_key)
            if info:
                return info["name"]
        return f"{peer_key[0]}:{peer_key[1]}"

    def register_chat_conn(self, peer_key: PeerKey, sock: socket.socket) -> Optional[socket.socket]:
        """Luu socket chat cho peer_key. Tra ve socket cu (neu co) de dong."""
        with self.state_lock:
            old = self.chat_conns.get(peer_key)
            self.chat_conns[peer_key] = sock
            self._chat_ranks.pop(peer_key, None)
            return old

    def get_chat_conn(self, peer_key: PeerKey) -> Optional[socket.socket]:
        with self.state_lock:
            return self.chat_conns.get(peer_key)

    def remove_chat_conn(self, peer_key: PeerKey, expected_sock: Optional[socket.socket] = None) -> bool:
        """
        Xoa ket noi chat cua peer_key. Neu peer_key dang la current_partner thi dat ve None.
        Tra ve True neu peer_key tung la current_partner.
        """
        with self.state_lock:
            cur_sock = self.chat_conns.get(peer_key)
            if expected_sock is not None and cur_sock is not expected_sock:
                return False
            self.chat_conns.pop(peer_key, None)
            self._chat_ranks.pop(peer_key, None)
            if self.current_partner == peer_key:
                self.current_partner = None
                return True
            return False

    def offer_chat_conn(self, peer_key, sock, rank):
        with self.state_lock:
            old = self.chat_conns.get(peer_key)
            if old is sock:
                return True, None
            if self.stop_event.is_set():
                return False, None
            old_rank = self._chat_ranks.get(peer_key)
            if old is not None and old_rank is not None and old_rank <= rank:
                return False, None
            self.chat_conns[peer_key] = sock
            self._chat_ranks[peer_key] = rank
            return True, old

    def track_socket(self, sock):
        with self.state_lock:
            if self.stop_event.is_set():
                return False
            self._active_sockets.add(sock)
            return True

    def untrack_socket(self, sock):
        with self._socket_condition:
            self._active_sockets.discard(sock)
            self._socket_condition.notify_all()

    def wait_for_socket_cleanup(self, timeout):
        with self._socket_condition:
            return self._socket_condition.wait_for(lambda: not self._active_sockets, timeout)

    def get_active_sockets(self):
        with self.state_lock:
            return list(self._active_sockets)

    def activate_chat(self, peer_key):
        with self.state_lock:
            if peer_key not in self.chat_conns:
                return None
            self.current_partner = peer_key
            self.unread_counts[peer_key] = 0
            return self._unread_messages.pop(peer_key, [])

    def record_incoming_message(self, peer_key: PeerKey, sender_name: str, text: str) -> Tuple[bool, int]:
        """
        Luu tin nhan den.
        - Neu dang ranh (current_partner is None) -> tu dong dat peer_key lam doi tac hien tai.
        - Neu dang chat voi peer_key -> hien truc tiep (is_active=True, unread=0).
        - Neu dang chat voi nguoi khac -> tang unread_counts (is_active=False, unread=n).
        """
        line = f"[{sender_name}] {text}"
        with self.state_lock:
            self.chat_history.setdefault(peer_key, []).append(line)
            if self.current_partner is None:
                self.current_partner = peer_key
                return (True, 0)
            if self.current_partner == peer_key:
                return (True, 0)
            self._unread_messages.setdefault(peer_key, []).append(line)
            new_unread = self.unread_counts.get(peer_key, 0) + 1
            self.unread_counts[peer_key] = new_unread
            return (False, new_unread)

    def record_incoming_for_socket(self, peer_key, sock, sender_name, text):
        line = f"[{sender_name}] {text}"
        with self.state_lock:
            if self.chat_conns.get(peer_key) is not sock:
                return None
            self.chat_history.setdefault(peer_key, []).append(line)
            if self.current_partner is None or self.current_partner == peer_key:
                self.current_partner = peer_key
                self.unread_counts[peer_key] = 0
                backlog = self._unread_messages.pop(peer_key, [])
                return True, 0, backlog
            self._unread_messages.setdefault(peer_key, []).append(line)
            count = self.unread_counts.get(peer_key, 0) + 1
            self.unread_counts[peer_key] = count
            return False, count, []

    def record_outgoing_message(self, peer_key: PeerKey, text: str) -> None:
        line = f"[{self.my_name}] {text}"
        with self.state_lock:
            self.chat_history.setdefault(peer_key, []).append(line)

    def switch_to_partner(self, peer_key: PeerKey) -> List[str]:
        """
        Chuyen current_partner sang peer_key, reset unread_counts va tra ve
        danh sach cac tin nhan chua doc (de in ra man hinh).
        """
        with self.state_lock:
            self.current_partner = peer_key
            self.unread_counts[peer_key] = 0
            return self._unread_messages.pop(peer_key, [])

    def get_all_chat_conns(self) -> List[Tuple[PeerKey, socket.socket]]:
        with self.state_lock:
            return list(self.chat_conns.items())
