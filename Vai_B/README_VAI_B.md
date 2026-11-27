# Vai B – bộ kiểm thử độc lập và bản cải tiến

Không ghi đè file gốc. Sao lưu và xem CHANGES.patch trước khi ghép. Đây không phải ứng dụng hoàn chỉnh của nhóm: không có UDP discovery thật, lanchat.py hay UI chính thức của Vai C. Các peer trong test_vai_b.py được thêm thủ công.

## Cài và chạy test

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-demo.txt
python3 -m unittest -v test_automatic
```

Bộ unittest chỉ cần thư viện chuẩn, không cần prompt_toolkit. Demo tương tác dùng prompt_toolkit nếu đã cài; nếu không, fallback input() không bảo đảm giữ chữ đang gõ.

## Ba terminal trên một máy

```bash
python3 test_vai_b.py Quan 5001 --peer Minh=127.0.0.1:5002 --peer Lan=127.0.0.1:5003 --downloads downloads_quan --slow 0.02
python3 test_vai_b.py Minh 5002 --peer Quan=127.0.0.1:5001 --peer Lan=127.0.0.1:5003 --downloads downloads_minh --slow 0.02
python3 test_vai_b.py Lan 5003 --peer Quan=127.0.0.1:5001 --peer Minh=127.0.0.1:5002 --downloads downloads_lan
```

Mỗi lệnh chạy ở một terminal. Tạo file demo: `python3 -c 'import os; open("demo32.bin","wb").write(os.urandom(32*1024*1024))'`. Dùng `/list`, `/chat Minh`, gõ text, `/send demo32.bin`, `/leave`, `/quit`. --slow chỉ để minh họa demo, không phải giới hạn tốc độ production.

## Hai máy thật

Ví dụ máy 1 IP 192.168.1.10, máy 2 IP 192.168.1.20 (thay bằng IP thực). Quan và Lan trên máy 1, Minh trên máy 2. Từng lệnh ở terminal riêng:

```bash
python3 test_vai_b.py Quan 5001 --peer Minh=192.168.1.20:5002 --downloads downloads_quan --slow 0.02
python3 test_vai_b.py Lan 5003 --peer Minh=192.168.1.20:5002 --downloads downloads_lan
python3 test_vai_b.py Minh 5002 --peer Quan=192.168.1.10:5001 --peer Lan=192.168.1.10:5003 --downloads downloads_minh --slow 0.02
```

Hai máy cần cùng LAN có thể kết nối trực tiếp. Chỉ dùng dữ liệu demo, trên mạng tin cậy.

## Demo lỗi xác định

Ở terminal khác, với peer đang chạy, chạy một trong các lệnh (thay IP/port phù hợp):

```bash
python3 demo_fault.py 127.0.0.1 5002 --mode partial
python3 demo_fault.py 127.0.0.1 5002 --mode stall
python3 demo_fault.py 127.0.0.1 5002 --mode bad-header
python3 demo_fault.py 127.0.0.1 5002 --mode reset
```

partial: khai báo 1 MiB, gửi 64 KiB rồi đóng; stall: gửi 64 KiB rồi đứng yên quá 10 giây; bad-header: không gửi HI hợp lệ; reset: tạo kết nối thử, gửi MSG rồi yêu cầu abortive close qua SO_LINGER. Xác minh packet trace thay vì giả định luôn có RST. Đây là các test trên ứng dụng của chính nhóm; không thay cho test mất Wi-Fi thật.

## Tích hợp

Các hàm được Vai C gọi giữ tên và tham số chính; handle_send_file_command trả thêm đối tượng thread (caller cũ có thể bỏ qua). TCPAcceptor có ready và error. Dùng API state cũ cho discovery và UI; không ghi trực tiếp dict nếu không có lock.

CHAT| là tùy chọn mở rộng, mặc định tắt. Cả hai đầu phải hỗ trợ nếu bật --explicit-chat ở bản demo; chỉ cập nhật config.EXPLICIT_CHAT_OPEN khi nhóm đã thống nhất. Giao thức gốc không xác định loại kết nối trước frame MSG/FILE/BYE, nên không bảo đảm xử lý trọn vẹn hai lần mở đồng thời trước tin đầu tiên. Khi mở đồng thời với CHAT|, bộ test xác minh hai đầu hội tụ về một kết nối; không cam kết tin gửi đúng ngay trong khoảng chuyển tiếp.

Giới hạn: sender không nhận ACK lưu file; 100% là số byte đã gửi cho socket. So SHA-256 và mở file ở phía nhận để xác minh. Timeout file 10s là inactivity, không phải tổng thời gian truyền. Lock tên file bảo vệ trong một process; mỗi instance phải có thư mục riêng. Không mã hóa, không xác thực peer, không quota file/disk, không resume; chỉ dùng LAN tin cậy. Dừng Wi-Fi khi chat idle không bảo đảm phát hiện ngay; cần phối hợp UDP discovery và cơ chế heartbeat nếu yêu cầu. Đóng cứng tiến trình nhận có thể để lại .part vì tiến trình không còn chạy cleanup. Bản này đã chạy unit/integration loopback trong Linux; cần test macOS, LAN và UI chính thức trước khi nộp.
