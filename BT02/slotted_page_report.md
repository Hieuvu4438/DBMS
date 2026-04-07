# BÁO CÁO KỸ THUẬT CHUYÊN SÂU: KIẾN TRÚC VÀ CƠ CHẾ HOẠT ĐỘNG SLOTTED PAGE (BƯỚC 1)
**(Dựa trên phân tích mã nguồn `slotted_page.py`)**

Tài liệu này cung cấp bản phân tích kỹ thuật ở mức độ byte (byte-level) về một trong những kỹ thuật nền tảng quan trọng nhất trong thiết kế Storage Engine của Hệ quản trị CSDL (DBMS): **Slotted Page Architecture** (Kiến trúc Trang Phân Khe).

Mã nguồn `slotted_page.py` mô phỏng chính xác cách dữ liệu được sắp xếp vật lý bên trong các CSDL chuyên nghiệp như PostgreSQL (với Heap Page Tuple Format), SQLite, hoặc SQL Server.

---

## 1. PHÂN TÍCH BÀI TOÁN LƯU TRỮ VÀ GIẢI PHÁP

### 1.1 Vấn đề của cấu trúc tĩnh (Fixed-length Array)
Trong DBMS, ổ cứng được phân vùng thành các khối (Block) gọi là **Page** với kích thước cố định (thực tiễn thường là $4KB$, $8KB$ hay $16KB$). Mã nguồn định nghĩa Hằng số `PAGE_SIZE = 4096` bytes. 

Nếu hệ thống lưu trữ theo cấu trúc mảng một chiều thông thường (kích thước cố định), với tập dữ liệu các bản ghi có chiều dài biến thiên (Variable-length records - ví dụ: `VARCHAR`), hệ thống sẽ gặp các vấn đề nghiêm trọng:
- **Internal Fragmentation (Phân mảnh nội):** Nếu CSDL ấn định kích thước một bản ghi là kích thước tối đa của kiểu dữ liệu (vd: $255$ bytes). Khi người dùng nhập tên dài $5$ bytes, nó sẽ dư thừa lãng phí mất $250$ bytes khoảng trắng tĩnh (padding). 
- **External Fragmentation (Phân mảnh ngoại):** Khi chuỗi biến đổi dài ngắn chèn ép nhau, việc xóa một record sẽ tạo ra các khoảng hẹp khó tái sử dụng, việc di dời mọi bản ghi rất tốn kém $O(N)$.

### 1.2 Kiến trúc đối xứng của Slotted Page
Để giải quyết bài toán Variable-length, Slotted Page thiết kế ranh giới lưu trữ phân chia làm hai thái cực hướng vào nhau:
1. **Slot Directory (Mục lục cấu trúc):** Mọc từ đỉnh Page xuống (Top-down).
2. **Data Area (Vùng dữ liệu thô):** Mọc từ đáy Page lên (Bottom-up).

Khoảng không gian ở giữa chính là **Free Space**. Khi hai ranh giới này tiến dần vào nhau và chạm nhau, trang được tính là **Đầy (Full)**.

---

## 2. BỐ CỤC KHÔNG GIAN BỘ NHỚ (MEMORY LAYOUT)

Bố cục vật lý của mảng `bytearray` có dung lượng $4096$ byte được phân chia cụ thể như sau:

```text
Địa chỉ Offset 0
┌─────────────────────────────────────────────────────────────┐
│                   PAGE HEADER (12 Bytes)                    │
│ [ Page ID (4B) | Slot Count (2B) | Free Space Ptr (2B)      │
│                | Reserved (4B) ]                            │
├─────────────────────────────────────────────────────────────┤ Địa chỉ Offset 12
│            SLOT DIRECTORY (Mục lục trỏ gián tiếp)           │
│                    (Phát triển đi xuống ↓)                  │
│ [ Offset₀(2B) | Length₀(2B) ]  [ Offset₁(2B) | Length₁(2B) ]│
├─────────────────────────────────────────────────────────────┤ <-- End_SlotDir
│                                                             │
│             FREE SPACE (Khoảng trống điểm giao)             │
│                                                             │
├─────────────────────────────────────────────────────────────┤ <-- Free Space Pointer
│                DATA AREA (Vùng dữ liệu thực tế)             │
│                   (Phát triển đi ngược lên ↑)               │
│ [ Dữ liệu Record N ] [ Dữ liệu Record N-1 ] ... [ Record 0 ]│
└─────────────────────────────────────────────────────────────┘ Địa chỉ Offset 4095
```

---

## 3. PHÂN TÍCH TOÁN HỌC VÀ THUẬT TOÁN LOGIC

### 3.1. Cấu trúc Page Header 
Header tốn chính xác 12 bytes. Để xử lý cấu trúc kiểu byte chuẩn mà CPU có thể dễ giải mã, DBMS dùng thư viện `struct` với định dạng Little-Endian `<IHHI`:
*   `I` (Unsigned Int - 4 Bytes): **Page ID**. Tham chiếu tuyệt đối số hiệu của trang đĩa.
*   `H` (Unsigned Short - 2 Bytes): **Slot Count** ($N_{slots}$). Tổng số bản ghi tồn tại trong mục lục.
*   `H` (Unsigned Short - 2 Bytes): **Free Space Pointer** ($Ptr_{free}$). Con trỏ cực kỳ quan trọng đánh dấu mũi nhọn của vùng Data Area đang đi dần lên. Khởi tạo đầu tiên $Ptr_{free} = 4096$.
*   `I` (Unsigned Int - 4 Bytes): **Reserved**. Thường dùng lưu *Log Sequence Number* trong Transaction/Recovery system.

### 3.2. Thuật toán Chèn dữ liệu (Insert Routine)

Khi hệ thống chèn một chuỗi Bytes biến thiên, thuật toán được gọi sẽ thi hành các phép định tính toán học:

**Bước 1: Tính toán ranh giới dưới (Của Directory):** 
Xác định độ dài cực đại của chỉ mục hiện tại:
$$End_{SlotDir} = HeaderSize + (N_{slots} \times SlotEntrySize)$$
*(Trong đó, $HeaderSize = 12$, $SlotEntrySize = 4$)*

Khi bản ghi mới chuẩn bị sinh ra mục lục, ranh giới ảo tương lai sẽ trở thành:
$$NewEnd_{SlotDir} = End_{SlotDir} + SlotEntrySize$$

**Bước 2: Tính toán ranh giới trên (Của Data Area):**
Tính "ngôi nhà mới" (Offset) của Payload bằng cách ăn mòn vào Free Space đẩy ngược lên:
$$Offset_{NewRecord} = Ptr_{free} - Length_{Record}$$

**Bước 3: Phương trình Kiểm soát chạm (Collision Check):**
Sức chứa tổng hợp chỉ hợp lệ và không gây tràn nếu và chỉ nếu ranh giới mục lục không "chèn ép" (chạm) trực tiếp vào ranh giới Data.
$$NewEnd_{SlotDir} \le Offset_{NewRecord}$$
Nếu điều kiện sai $\rightarrow$ Trả về Exception `"LỖI] Page đã đầy"`.

**Bước 4: Vật lý hóa xuống Byte:**
- Chép $Length_{Record}$ byte vào vùng tọa độ `data[Offset_{NewRecord} : Offset_{NewRecord} + Length_{Record}]`.
- Đóng gói địa chỉ bằng hàm pack `(Offset_{NewRecord}, Length_{Record})` (tổng cộng 4 byte) và ghi vào chính xác vùng Offset $End_{SlotDir}$ trong Header của Mảng.
- Tăng biến nhấp lưu bộ $N_{slots} = N_{slots} + 1$, ép $Ptr_{free} = Offset_{NewRecord}$.
- Ghi đè cập nhật ngược lại về Header 12 byte vật lý. Chi phí thời gian tiệm cận $O(1)$.

### 3.3 Phương Pháp Indirection (Cơ chế trỏ gián tiếp)
Hàm đọc `read_record(slot_id)` hoạt động như thiết bị tra cứu Mảng Tuyến Tính. Quá trình tính toán tọa độ truy xuất diễn ra như sau:
$$Pos_{Slot} = 12 + slot\_id \times 4$$
Sau đó giải mã $(Offset, Length)$ để nhúng móc chuỗi String thực ở tận đáy Page. Mặc dù mất 2 công đoạn (O(1) Memory Jump), nhưng đây là linh hồn cho khả năng thay đổi bộ nhớ mà sẽ được làm rõ hơn ở chức năng dập phân mảnh ở Bước 2.
