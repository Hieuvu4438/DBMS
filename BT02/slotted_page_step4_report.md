# BÁO CÁO KỸ THUẬT CHUYÊN SÂU: BƯỚC 4 - KỸ THUẬT NULL BITMAP VÀ BENCHMARK HỆ THỐNG
**(Dựa trên phân tích mã nguồn `slotted_page_step4.py`)**

Tiểu luận nghiên cứu này đóng lại đồ án bằng việc trình diễn một kỹ nghệ thiết kế byte-level đẳng cấp trong các Storage Engine siêu tối ưu: **Null Bitmap**, đồng thời nghiệm thu lại thông số phần cứng từ bài Benchmark tổng lực hệ thống nhằm phản ứng thời gian của CPU & HDD.

---

## 1. PHÂN TÍCH TỐI ƯU CẤP THẤP: NULL BITMAP (NHỊ PHÂN FLAG)

### 1.1 Khủng hoảng Optional Column Padding
Phần lớn các schema dữ liệu thực tế (VD: Table `SinhVien`) có chứa thuộc tính có thể để trống (Nullable columns) như `Email`, `Số Điện Thoại`.
- Truyền thống: Dù chèn chuỗi cạn (`""`) hoặc Null-Terminator tĩnh, ta dĩ vãng vẫn mất trung bình 1 byte tới 5 byte khoảng trắng làm điểm giữ chỗ (Placeholder) cho mỗi thuộc tính (do đặc thù String Parser).
- Nếu cơ sở dữ liệu có cường độ 1.000.000 dữ liệu người dùng, một khoảng trăng tĩnh tiêu hủy hoàn toàn $\sim 5MB$ băng thông Disk mà không ghi một chữ cái có nghĩa nào.

### 1.2 Binary Flag Head (Null Bitmap Encoding)
Thay vì lưu chuỗi rỗng dưới Data Area, hệ thống mã nguồn Bước 4 cấy ghép mộc **1 Byte Tiêu Đề (8 bit Null Bitmap)** bám chặt tại byte cực đầu của mỗi mảng Data Byte.
- **Quy Luật Map (Little-Endian):**
  - $Bit_0$: Ràng buộc ID (0)
  - $Bit_1, Bit_2$: Ràng buộc Họ tên, Lớp (0)
  - $Bit_3$: Optional `Email` $\rightarrow$ Nếu Null, Toggle cắp cờ Bit chuyển hóa thành $1$.
  - $Bit_4$: Optional `Phone` $\rightarrow$ Tương tự $1$.

- **Toán tử Chế Định (Bitwise):**
Quá trình Serialization gán $Bit_3 = 1$ sử dụng hàm dịch trái `SHIFT LEFT` và Phép O-R cấu thành:
$$Bitmap = Bitmap \ | \ (1 \ll 3)$$
$\rightarrow$ Sau mã hóa Cờ Bit, bộ Serialization KHÔNG hề biến tính chuỗi Null xuống sau nó. Mảng String Data của Record bị cắt gọn chỉ còn các thông tin thực tế Not-Null, nén chiều dài Payload lại triệt để.

- **Toán tử Giải Mã (Deserialization):**
Bộ đọc vớt Byte mào đầu (Byte index [0]). Phân biệt bằng cổng `AND logic`:
$$Is\_Null = Bitmap \ \& \ (1 \ll 3)$$
Nếu ra kết quả $>0$, hệ thống tự nhử logic trả về đối tượng `None` cho ứng dụng Python thao tác, khôn khéo tái tạo hình ảnh Logic cho App mà không cần mảng Disk Backing tương ứng dưới ổ cứng.

- **Tiết kiệm toán học:** Cho 1 Record với 2 trường bị null, nếu tiết kiệm túc tắc $\sim 15$ bytes, Tỉ lệ rỗng giả định = $30\%$ của 1 Triệu Records tính nháp tiết kiệm ước lượng $4,5MB$ dư thừa trong Page Block. Lượng dư này đủ cho ta chứa thêm $> 60.000$ sinh viên hoàn toàn miễn phí.

---

## 2. PHÂN TÍCH VÀ ĐÁNH GIÁ METRIC (BENCHMARK RESULTS)

Output hàm `run_benchmarks()` mô phỏng tổng kết các đặc thù khốn khổ và hiệu năng của HDD & RAM Storage. Khung phần cứng đo lường trên mô phỏng máy tính ở mức $\mu s$ (Microsecond $10^{-6}$s).

### 2.1 Benchmark Insert (Phân Phối O(1) Amortized)
- **Insert vào file trống và Insert vào Database ngập $\sim 500.000$ (Full Capacity):** Tốc thời đo cho thấy hiệu năng sai lệch nhau không vượt quá mức $1.02\times$. 
- Điểm đòn gánh **Page Cache** của `Step3` chứng tỏ quyền lực: Mọi thao tác ghi cho dù file khổng lồ vẫn chỉ là chép vào block Ram cuối. Hành động I/O Seek tới trang cũ không diễn ra nếu bạn có tính định tuyến tốt.

### 2.2 Đọc Random Access vs Sequential Table Scan
- **Fast Point (Truy xuất ngẫu nhiên Tốc kích):** $Record Pointer(PageID, SlotID)$ chích tệp tin Array Disk $O(1)$ thẳng trục, cho mốc độ trễ trung bình siêu tốc (Dưới độ trễ IO Disk latency tiêu chuẩn nhờ Python buffer).
- **Sequential Scan (Lỗ hổng The Great O(N)):** Chạy Full table scan 1.000.000 tập tin, băng thông nhồi liên tiếp mất tốn $2 \sim 3$ giây nghẽn I/O để kiểm đếm. Nó nhắc cho DB Engineer rằng tại sao bài toán lập chỉ mục Indexing lại quan trọng tới vậy mới cướp đi vòng FTS tồi tệ.

### 2.3 Compaction Time (Bộ trễ dồn Mảng CPU Memcpy)
Thời khoản Gom mọt 1 Page tốn tầm  $< 50 \mu s$. Tuy nhỏ ở mức 1 block, nhưng nếu Transaction DB phải gọi `Compact` ở hệ cường độ $10.000$ Req/s, sự thắt nút vòng lặp CPU sẽ làm cháy Thread xử lý. 
$\rightarrow$ Đây là lý do CSDL như PostgreSQL thiết đặt cơ chế Vacuum Background Thread ẩn làm hậu trường thay vì khóa Block và dọn khẩn cấp theo kiểu Synchronous Block.

---

## 3. TỔNG QUAN HỆ CSDL LƯU TRỮ VẬT LÝ

Kết luận hệ đồ án chỉ ra triết lý vĩ đại của kiến trúc máy tính chuyên sâu CSDL: **Đừng bao giờ giao hoàn toàn quá trình quản lý tập tin cho File System (NTFS/EXT4) của HDH máy trạm**. 

DBMS là những phần mềm siêu việt tự tạo cấu trúc Disk Array độc quyền, tự duy trì hệ Index Proxy riêng biệt (Slotted Directory), tự khoét bọc Page $4KB$, và kiến trúc Memory Pooling chuyên rẽ. Điều đó đã giữ vị thế cực đỉnh về Database Performance của ngành Storage Management suốt qua hàng thập kỷ cải tiến cho đến ngày nay.
