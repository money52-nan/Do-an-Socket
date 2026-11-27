# LAN Chat & File Sharing (Python Console Socket)

Ứng dụng chat và chia sẻ file mạng nội bộ (P2P) sử dụng Socket API gốc của Python (UDP cho khám phá/trạng thái, TCP cho chat và truyền file).

## 1. Cài đặt
Yêu cầu Python 3.9+ và cài đặt thư viện `prompt_toolkit`:
```bash
pip install -r requirements.txt
```

## 2. Cách chạy
### Chạy trên 2+ máy cùng mạng LAN/Wi-Fi
```bash
# Máy 1
python lanchat.py --name Quan --port 5000

# Máy 2
python lanchat.py --name Minh --port 6000
```
*Lưu ý:* Cho phép Python đi qua Windows Firewall (Private/Public network) để nhận được gói UDP broadcast cổng 9999.

### Chạy thử nhiều phiên bản trên 1 máy (offline)
```bash
python lanchat.py --name Quan --port 5001 --local
python lanchat.py --name Minh --port 5002 --local
```

## 3. Bộ lệnh hỗ trợ
- `/list` — Xem danh sách peer đang online
- `/chat <tên|số>` — Mở hoặc chuyển cuộc trò chuyện TCP
- `<văn bản>` — Gửi tin nhắn tới đối tác hiện tại
- `/send <đường_dẫn_file>` — Gửi file (nhị phân/văn bản) tới đối tác hiện tại
- `/leave` — Đóng cuộc trò chuyện hiện tại
- `/status <online|away>` — Đổi trạng thái hiện diện
- `/help` — Xem hướng dẫn lệnh
- `/quit` — Thoát chương trình
