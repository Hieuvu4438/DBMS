# BÁO CÁO CHUYÊN SÂU: BƯỚC 4 - KỸ THUẬT NULL BITMAP VÀ FINAL BENCHMARK TỔNG THỂ
**(Dựa trên phân tích mã nguồn `slotted_page_step4.py`)**

Bước 4 tích hợp trọn vẹn lý thuyết nền của cấp cơ sở dữ liệu: So sánh và đo lường sự thật qua dòng code Benchmark hệ máy, cũng như tìm cách tiết kiệm cấu trúc phân tử của chuỗi Record Data Header. Vấn nạn được mang ra bàn luân ở đây là: **Dữ liệu có trường giá trị NULL sẽ ăn phí ổ cứng như thế nào nếu thiết kế ngu ngơ?**

---

## 1. KỸ THUẬT TIẾT KIỆM TỐI THƯỢNG: NULL BITMAP

### Mở rộng bài toán Variable-Length Column Option:
Một CSDL thực tế cho phép có những cột dữ liệu có ràng buộc tuỳ chọn, nghĩa là nó **không bắt buộc phải có nạp vào**. (VD: Bảng `Sinh Vien` có cột `Điện Thoại`, `Email`... có thể trống).

Nếu một sinh viên không cung cấp điện thoại/email:
- DBMS có thể lưu Chuỗi Rỗng `""`
- DBMS lưu Data Giả `"N/A"`, `"0"`...

*Cả hai phương pháp trên đều lãng phí nhảm nhí 2 byte tới 6 byte vô dụng nằm trên bộ nhớ vật lý đĩa. Thử nhân lên 10 triệu User thì OS đã "bị cướp" chục Mega Cấu Trúc*.

### Lời Giải Của DBMS Cổ Điển: Dùng 1 Byte Đầu (Null Bitmap)
Thuật toán `slotted_page_step4.py` cài cắm một Header Nhỏ bên trong bản thân Record: **Byte số 0 (8 Bit Mật Mã)**. Nó gắn liền đi đầu mỗi Data Array.
Mỗi cụm bit quản trị một cột:
- Bit 1: Cột 1 (Luôn có) = 0
- Bit 3 (Email): Nếu Email Trống thì Cắm Cờ Bit 3 = `1`. 

**Sự kì diệu của Serialization bằng Cờ Bit Cắm:**
Tại quá trình chép vào Page, vì Email (Bit 3) đã cờ vàng `1`, DBMS không có ghi cộc lệch `""` hoặc ghi thêm cột dữ liệu đó. Cột dữ liệu đó bị xoá sổ không hề tồn tại về mặt chữ ở Data. Khi Deserialization (Gỡ Cọc Byte Đọc Gốc), OS quét Header Null Byte, phát hiện cắm Bit 3, Hệ Thống Auto Phục Hồi nó thành định dạng Logic `"None"` và nhét báo cáo lên giao diện cấp trên. Số byte dư ra cho mỗi bảng NULL được rít cạn một cách đáng sợ (Chẳng bằng 1 byte quản lý đủ 8 trường Null chung trên cột Header).  

---

## 2. PHÂN TÍCH ĐÁNH GIÁ METRIC 

Mã nguồn `run_benchmarks()` mô phỏng tổng kết các đặc thù khốn khổ và hiệu năng của HDD & RAM Storage. Nó tính hiệu năng vi mô đến cực vi mô (Tính bằng µs - Microsecond).

### Benchmark 1: Sức Mượn RAM Trống Rỗng (Insert Overhead)
*   Chèn vô tệp Database Rỗng: Vì có Cache Ram của `step3.py`, nên thao tác chép 100 Tệp File thực tế mất `vài MicroSecond` lẻ siêu rẻ mạt.
*   Chèn vô tệp Database Đã Tràn ~500.000 dòng file: Kết quả tốc hành vẫn mất ... y xì đúc như cũ. Điều này chứng minh thuật toán O(1) Amortize cho `Insert_Page` được thiết kế quá sắc gọn. Có đầy trang đến mức nào, HDD nó vẫn chỉ thao tác ở đoạn Page Cuối Lấy.

### Benchmark 2 & 3: Fast Point Vs Dead FTS (Lỗ hổng của Scan Read)
*   Trong bộ phép đo Đọc Random `Read (Random Access)`: Vì trỏ từ `(Page ID, Offset ID)`, nó lấy con số trỏ nhân khối lượng lên RAM và lấy tệp tin theo ngách Array một cái rụp.
*   Tuy nhiên `Sequential Table Scan`: Vớt toàn bộ khối băng chấn 1 Triệu Records sẽ khiến băng thông ổ cứng nạp toàn bộ vài trăm Megabytes đè trên RAM để kiểm đếm rạch gạch chéo. Nó chứng minh FTS là thảm hoạ của Heap Table và nhắc hệ CSDL B-Tree tại sao lại thống trị ngai vàng.

### Benchmark 4: Đo Thời Gian Gom Mảng Phân Mảnh (Compaction)
Gom cấu hình Page làm 1 là thứ tốn năng lượng CPU (vốn để đi phân mảnh và cấp chép Data Memory - MemCoppy).
Sự chênh lệch giữa tốc độ Compact 1 file 4KB và Không Compact gần như không thấy về độ hoạ. Điều này bởi vì 4KB được CPU hiện đại (Clock Speed 4GHz) cuốn như mây gió. Một số Cường Quốc CSDL vẫn khuyên sử dụng Size 16KB Page để Compaction ở ngưỡng vừa đủ. Nhỏ quá mất công Header nhiều, to quá Compact quá tải.

---

## 3. TÔNG QUAN TẠI SAO NGƯỜI TA SÁNG CHẾ RA NÓ?

Ngâm cứu `slotted_page_step4.py` kết thúc bản Report hệ sinh thái cho thấy:
Người chế tạo CSDL muốn kiểm soát 100% sự sống và chu kỳ cấu trúc bộ nhớ vật lý Cấp File (Thay vì phó thác cho cấp File System NTFs của Window hay Linux Ext4). Nơi mà OS bị cấm xen vào quá trình sắp xếp byte nhị phân của dữ liệu. Đó là cách Hệ Quản Trị CSDL đạt được vị thế Performance siêu đẳng hàng chục năm qua.
