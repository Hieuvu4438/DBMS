# BÁO CÁO KỸ THUẬT CHUYÊN SÂU: BƯỚC 3 - QUẢN LÝ HEAP FILE VÀ DATA STREAMING
**(Dựa trên phân tích mã nguồn `slotted_page_step3.py`)**

Hệ thống bước 3 nâng tầm tư duy lưu trữ từ việc quản trị cục diện 1 Block $4KB$ rời rạc tới việc vận hành một kho liên khối khổng lồ (Dataset $500.000+$ records) thông qua kiến trúc gốc nguyên sinh của Storage: **Heap File Manager**.

---

## 1. MÔ HÌNH VẬT LÝ HEAP FILE MANAGER

### 1.1 Cấu trúc mảng Page tuần tự
"Heap File" (Tập tin đống) là kiến trúc lưu dữ liệu nguyên thủy khi phân tích DBMS chưa có chỉ mục phức tạp. Trong thuật toán mô phỏng này, hàng ngàn đối tượng `SlottedPage` sẽ được xả tuần tự, san sát nhau thành một File Nhị Phân dung lượng khổng lồ.

```text
Offset đĩa: 0        4096      8192      12288
            ┌────────┬────────┬────────┬────────┬───...
            │ Page 0 │ Page 1 │ Page 2 │ Page 3 │
            │ (4KB)  │ (4KB)  │ (4KB)  │ (4KB)  │
            └────────┴────────┴────────┴────────┴───...
```
- **Phương trình Địa chỉ ổ cứng Sector O(1):**
Khi CSDL nhận Tuple Record Pointer báo $PageID = X$, hệ thống bỏ qua việc quét tệp file theo kiểu con người (File stream), ngắt thẳng bộ xử lý I/O truy hồi vào toạ độ vật lý phần cứng tuyệt đối:
$$Disk\_Offset = PageID \times PAGE\_SIZE = X \times 4096$$

### 1.2 Bất Toán Insert Tuyến Tính Amortized O(1)
Luồng thao tác Thêm Bản ghi Của Heap khá bạo ngược:
1. Đọc trang vương vấn cuối cùng (Biết trước nhờ lưu metadata số Page của Header).
2. Xả Payload data vào. Nếu thừa sức chứa, gọi Routine Slot Insert ở (Bước 1/2) $\rightarrow O(1)$.
3. Nếu hết Contiguous, chạy Compact (Bước 2).
4. Nếu Compact rồi vẫn hết mảng vùng rỗng biên $\rightarrow$ Kêu gọi HĐH cấp 4096 Byte mới (Tạo $Page_{last+1}$) $\rightarrow$ Ghi tiếp nhồi xuống.

---

## 2. KIẾN TRÚC BỘ NHỚ TRUNG GIAN (PAGE CACHE) 

Nếu mỗi một lệnh ghi sinh viên `[Thêm data] -> Cất xuống File.db -> Hoàn tất`, việc nhập $500,000$ bản ghi sẽ khiến ổ đĩa kêu thét vì $500,000$ lần gọi Write IOPS vật lý.
**Kỹ nghệ Cache Phân Đoạn (Buffer pool mini):**
- Biến cấp Lớp `_cached_page` và biến cờ Dirty-bit `_cached_dirty` đóng vai trò là một thanh Ram đệm RAM $4KB$.
- Một Page nhận trung bình $\sim 60$ Records trước khi cạn $Ptr_{free}$. Khi thuật toán Generator Streaming chép vòng lặp nhập tin, nó đổ nhồi $60$ sinh viên vào chung một Memory Object cấp Lớp, và chỉ cắm `Dirty = True`.
- **Ghi đĩa Một Chạm:** Chỉ khi Page bị đầy, vòng lặp sinh Page mới ở Cấp Heap chèn vào ổ cứng sẽ rớt một lệnh `.flush_cache` (Vứt đá đệm xuống đĩa). 
$\rightarrow$ Lượng Write I/O giảm từ $500.000$ lần xuống còn vỏn vẹn chỉ $\approx 8.500$ lệnh (tiết kiệm sốc $98\%$ băng thông I/O hệ thống OS).

---

## 3. STREAMING GENERATOR LOGIC VÀ KIỂM SOÁT TÀI NGUYÊN BẤT BIẾN

File mã nguồn đi kèm `generate_dataset` tự sinh $500.000$ dòng CSV tốn $\sim 35MB$. Thuật toán sau chép Bulk Load nó thể hiện cách thiết kế phần mềm Tối Ưu Bộ Nhớ:

**Cơ chế Yield / Streaming Read:**
- File lớn đến đâu, hệ thống Python hàm `csv.reader` chỉ hút ra từng hàng dữ liệu $O(1)$.
- Serialization hàm chuyển thành dãy Byte nhị phân ngắn (VD: 54 byte). Chuyển rớt vào Cache Của Heap O(1).
- Ram OS System Peak được bảo thủ ổn định $\sim 5 MB$ cực kỳ cố định. (Không phụ thuộc vào việc tập tin $50.000$ dòng hay cực hạn $50.000.000$ dòng).

---

## 4. CHI PHÍ BIG-O: TỬ HUYỆT FULL TABLE SCAN (FTS)

Trực giao thông qua Hàm Test của hệ thống, Báo cáo cho kết luận FTS của Heap:
- Thao tác đính tọa độ $PageID, SlotID$ qua hàm `get_record()` có thời gian phản hồi ở mức nhỏ cỡ Nano/Micro second. Vì CPU nhảy cực xa bằng công thức tính Offset Disk $O(1)$.
- Toán cục đếm Full Scan Table `scan_all_records` Generator. Vì trong cấu trúc đống chưa định hình băm chỉ mục (Indexless), phép đếm "Tìm sinh viên tên Đạt" sẽ gò phần mềm chạy tuần tự qua các luồng offset từ `Page=0` đâm nát cạn đến `Page=End`, giải mã từng Byte `Serialization`. Mặc dù Python sử dụng Generator yield siêu việt, việc càn quét ngàn trăm MB bộ nhớ vẫn chứng minh cho sự khao khát ra đời của **Thuật toán cây B-Tree Indexing** để thoát kiếp FTS.
