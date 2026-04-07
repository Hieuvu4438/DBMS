# BÁO CÁO CHUYÊN SÂU: BƯỚC 3 - QUẢN LÝ HEAP FILE VÀ NẠP DỮ LIỆU ĐẠI TRÀ (BULK LOAD)
**(Dựa trên phân tích mã nguồn `slotted_page_step3.py`)**

Sau khi đã tạo được lõi quản lý một Page đơn rẻ rách (4KB), `slotted_page_step3.py` giải quyết bài toán lớn hơn rất nhiều: **"Làm sao kiểm soát 500,000 tới Hàng Triệu Page kết hợp thành một file Database hoàn chỉnh?"**. Kiến trúc Cấu trúc File đơn giản nhất được sử dụng ở đây mang tên là **Heap File**.

---

## 1. MÔ BÌNH HEAP FILE QUẢN LÝ (HEAP FILE MANAGER)

*Heap File* là định dạng lưu vứt mọi thứ vào cơ sở dữ liệu khi hệ thống chưa được đánh chỉ mục. 
Bản chất của `HeapFileManager`: Chèn mọi thứ tuần tự. Khi đủ sức chứa nó ghi tiếp file và cấp Trang kế tiếp.

### Cấu trúc mô phỏng trên đĩa cứng:
Kho dữ liệu được lưu dưới dạng binary file (`database.db`).
```text
Offset 0         Offset 4096      Offset 8192      Offset ...
┌────────────────┬────────────────┬────────────────┬─────────┐
│     Page 0     │     Page 1     │     Page 2     │  ...    │
│    (4096 B)    │    (4096 B)    │    (4096 B)    │         │
└────────────────┴────────────────┴────────────────┴─────────┘
```
Bởi vì mỗi trang luôn dài chuẩn 4096 byte, người ta dễ dàng dùng phép nhân để "nhảy" đến một trang bất kỳ. 
Khi CSDL thông báo `FETCH PAGE = 2`, Hệ thống I/O ổ cứng sẽ xích tới độ dài con trỏ chép `2 * 4096 = 8192`. Tốc độ nhảy nhanh như chớp mồi (O(1)). Cả triệu file kết thúc nối tiếp nhau dính lấp.

---

## 2. KỸ THUẬT BUFFER TRONG RAM VÀ QUẢN TRỊ CACHE I/O CƠ BẢN

### Vụ nổ chi phí thao tác Disk I/O (The Threat Of Disk I/O Cost)
Khi cắm dữ liệu liên tục 500.000 records, nếu cứ dồn Insert mỗi lệnh là OS lại chép `4096` bytes đập dính vào đĩa, máy tính của bạn sẽ bốc cháy vì ổ cứng kiệt sức. 

### Page Cache (Bộ Nhớ Đệm) Giải Cứu
Mã nguồn khắc phục bằng cách thiết kế hệ thống giữ `_cached_page`. 
- Nó cất giữ toàn bộ Page ở mức RAM. Trạng thái dính nháp được ghi là `_cached_dirty = True`
- Ghi đè vào cùng cục diện cho đến khi Full (Ví dụ được khoảng 60 records).
- Khi đã Full nó tiến hành vắt một giọt lệnh xả (`flush_cache`) để viết khối đá RAM đó xuống File Base vật lý một lần.

Như vậy thay vì đập I/O 60 lệnh Write lên mặt đĩa, Hệ quản trị chỉ làm gánh nặng nhấc ghi cho ổ SSD đúng "MỘT CHẠM". 

---

## 3. KIẾN TRÚC STREAMING NẠP DATA (BULK LOAD GENERATOR)

File `slotted_page_step3.py` đi kèm theo 1 hệ phễu làm File giả (Generate CSV) tạo ra danh sách 500,000 Sinh viên theo Format Variable-Length. Câu hỏi lớn là: OS có phải mở bộ file khổng lồ chục MegaByte đọng vào RAM?

*   Câu trả lời là **KHÔNG**.
*   Khung phần Bulk Load sử dụng cách thức `Iterator \ Generator`. CSV Data được hút từng hàng `csv.reader() -> next() -> read()`. Lôi ra RAM để Deserialize xong xả vào Page Buffer. Page Buffer xả vào Ổ Cứng bằng Streaming.
*   **Chi phí cực thấp**: Bất kể bạn đút 50.000 hoặc đút tới 50 Triệu phần tử, Ram Load không hề bão hoà quá số 5 Megabyte. (Độ phức tạp tiêu tốn Storage không gian RAM: `O(1) Constant`).

---

## 4. BENCHMARK CƠ BẢN - YẾU ĐIỂM CỦA HEAP FILE QUÉT FTS

Hàm benchmark đo lường chức năng chèn và Get ở Step 3 có các ý nghĩa quan trọng sau:
1.  Nhờ Page cache mà hiệu năng (Insert Benchmark) được đẩy lên hàng trăm nghìn Rows một giây. Ghi ổ mượt mà nhịp đều. 
2.  Hiệu năng Get (Random Access theo chỉ mục gốc): Nếu truy xuất điểm `(PageID, SlotID)` thì I/O nhảy vọt tức thời xuống trang đó, tốc độ xấp xỉ tính theo phần của phần nghìn MicroSecond (µs).
3.  **Tử huyệt cực kỳ của Heap Table:** Đạt tên CSDL `Full Table Scan` (Quét từ đầu chí cuối).
    Để đếm thử xem có bao nhiêu "Nguyễn Văn Đạt", Hệ quản trị không có quyền ưu tiên, nó bắt buộc phải nhảy từng Page (từ 0...10.000) và dò quét qua từ điểm đầu cho tới chân. Đây là vấn nạn khét tiếng được gọi nôm na cho sinh viên CSDL: "**Sự thiếu thốn Index**". Bài toán này minh chứng dập khuôn rằng tại sao Hệ Thống cần thiết kế Index `B-Tree` để tìm kiếm không gian cho Heap File.
