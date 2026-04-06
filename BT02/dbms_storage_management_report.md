# BÁO CÁO BÀI TẬP LỚN: MÔ PHỎNG STORAGE MANAGEMENT TRONG HỆ QUẢN TRỊ CƠ SỞ DỮ LIỆU
**Chủ đề:** Mô phỏng Variable-Length Records và Slotted Page

---

## Phần 1: Giới thiệu chung (Introduction)

### 1.1 Mục tiêu bài tập
Bài tập thiết kế và xây dựng một phần mềm mô phỏng cơ sở dữ liệu ở tầng lưu trữ vật lý nhằm giúp hiểu rõ cách một Hệ quản trị CSDL (DBMS) quản lý bộ nhớ, ghi chép và trích xuất dữ liệu trên ổ cứng. Hệ thống thử nghiệm sẽ hạn chế sử dụng bộ nhớ RAM và thiết kế xoay quanh kiến trúc hướng khối (block-oriented).

### 1.2 Đối tượng nghiên cứu
Trong báo cáo này, nhóm tập trung nghiên cứu xử lý **Bản ghi độ dài biến đổi (Variable-length records)** bằng cách áp dụng cấu trúc **Trang có khe cắm (Slotted Page)**. Đây là nền tảng quản lý lưu trữ cốt lõi được ứng dụng trong hầu hết các hệ quản trị hiện đại như PostgreSQL, SQLite và MySQL InnoDB.

### 1.3 Công nghệ sử dụng
- **Ngôn ngữ lập trình:** Python.
- **Tiền xử lý nhị phân:** Sử dụng thư viện `struct` để mã hóa và giải mã dữ liệu chuỗi/số học thành các khối bytes nguyên thủy.
- **Dữ liệu thử nghiệm:** Trực tiếp tiến hành Bulk Load trên dataset gồm $1.000.000$ bản ghi sinh viên nhằm kiểm chứng tính bền vững và khả năng đáp ứng lượng truy xuất lớn.

---

## Phần 2: Cơ sở lý thuyết (Theoretical Background)

### 2.1 Vì sao bản ghi độ dài biến đổi lại xuất hiện?
Trong thực tế, dữ liệu vô cùng đa dạng. Ngay cả trong cùng một bảng dữ liệu, một số cột như họ tên (`VARCHAR`), mô tả (`TEXT`), hoặc dữ liệu nhị phân (`BLOB`) có kích thước khác nhau đối với từng hàng.
Đồng thời, sự tồn tại của các giá trị rỗng (`NULL`) làm phức tạp việc phân bổ dung lượng. Nếu sử dụng cách bố trí bản ghi có độ dài cố định (Fixed-length layout) theo kích thước lớn nhất có thể của mỗi cấu trúc, bộ nhớ sẽ đối mặt với tình trạng dư thừa (internal fragmentation) gây lãng phí vô cùng nghiêm trọng. Việc biến đổi cấu hình cho phép bản ghi "co giãn" linh hoạt, nhờ đó tối ưu hóa tối đa dung lượng tệp tin.

### 2.2 Vai trò của cặp $(offset, length)$ trong Slot Directory
Cấu trúc Slotted Page quản lý dữ liệu linh hoạt nhờ một mảng chỉ mục ở đầu trang gọi là **Slot Directory**. Tại đây, với mỗi bản ghi được chèn vào, mảng này ghi lại một mục (slot entry) chứa cặp $(offset, length)$:
- **$offset$:** Độ dời (tính bằng byte) từ điểm bắt đầu của trang (Page Header) đến điểm bắt đầu của bản ghi thực tế nằm trong vùng Data Area.
- **$length$:** Chiều dài vật lý của bản ghi.
Nhờ cơ chế định vị này, DBMS có thể đi thẳng tới tệp tin nhị phân dựa theo $offset$ và trực tiếp cô lập đủ số byte quy định bởi $length$ mà không cần thiết lập bất kỳ byte kết thúc giới hạn (delimiter) nào.

### 2.3 Vai trò của Null Bitmap
Null Bitmap là một cơ chế tối ưu cho phép tiết kiệm các byte lưu trữ vật lý cho các trường thông tin mang giá trị `NULL`. Phía trước cơ sở dữ liệu của mỗi bản ghi, hệ thống đặt một chuỗi điều khiển dạng bit (ví dụ $1$ byte), trong đó bit thứ $i$ tương ứng cho trường thứ $i$. Nếu bit mang giá trị $1$, điều này có nghĩa là trường đó bị khuyết (`NULL`) và bản ghi sẽ bỏ qua việc lưu trữ hoàn toàn đoạn bộ nhớ đó. Cơ chế này loại bỏ thao tác lưu trữ thông tin vô nghĩa, tiết kiệm được hàng MB dữ liệu không cần thiết.

### 2.4 Tính chất Indirection: Vì sao Pointer trỏ trực tiếp tới Slot thay vì trỏ tới Record?
Khi bên ngoài trang cần tham chiếu tới một bản ghi thông qua hệ thống phân tầng (ví dụ Index B-Tree hoặc Foreign Key), con trỏ sẽ lưu trữ giá trị `RecordId = (PageID, SlotID)`, thay vì trỏ thẳng tới $offset$ thực tế bên trong block đĩa. Lớp trỏ trung gian **Indirection** này vô cùng quan trọng: 
Khi xảy ra sự thao tác dồn trang (Compaction) nhằm thu hồi các lỗ hổng bị xóa bớt, dữ liệu và $offset$ của bản ghi sẽ phải dịch chuyển. Nếu trỏ trực tiếp bằng $offset$, toàn bộ Index sẽ bị tàn phá và phải tái tạo. Việc trỏ đến $SlotID$ luôn giữ nguyên lập trường tham chiếu Index một cách ổn định, vì chỉ các entry định tính tại Slot Directory mới biến đổi vật lý trong suốt quá trình (vô hình trong góc nhìn của lớp Index ngoài).

---

## Phần 3: Thiết kế hệ thống (System Design)

### 3.1 Cấu trúc vật lý của Page ($4KB$)
Mỗi trang cấp phát chuẩn $4096$ bytes, thiết kế như sau:
- **Page Header ($12$ bytes):** Lưu các luồng điều khiển bao gồm `PageID` ($4$ bytes), `SlotCount` ($2$ bytes), `FreeSpacePointer` ($2$ bytes) và $4$ bytes dữ liệu dự trữ tự do.
- **Slot Directory:** Phát triển từ đầu bảng trở xuống phân rã từ sau Page Header, mỗi entry nạp đúng $4$ bytes chứa số liệu định danh $(offset, length)$.
- **Data Area:** Phát triển nghịch từ đáy trang ngược lên (chiều dưới lên), tính từ byte thứ $4095$ trở lại. Thao tác này sinh ra để dành chỗ cho Slot Directory tiếp tục phát triển.
- **Free Space:** Khoảng trống nằm giữa ranh giới Slot Directory và phần Data Area chưa giao thoa.

### 3.2 Cấu trúc Heap File
Heap File tổ chức hàng triệu bản ghi thông qua hệ thống tệp `.db` nguyên khối. Cấu trúc bao gồm các Block $4KB$ nối tiếp nhau và quản lý ngầm bằng cơ chế cấp số biên dịch `PageID = 0, 1, 2...`. Quản lý luồng dùng kiến trúc trung gian "Page Cache" trên RAM để triệt tiêu số lần truy vấn ổ I/O trực tiếp. 

### 3.3 Thuật toán cốt lõi
- **Insert:** Tính toán thử `new_offset = FreeSpacePtr - len(record)`. Nếu `new_offset` tính từ ranh giới nhỏ nhất của Free Space không đè lên vùng Header/Slot Directory hiện tại, hệ thống gán $SlotID$, lưu chuỗi bytes dữ liệu lên Data Area, lưu mục ghi chú trên Slot Directory và thiết lập lại `FreeSpacePtr`.
- **Delete (Lazy Deletion):** Cờ khóa giới hạn của bộ điều phối $offset$ trong bản ghi trở thành `0xFFFF` ($65535$). Vùng nhớ thực tế chưa lập tức bị xóa ngay nhằm giữ lại tốc độ nhanh nhạy của thuật toán giới hạn ở mức $O(1)$.
- **Compact Page:** Thuật toán kích hoạt cục bộ quét toàn bộ Slot Directory, dỡ rác các vùng byte liên kết với `0xFFFF`. Nó tuần tự di dời các Record an toàn ghép sát nhau, lấp kín không gian đứt đoạn và kết thúc quy trình bằng một Slot Directory với bộ biểu đồ $offset$ mới nhất.

---

## Phần 4: Kết quả thực hiện và Mô phỏng (Implementation & Demo)

### 4.1 Kịch bản Demo 
Nhóm thực hiện mô phỏng tương tác trên `PageID #42`:
1. **Insert:** Chèn tuần tự các Records chứa sinh viên. Các bản ghi cư trú tại Slot \#0, \#1, \#2, \#3.
2. **Delete:** Vận hành Lazy Deletion đối với bản ghi tại Slot \#1 và Slot \#2, phân mảnh sinh ra $109$ Bytes lỗ hổng rác. Không gian trống liên tục đo được là $3857$ Bytes.
3. **Compaction:** Khởi động hệ thống thu hồi miền nhớ. Page quét toàn bộ khoảng ghi bị xóa, xê dịch nội dung của Slot \#3 tiếp nối lên liền kề với Slot \#0.

| Minh chứng sự thay đổi bù đằng sau Compact | Trạng thái trước khi Compact | Trạng thái sau khi Compact |
| :--- | :--- | :--- |
| **Slot #0 (Nguyên vẹn)** | Offset: `4051`, Length: `45` bytes | Offset: `4051`, Length: `45` bytes |
| **Slot #1 (Xóa rác)** | Offset: `0xFFFF`, Length: `60` bytes | Offset: `0xFFFF`, Length: `0` bytes (Giải phóng) |
| **Slot #2 (Xóa rác)** | Offset: `0xFFFF`, Length: `49` bytes | Offset: `0xFFFF`, Length: `0` bytes (Giải phóng) |
| **Slot #3 (Di dời vật lý)**| Offset: `3885`, Length: `57` bytes | Offset: `3994`, Length: `57` bytes |
| **Dung lượng liên tục** | Thu hồi khả dụng: **$3857$ Bytes** | Thu hồi khả dụng: **$3966$ Bytes** |

### 4.2 Hiệu năng Hệ thống (Benchmarks)
Đo lường bằng dữ liệu thực tế lớn trên $1.000.000$ bản ghi, hệ thống thông kê:
- **Thời gian Bulk Load $1.000.000$ bản ghi:** Khoảng **$2.5$** s (Năng suất: $844,096$ Inserts/s).
- **Thời gian truy xuất ngẫu nhiên (Read):** Đạt **$0.0056$** ms/record ($5.6 \, \mu s$).
- **Thời gian thực hiện quá trình nháp (Compaction):** Mất **$2.707$** ms.
- **Kích thước file dữ liệu cuối cùng:** ~**$72.0$** MB. Việc thực hiện Sequential Scan bộ tệp $504.000$ records thực nghiệm tốn $0.471$ s.

---

## Phần 5: Phân tích và Đánh giá (Analysis)

### 5.1 Đánh giá Cơ sở lưu trữ giải quyết bài toán cốt lõi 
Quy trình Slotted Page là giải pháp chuẩn chỉnh đập tan 2 vấn đề lớn: sự phí phạm cấu trúc đối với lưu trữ biến thiên và chống lại việc bết dính tài nguyên bằng cơ chế gom nháp linh hoạt (Defragmentation), cùng lúc bảo đảm mọi cơ cấu định tuyến trong CSDL đều được an toàn.

### 5.2 Phân tích Ưu/Nhược điểm

1. **Ưu điểm vượt trội:**
   - **Tối ưu Tính toàn vẹn của con trỏ (Stable Indexing):** $SlotID$ hoạt động như một lớp cách ly (Indirection). Bất chấp việc xáo trộn vùng byte của Compaction, tham chiếu vẫn đứng nguyên, không đe dọa các kết nối ở Foreign Key hay B-Tree.
   - **Tối ưu hóa mức cao nhất trên bộ nhớ (Storage Efficient):** Bất kể hàng lưu trữ một đoạn văn bản hay một kí tự, trang đĩa thu hồi đúng con số chính xác số byte yêu cầu, đồng thời áp dụng Null Bitmap giảm trừ vô số biến số khuyết.
   - **Tốc độ thực thi tuyệt đối cho Deletion:** O($1$) chi phí cho hoạt động hủy bản ghi bằng Lazy Deletion. 
   - **Compact ngầm (On Demand):** Hệ thống không dọn dẹp thường trực để tránh rào cản thao tác, thay vào đó chỉ dồn trang khi không dưng xuất hiện sự cố nhồi bộ nhớ đứt đoạn.

2. **Nhược điểm giới hạn:**
   - **Chi phí tái lập CPU (Compaction CPU Overhead):** Tốn $O(n)$ chi phí quy trình copy-tháo-lắp lại vùng nhớ đối tượng, có thể kéo chậm tốc độ một vài mili-giây nếu hệ thống liên tục tiếp nhận truy vấn thay đổi.
   - **Chi phí hao tổn phần cứng (Directory Overhead):** Cấu trúc tốn mất $4$ bytes định danh cho mỗi Record làm hao đi gần $5$\% tài nguyên thật sự lưu trữ các khối thông tin thuần.

### 5.3 Môi trường áp dụng thực tế (Use Cases)
- **Chuẩn hóa toàn diện:** Là cốt lõi và nền móng không thể tách rời trong các **DBMS đặc trưng OLTP** (Online Transaction Processing) phổ cập. Ví dụ như `heap structures` thuộc **PostgreSQL**, đối tượng `compact` của mô hình **MySQL (InnoDB)** và cách bố trí mảng tế bào trực tiếp của hệ thống nhúng **SQLite**.
- **Không áp dụng đối với:** Các cấu trúc dạng Block không phải là điểm sáng cho hệ thống làm việc với nghiệp vụ thiên hướng Analytical, báo cáo dữ liệu định kì (OLAP) như **ClickHouse** hay **Snowflake**, nơi người ta ứng dụng hệ Columnar để tập trung sức mạnh Scan một cột cụ thể.

---

## Phần 6: Kết luận

Bài tập hoàn thiện hệ thống Slotted Page bằng cơ chế tự khai thác giúp củng cố kiến thức gốc liên quan đến cách dữ liệu được nhào nặn cấu trúc trong ổ địa. Từ thực tiễn phân rã thuật toán $1.000.000$ bản đồ tham chiếu và đối chứng phân tích chỉ số Benchmark, nó minh chứng rõ vì sao quá trình cân bằng giữa Insert/Delete với Defragmentation trên bộ vi xử lý và cách Indirection bảo tồn một con trỏ là những kỹ nghệ rường cột đảm bảo các công cụ cơ sở dữ liệu làm việc trơn tru thông qua hàng thập kỷ cải biến thiết kế máy tính. 

Đồ án là một điểm nhấn tuyệt vời ở phần đào tạo tổ chức lưu trữ và Data Processing ở mức cấp bậc lõi nguyên thủy `byte-level`.
