# BÁO CÁO CHUYÊN SÂU: KIẾN TRÚC VÀ CƠ CHẾ HOẠT ĐỘNG SLOTTED PAGE
**(Dựa trên phân tích mã nguồn `slotted_page.py`)**

Tài liệu này cung cấp bản phân tích chuyên sâu về một trong những kỹ thuật nền tảng quan trọng nhất trong thiết kế Storage Engine của Hệ quản trị CSDL (DBMS): **Slotted Page Architecture** (Kiến trúc Trang Phân Khe).

Mã nguồn `slotted_page.py` mô phỏng chính xác cách dữ liệu được sắp xếp vật lý bên trong các CSDL chuyên nghiệp như PostgreSQL (với Heap Page Tuple Format), SQLite, hoặc SQL Server.

---

## 1. BÀI TOÁN CỐT LÕI MÀ "SLOTTED PAGE" GIẢI QUYẾT

Trong DBMS, bộ nhớ máy tính hoặc ổ đĩa được chia thành các khối có kích thước cố định gọi là **Page** (thường là 4KB, 8KB hoặc 16KB). Việc ghi chép và đọc đĩa phụ thuộc vào các Page này chứ không truy xuất từng byte lẻ. 

Vấn đề xuất hiện khi lưu trữ các dòng dữ liệu (records) có **độ dài biến thiên (Variable-length records)** (ví dụ trường `VARCHAR` trong SQL):
- Một sinh viên có tên dài 10 ký tự, sinh viên khác có tên dài 50 ký tự.
- Nếu kìm cứng kích thước mỗi bản ghi giống nhau (Fixed-length) → Sẽ gây lãng phí ổ đĩa (Padding khoảng trắng thừa thãi).
- Nếu ghi nối tiếp nhau kiểu chuỗi biến thiên → Khi xóa một dòng dữ liệu, ta để lại "lỗ hổng" (fragmentation). Rất khó để tái sử dụng chỗ trống đó hoặc phải "dời" toàn bộ các dòng khác → Chi phí xử lý quá chậm.

**Giải pháp:** Slotted Page tách ranh giới lưu trữ làm hai phần: Một cấu trúc MỤC LỤC nằm ở đỉnh và VÙNG DỮ LIỆU nằm ở đáy. Cả 2 cùng trượt tiến vào khoảng không ở giữa.

---

## 2. BỐ CỤC KHÔNG GIAN BỘ NHỚ CỦA PAGE MÔ PHỎNG

Đoạn code định nghĩa biến `PAGE_SIZE = 4096` bytes. Bố cục vật lý của 4096 byte này như sau:

```text
Địa chỉ Offset 0
┌─────────────────────────────────────────────────────────────┐
│                   PAGE HEADER (12 Bytes)                    │
│ [ Page ID (4B) | Slot Count (2B) | Free Space Ptr (2B)      │
│                | Reserved (4B) ]                            │
├─────────────────────────────────────────────────────────────┤ Địa chỉ Offset 12
│            SLOT DIRECTORY (Mục lục trỏ gián tiếp)           │
│                    (Phát triển đi xuống ↓)                  │
│ [ Offset(2B) | Length(2B) ]  [ Offset(2B) | Length(2B) ]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│             FREE SPACE (Khoảng trống điểm giao)             │
│                                                             │
├─────────────────────────────────────────────────────────────┤ <- Free Space Pointer (Biến động)
│                DATA AREA (Vùng dữ liệu thực tế)             │
│                   (Phát triển đi ngược lên ↑)               │
│ [ Dữ liệu Record N ] [ Dữ liệu Record N-1 ] ... [ Record 0 ]│
└─────────────────────────────────────────────────────────────┘ Địa chỉ Offset 4095
```

Như bạn có thể thấy, **Dữ liệu được nạp vào từ đáy trang (đẩy ngược lên), trong khi index được đẩy từ trên đỉnh hạ xuống**. Khoảng rỗng ở giữa là bộ nhớ có thể tái dụng. Khi 2 vùng trên-dưới chạm nhau, Page được tính là Full.

---

## 3. PHÂN TÍCH SÂU CÁC KHỐI CODE QUAN TRỌNG

### 3.1. Cấu trúc Page Header (Hàm `_write_header` & `_read_header`)
Header tốn chính xác 12 bytes. Để xử lý cấu trúc kiểu byte chuẩn mà máy tính dễ đọc-ghi vào file nhị phân, tác giả dùng module `struct` của Python với định dạng ngàm `<IHHI` (Little-Endian):
*   `I` (Unsigned Int - 4 Bytes) - **Page ID**: Định danh ID để DBMS nhận diện Trang này.
*   `H` (Unsigned Short - 2 Bytes) - **Slot Count**: Tổng số lượng bản ghi có mặt trong trang.
*   `H` (Unsigned Short - 2 Bytes) - **Free Space Pointer**: Con trỏ quan trọng nhất. Nó đánh dấu "nóc" của phần dữ liệu đang chất đống ở dưới đáy. Khi chưa có dữ liệu nào `free_space_ptr = 4096`. Khi có cục data dài 100 byte được nhét xuống đáy, biến này được cập nhật `free_space_ptr = 3996`.
*   `I` (Unsigned Int - 4 Bytes) - **Reserved**: Để dành nâng cấp (thường dùng lưu Log Sequence Number trong Transaction/Recovery system thực tế).

### 3.2. Thuật toán Chèn dữ liệu (Hàm `insert_record`)
Khi hệ thống có cục bytes nhị phân độ dài biến thiên (do Hàm Serialization xử lý), quá trình Insert chạy qua các bước:
1.  **Tính ranh giới trên (Của Directory):** `slot_dir_end = 12 + (slot_count * 4)`. Xác định điểm tận cùng của mục lục. Trong đó 12 là độ lớn header, mỗi slot dài 4 byte.
2.  **Tính ranh giới dưới (Của Data):** `new_record_offset = free_space_ptr - record_len`. Do đẩy dữ liệu từ dưới lên, ta tính "ngôi nhà mới" bằng cách khoét thêm vào Free Space.
3.  **Kiểm soát tràn bộ nhớ (Overflow Check):**  Nếu `new_slot_dir_end > new_record_offset`, có nghĩa hai thế lực trên-dưới đã giao nhau. Code thực hiện rớt ngoại lệ `ValueError("Page đã đầy")`.
4.  **Chép byte:** Thực thi `self.data[new_record_offset : new_record_offset + record_len] = data_bytes`.
5.  **Ghi vào Slot Directory:** Bọc 1 cục 4 byte bằng lệnh `struct.pack_into('<HH', ...)` gồm `(new_record_offset, record_len)`. Đây là thông tin giúp DBMS định vị sau này.
6.  **Cập nhật cấu trúc:** Tăng bộ biến cục bộ (cộng slot, nới free_space_ptr).

### 3.3. Phương pháp Indirection & Đọc Dữ Liệu (Hàm `read_record`)
Đây là Tinh hoa của Slotted Page. 
*   **Hệ thống bên ngoài không bao giờ truy xuất thẳng offset bộ nhớ vật lý**
*   Khi cần truy xuất bản ghi thứ 3, DBMS dùng toạ độ `Slot #3`. Toạ độ này gọi là **Record Pointer (Page ID = X, Slot ID = 3)**.
*   Hàm `read_record(3)` đi tới đỉnh trang `(12 + 3 * 4)` đọc ra thông số `(Offset, Length)`.
*   Dựa vào con số đó chạy ra sau chót trang móc đúng cục Data.

#### Tại sao lại "cồng kềnh" như vậy?
Bởi vì trong tương lai (ở các bài tập mở rộng), DBMS sẽ có tính năng "Dồn mảng - Compact Defragment". Nghĩa là ta xóa 1 sinh viên, để lại lỗ hổng, máy tính sẽ dịch bạt các dòng ở dưới đè lên mảng rỗng để gom Free Space về 1 mối. 
Việc này làm thay đổi `Offset Vật Lý` của mọi Record. VỚI HỆ THỐNG SLOT, DBMS CHỈ CẦN cập nhật Offset mới vào đúng Slot #3 tương ứng. Bảng mục lục Index (như B-Tree) bên ngoài trang KHÔNG HỀ BIẾT điều đó xảy ra vì nó đang tham chiếu đến `Slot #3` - thứ vốn không thay đổi. Tránh triệt để thảm hoạ Dangling Pointer (Con trỏ mồ côi lạc lối).

---

## 4. KẾT LUẬN VỀ KIẾN TRÚC

Mã nguồn `slotted_page.py` diễn giải một nguyên lý kinh điển nhưng tối ưu của Khoa học máy tính cấu trúc cấp thấp:
1.  **Tiết kiệm hoàn hảo:** Variable-length cho phép text dài 5 byte hay 500 byte đều nằm khít nhau, không chèn byte thừa (Padding Zeroes).
2.  **Khối Block duy nhất (4KB Sector-friendly):** Quản lý đóng gói tất cả metadata, mục lục và dữ liệu vào duy nhất 1 mảng bytes. Khi cần có thể dùng hàm `save_to_bin` kết xuất xả file thẳng vào ổ cứng cực lẹ không dính phân mảnh File System OS. Tốc độ I/O nhanh hơn nhiều lần so với ghi rời rạc.

Mô hình này là ví dụ xuất sắc về thiết kế Phân Lớp Lô Gíc (cơ chế Indirection Array). Sự đầu tư và comment kịch bản của tác giả khiến code đóng vai trò như một giáo trình thu nhỏ minh hoạ hoàn thiện Storage Management của bộ môn HQT Cơ Sở Dữ Liệu.
