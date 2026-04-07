# BÁO CÁO KỸ THUẬT CHUYÊN SÂU: BƯỚC 2 - QUẢN LÝ XOÁ VÀ DỒN PHÂN MẢNH TRANG
**(Dựa trên phân tích mã nguồn `slotted_page_step2.py`)**

Tiếp nối nền tảng lưu biến thiên (Variable-Length) tại Bước 1, mã nguồn `slotted_page_step2.py` giải quyết lỗ hổng nan giải nhất trong việc quản trị dữ liệu thực tế tại ổ đĩa: **Vấn đề phân mảnh khi thay đổi Dữ liệu**, bằng cách ứng dụng cơ chế **Lazy Deletion** (Xóa mềm) và **Compaction** (Dồn phân mảnh không gian O(N)).

---

## 1. CƠ CHẾ XÓA MỀM (LAZY DELETION)

### 1.1 Khó khăn của "Xóa Cứng" trên không gian Đĩa
Giả sử bản ghi $A$ (dài $800$ bytes) nằm giữa Page. Nếu tiến hành dỡ bỏ ngay lập tức (Hard Deletion), DBMS sẽ phải lấp vào "khoảng trống vật lý" bằng cách xê dịch toàn bộ khối bản ghi ở trên xuống. Nếu thao tác này được thực hiện tức thì trên một ổ cứng từ tính chậm chạp (Disk I/O), độ trễ sẽ khiến DBMS tắc nghẽn vô hạn. Chi phí thời gian sẽ là $O(N)$ trong đó $N$ là lượng dữ liệu phải chép dời.

### 1.2 Giải Pháp Lazy Deletion (Xóa Mềm)
Thuật toán ưu tiên thay đổi phần thẻ mục (Meta-Data) trên đầu trang và bỏ mặc lại khối Storage Payload thực sự.
- **Tiến trình vật lý:** Truy xuất đến `Slot Entry #K` trong *Slot Directory* chạy trong vùng offset: $Pos_{slot} = 12 + K \times 4$
- **Hành động can thiệp toán tử:** Chèn đè giá trị đặc biệt $0xFFFF$ ($65535$) vào vị trí $Offset_{k}$ của mục lục, bảo lưu nguyên $Length_{K}$ gốc. Ghi đè vào mảng MRAM: `_write_slot(slot_id, DELETED_MARKER, length)`.
- **Hệ quả của O(1):** Quá trình mất đúng phân nửa $1 \mu s$, bản ghi "như đã biến mất" trước các API truy vấn của người dùng. 
- **The Fragmentation Tax (Thuế Phân Mảnh):** Vùng payload thực sự ở dưới cùng vẫn chưa được xóa, dẫn tới một "khoảng hổng bộ nhớ" không thể chạm tới xuất hiện, có diện tích bằng $Length_{k}$ (gọi là External Fragmentation). Nếu không gian liền mạch (Contiguous) bị nén quá nhỏ, mặc cho tổng không gian tổng cực kỳ rộng rãi, `Insert` vẫn sẽ thất bại.

---

## 2. QUỸ ĐẠO TOÁN HỌC: CÔNG THỨC KHÔNG GIAN BỘ NHỚ

Thuật toán giờ đây phải giám sát hai thông số không gian độc lập:

1. **Khối lượng Rỗng Tịnh Tiến ($Space_{Contiguous}$):** Là phần trắng xuyên suốt liên tục, tính từ rìa của thẻ định danh Slot tới chóp của Payload Data Area.
   $$Space_{Contiguous} = Ptr_{free} - End_{SlotDir} - SlotSize$$
   *(Khoảng này được dùng cho lệnh Insert gốc)*

2. **Khối lượng Trống Khả Dụng Tổng Thể ($Space_{Total}$):** Là sức chứa "Lý Thuyết" sau khi ép bay mọi rác tàn dư bị xóa (Fragments).
   $$Space_{Total} = Space_{Contiguous} + \sum_{k=0}^{N_{slots}} (Length_k \text{ nếu } Offset_k = 0xFFFF)$$
   *(Hàm Insert kiểm tra nếu $Length_{NewRecord} \le Space_{Total}$ và $> Space_{Contiguous}$ có nghĩa là Page vẫn Đủ sức chứa, nhưng phải chạy Compact!)*

---

## 3. THUẬT TOÁN DEFRAGMENTATION (COMPACTION / DỒN TRANG)

Quá trình `compact_page()` là một sự tái sinh toàn diện bộ nhớ của Page hiện tại mô phỏng dọn ổ cứng.

### 3.1 Quy trình O(N) Array Coalesce
1. **Extraction (Trích xuất các Bản ghi còn Sống):** Duyệt trọn vòng lặp Mảng Slot Directory ($k=0$ đến $slot\_count$). Lưu Payload của các thẻ có $Offset \neq 0xFFFF$ vào một Array Cache đệm tậm thời trong RAM.
2. **Purge (Tẩy uế trang đĩa vật lý):** Quét toàn bộ khối vùng $End_{SlotDir}$ đến giới hạn $4096$ byte về dải $0x00$ theo hệ $XOR$.
3. **Restoration (Trám trần từ đáy lên):** Quy chiếu con trỏ đẩy chéo từ đáy $WritePtr = 4096$. Bóc khối RAM từ Cache.
   Tính lại giới hạn chèn mới cho vòng lặp:
   $$Offset_{new\_i} = WritePtr - Length_{i}$$
   Thả vùng block Bytes vào đúng $Offset_{new\_i}$, sau đó gạt $WritePtr = Offset_{new\_i}$.
4. **Relinking (Sửa đổi Bảng Định Danh O(1)):** Hệ thống chèn giá trị $Offset_{new\_i}$ ngược lại vào vùng Metadata của $Slot\_id$. Các bản ghi Delete thì bị cướp dời thông số vùng nhớ lưu rỗng bằng 0 (`Length_k = 0`).

### 3.2 Hạt nhân Thiết kế: ĐỊNH LUẬT INDIRECTION & CON TRỎ MỒ CÔI
Một trang đĩa không nằm cô lập mà được gắn kết với hàng tỷ nhánh trỏ từ các cấu trúc Cây **B-Tree** hoặc **Khóa ngoại (Foreign Key)**. 
Nếu khi Defragmentation, ta phá hủy số hiệu dòng của Record (Thay $Slot\_id=3$ thành $Slot\_id=1$) để "ngay ngắn", hàng ngàn Cây Index tham chiếu tọa độ ảo cũ đó sẽ rơi vào hội chứng phân ly (**Dangling Pointer**) $\rightarrow$ Ngưng sập hoàn toàn Tín Tâm của Database.

**Sự kì diệu của thiết kế Slotted:**
- Tọa độ BĐS bên ngoài là Tuple `(Page_ID, Slot_ID)`.
- Hàm Compaction đẩy văng vật lý Dòng dữ liệu từ $Offset = 3400$ tuột thẳng xuống $Offset = 3800$, nhưng **$Slot\_ID$ ở mục lục Header không hề biến đổi**. Chỉ có số định danh trỏ bên trong thay thế. Khối bộ nhớ ngoài luồng hoàn toàn "Mù thông tin" về sự dịch chuyển vật lý nhưng luôn tìm được Data nhờ sự đóng đè Proxy Indirection này.
