# Checklist trước khi demo – Vai B

Nguồn: LAN_Chat_Socket_Project.docx.pdf (mục 3.3–5.3, 7–8); Demo_Socket.docx.pdf (mục 1.3–1.4, 3, 5.1–5.3).
Đánh dấu sau khi kiểm tra trên bản sẽ nộp, không dùng kết quả Linux thay cho kết quả macOS/LAN thật.

## 1. Code và tích hợp
- [ ] Sao lưu mã gốc và tạo nhánh feat/tcp-chat-file.
- [ ] Nhóm trưởng duyệt thay đổi config.py, state.py, protocol.py.
- [ ] CHAT| tắt mặc định; nếu bật, thống nhất tất cả peer và cập nhật đặc tả.
- [ ] Giữ API cho Vai A/C; test discovery.py, ui.py, lanchat.py sau merge.
- [ ] Không đưa demo_fault.py, --slow hoặc test harness thành chức năng production.
- [ ] Mỗi instance test trên cùng máy có TCP port và thư mục downloads riêng.
- [ ] Chạy python3 -m unittest -v test_automatic trên macOS.

## 2. Các test chức năng
- [ ] Chat hai chiều và tái sử dụng kết nối.
- [ ] Tiếng Việt, emoji, ký tự |, nhiều frame liên tiếp.
- [ ] Ba peer: đếm 1, 2 unread và chuyển chat đọc đủ nội dung.
- [ ] Chat và truyền file đồng thời; hai chiều gửi file cùng lúc.
- [ ] TXT/PDF/JPG/ZIP, file 0 byte, tên có dấu cách, tên trùng.
- [ ] So sánh SHA-256 trước/sau; mở thử file nhận.
- [ ] /leave, /quit, peer đóng ngang, peer không còn online.
- [ ] File không tồn tại, lệnh sai, gói rác, kích thước âm.
- [ ] Ngắt kết nối khi file chưa nhận đủ; file .part bị xóa.
- [ ] Test mất Wi-Fi thật và xác minh timeout/cleanup.
- [ ] Kiểm tra giữ nguyên dòng đang gõ với UI thật của Vai C.

## 3. Thiết bị, demo và Wireshark
- [ ] Hai máy thật cùng LAN, IP thật, kiểm tra firewall và quyền Local Network nếu macOS yêu cầu.
- [ ] Chạy ba peer trên hai máy (hai instance trên một máy), không dùng loopback để kết nối giữa máy.
- [ ] Wireshark cài đặt và có quyền ChmodBPF.
- [ ] Bắt đúng giao diện Wi-Fi/Ethernet (lo0 chỉ cho local test).
- [ ] Ảnh UDP HELLO (Vai A); TCP SYN/SYN-ACK/ACK (Vai B).
- [ ] Ảnh Follow TCP Stream hiển thị HI/MSG, byte length.
- [ ] Ảnh stream chat và stream file có tcp.stream khác nhau.
- [ ] Ảnh BYE/FIN và RST nếu thực sự bắt được RST.
- [ ] File .pcapng lưu sẵn, ảnh đã chú thích, chỉ dùng dữ liệu demo.
- [ ] Có sẵn file demo lớn, checksum, file PDF/ảnh nhỏ.
- [ ] Có phương án lỗi giả lập xác định và phương án offline luyện tập.
- [ ] Tập demo cả nhóm trong 10 phút; nếu Vai B riêng 10 phút, dùng kịch bản riêng.

## 4. Báo cáo và nộp
- [ ] Sơ đồ kiến trúc, mô hình thread/lock, đặc tả giao thức.
- [ ] Bảng test: mong đợi, thực tế, PASS/FAIL, môi trường.
- [ ] Nêu rõ hạn chế: chưa có ACK lưu file, không mã hóa, không resume, timeout là inactivity.
- [ ] Minh chứng Wireshark chụp trên hai máy thật, không dùng ảnh giả.
- [ ] README hướng dẫn cài, chạy, test 1 máy và LAN thật.
- [ ] Ghi lại link lịch sử sử dụng AI theo yêu cầu nhóm trưởng/giảng viên.
- [ ] Xóa __pycache__, .part, file demo lớn, thông tin cá nhân trước khi đóng gói.
- [ ] Mọi thành viên giải thích được TCP/UDP, framing, thread, lock, socket file riêng.
