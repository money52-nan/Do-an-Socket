import hashlib
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import file_transfer as ft
import tcp_manager as tm
from protocol import ProtocolError, recv_exact, recv_until, send_hi, send_msg
from state import SharedState


class UI:
    def __init__(self):
        self.lock = threading.Lock()
        self.lines = []

    def safe_print(self, msg):
        with self.lock:
            self.lines.append(msg)

    def contains(self, text):
        with self.lock:
            return any(text in line for line in self.lines)


def wait_for(predicate, timeout=4):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(.01)
    return bool(predicate())


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.downloads = self.folder / "downloads"
        self.nodes = []
        self.patches = [patch.object(ft, "DOWNLOAD_DIR", str(self.downloads)), patch.object(ft, "FILE_IDLE_TIMEOUT", .4), patch.object(tm, "HANDSHAKE_TIMEOUT", .4), patch.object(tm, "EXPLICIT_CHAT_OPEN", False)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for state, ui, acceptor in self.nodes:
            state.stop_event.set()
            tm.close_all_chats(state)
        for state, ui, acceptor in self.nodes:
            acceptor.join(2)
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def node(self, name):
        s = SharedState(name, free_port(), "127.255.255.255")
        ui = UI()
        t = tm.TCPAcceptor(s, ui)
        self.nodes.append((s, ui, t))
        t.start()
        self.assertTrue(t.ready.wait(2))
        self.assertIsNone(t.error)
        for other, _, _ in self.nodes:
            if other is not s:
                s.update_peer(self.key(other), other.my_name, "online")
                other.update_peer(self.key(s), name, "online")
        return s, ui

    def key(self, s):
        return "127.0.0.1", s.my_tcp_port

    def chat(self, a, ua, b, ub):
        tm.handle_chat_command(b.my_name, a, ua)
        tm.handle_send_text("Chào | 😊", a, ua)
        self.assertTrue(wait_for(lambda: ub.contains("Chào | 😊")))

    def raw(self, s):
        return socket.create_connection(self.key(s), timeout=2)

    def file_frame(self, s, name, data, claimed=None):
        with self.raw(s) as sock:
            send_hi(sock, "Raw", 60000)
            sock.sendall(f"FILE|{name}|{len(data) if claimed is None else claimed}|".encode()+data)

    def test_01_fragmented_and_coalesced_frames(self):
        a, b = socket.socketpair()
        with a, b:
            payload = "Việt | 😊".encode()
            wire = f"MSG|{len(payload)}|".encode()+payload+b"MSG|3|abc"
            for byte in wire[:8]:
                a.sendall(bytes([byte]))
            a.sendall(wire[8:])
            for expected in (payload, b"abc"):
                self.assertEqual(recv_until(b), b"MSG")
                self.assertEqual(recv_exact(b, int(recv_until(b))), expected)
            with self.assertRaises(ProtocolError):
                recv_exact(b, -1)

    def test_02_chat_two_way_reuse_and_leave(self):
        a, ua = self.node("A"); b, ub = self.node("B")
        self.chat(a, ua, b, ub)
        original = b.get_chat_conn(self.key(a))
        tm.handle_chat_command("A", b, ub)
        self.assertIs(original, b.get_chat_conn(self.key(a)))
        tm.handle_send_text("Reply", b, ub)
        self.assertTrue(wait_for(lambda: ua.contains("Reply")))
        tm.handle_leave_command(a, ua)
        self.assertTrue(wait_for(lambda: ub.contains("left the chat")))
        self.assertIsNone(b.current_partner)

    def test_03_three_peers_unread(self):
        a, ua = self.node("A"); b, ub = self.node("B"); c, uc = self.node("C")
        self.chat(a, ua, b, ub)
        tm.handle_chat_command("B", c, uc)
        tm.handle_send_text("one", c, uc); tm.handle_send_text("two", c, uc)
        self.assertTrue(wait_for(lambda: ub.contains("2 unread")))
        tm.handle_chat_command("C", b, ub)
        self.assertTrue(ub.contains("[C] one") and ub.contains("[C] two"))
        self.assertEqual(b.unread_counts[self.key(c)], 0)

    def test_04_binary_hash_and_progress(self):
        a, ua = self.node("A"); b, ub = self.node("B")
        self.chat(a, ua, b, ub)
        src = self.folder / "data.bin"; src.write_bytes(os.urandom(250000))
        sender = tm.handle_send_file_command(str(src), a, ua); sender.join(3)
        dst = self.downloads / src.name
        self.assertTrue(wait_for(dst.exists))
        self.assertEqual(hashlib.sha256(src.read_bytes()).digest(), hashlib.sha256(dst.read_bytes()).digest())
        for n in (25, 50, 75, 100):
            self.assertTrue(ua.contains(f": {n}%"))

    def test_05_concurrent_bidirectional_file_and_chat(self):
        a, ua = self.node("A"); b, ub = self.node("B")
        self.chat(a, ua, b, ub)
        x = self.folder / "a.bin"; y = self.folder / "b.bin"
        x.write_bytes(os.urandom(1024*1024)); y.write_bytes(os.urandom(1024*1024))
        with patch.object(ft, "DEMO_CHUNK_DELAY", .02):
            t1 = tm.handle_send_file_command(str(x), a, ua); t2 = tm.handle_send_file_command(str(y), b, ub)
            self.assertTrue(wait_for(lambda: ua.contains("25%") and ub.contains("25%")))
            tm.handle_send_text("during transfer", a, ua)
            self.assertTrue(wait_for(lambda: ub.contains("during transfer")))
            self.assertTrue(t1.is_alive() or t2.is_alive())
            t1.join(3); t2.join(3)
        for src in (x, y):
            dst = self.downloads / src.name
            self.assertTrue(wait_for(dst.exists)); self.assertEqual(src.read_bytes(), dst.read_bytes())

    def test_06_same_name_parallel(self):
        a, ua = self.node("A")
        payloads = [b"A"*200000, b"B"*200000]
        threads = [threading.Thread(target=self.file_frame,args=(a,"same.bin",p)) for p in payloads]
        for t in threads:t.start()
        for t in threads:t.join(2)
        self.assertTrue(wait_for(lambda: len(list(self.downloads.glob("*.bin"))) == 2))
        self.assertCountEqual([p.read_bytes() for p in self.downloads.glob("*.bin")], payloads)
        self.assertFalse(list(self.downloads.glob("*.part")))

    def test_07_partial_eof(self):
        a, ua = self.node("A")
        self.file_frame(a,"partial.bin",b"abc",100)
        self.assertTrue(wait_for(lambda: ua.contains("Failed to receive")))
        self.assertFalse(list(self.downloads.iterdir()))

    def test_08_partial_timeout(self):
        a, ua = self.node("A")
        with self.raw(a) as sock:
            send_hi(sock,"Raw",60000); sock.sendall(b"FILE|stall.bin|100|abc")
            self.assertTrue(wait_for(lambda: (self.downloads/"stall.bin.part").exists()))
            self.assertTrue(wait_for(lambda: ua.contains("Failed to receive")))
            self.assertFalse(list(self.downloads.iterdir()))

    def test_09_bad_header_and_negative_size(self):
        a, ua = self.node("A")
        with self.raw(a) as sock:
            sock.sendall(b"abc\n")
            self.assertTrue(wait_for(lambda: ua.contains("Rejected TCP")))
        with self.raw(a) as sock:
            send_hi(sock,"Raw",60000); sock.sendall(b"FILE|bad.bin|-1|")
        self.assertTrue(wait_for(lambda: sum("Rejected TCP" in x for x in ua.lines)>=2))
        self.assertFalse((self.downloads/"bad.bin").exists())
        b, ub = self.node("B"); self.chat(b, ub, a, ua)

    def test_10_empty_file(self):
        a, ua = self.node("A"); b, ub = self.node("B"); self.chat(a,ua,b,ub)
        src=self.folder/"empty.bin"; src.touch()
        t=tm.handle_send_file_command(str(src),a,ua); t.join(2)
        self.assertTrue(wait_for(lambda:(self.downloads/src.name).exists()))
        self.assertEqual((self.downloads/src.name).stat().st_size,0)
        self.assertTrue(ua.contains("100%"))

    def test_11_missing_and_offline(self):
        a, ua = self.node("A"); b, ub = self.node("B"); self.chat(a,ua,b,ub)
        t=tm.handle_send_file_command(str(self.folder/"missing.bin"),a,ua); t.join(2)
        self.assertTrue(ua.contains("File not found"))
        a.update_peer(("127.0.0.1",free_port()),"Gone","online")
        tm.handle_chat_command("Gone",a,ua)
        self.assertTrue(ua.contains("Cannot connect"))

    def test_12_old_receiver_cannot_clear_new(self):
        s=SharedState("A",5001,""); key=("127.0.0.1",5002)
        a,b=socket.socketpair()
        with a,b:
            s.register_chat_conn(key,a); s.switch_to_partner(key); s.register_chat_conn(key,b)
            self.assertFalse(s.remove_chat_conn(key,a))
            self.assertEqual(s.current_partner,key); self.assertIs(s.get_chat_conn(key),b)

    def test_13_abrupt_close(self):
        a,ua=self.node("A"); b,ub=self.node("B"); self.chat(a,ua,b,ub)
        tm._close_socket(a.get_chat_conn(self.key(b)))
        self.assertTrue(wait_for(lambda: ub.contains("Connection lost") or ub.contains("Disconnected")))
        self.assertTrue(wait_for(lambda: b.current_partner is None))

    def test_14_explicit_open_before_message(self):
        with patch.object(tm,"EXPLICIT_CHAT_OPEN",True):
            a,ua=self.node("A"); b,ub=self.node("B")
            tm.handle_chat_command("B",a,ua)
            self.assertTrue(wait_for(lambda:b.get_chat_conn(self.key(a)) is not None))
            original=b.get_chat_conn(self.key(a)); tm.handle_chat_command("A",b,ub)
            self.assertIs(b.get_chat_conn(self.key(a)),original)
            tm.handle_send_text("early reply",b,ub)
            self.assertTrue(wait_for(lambda:ua.contains("early reply")))

    def test_15_quit_closes_pending_file(self):
        a,ua=self.node("A")
        with self.raw(a) as sock:
            send_hi(sock,"Raw",60000); sock.sendall(b"FILE|quit.bin|1000|abc")
            self.assertTrue(wait_for(lambda:(self.downloads/"quit.bin.part").exists()))
            a.stop_event.set(); tm.close_all_chats(a)
            self.assertTrue(wait_for(lambda:ua.contains("Failed to receive")))
            self.assertFalse(list(self.downloads.iterdir()))

    def test_16_simultaneous_explicit_open(self):
        with patch.object(tm,"EXPLICIT_CHAT_OPEN",True):
            a,ua=self.node("A"); b,ub=self.node("B")
            barrier=threading.Barrier(2)
            def open_chat(src,ui,dst):
                barrier.wait(); tm.handle_chat_command(dst.my_name,src,ui)
            t1=threading.Thread(target=open_chat,args=(a,ua,b)); t2=threading.Thread(target=open_chat,args=(b,ub,a))
            t1.start();t2.start();t1.join(3);t2.join(3)
            def same_connection():
                x=a.get_chat_conn(self.key(b)); y=b.get_chat_conn(self.key(a))
                if not x or not y:return False
                try:return x.getsockname()==y.getpeername() and y.getsockname()==x.getpeername()
                except OSError:return False
            self.assertTrue(wait_for(same_connection))
            tm.handle_chat_command("B",a,ua); tm.handle_chat_command("A",b,ub)
            tm.handle_send_text("from A",a,ua);tm.handle_send_text("from B",b,ub)
            self.assertTrue(wait_for(lambda:ua.contains("from B") and ub.contains("from A")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
