📄 DBMS Project Context: Storage Management Simulation
1. Mục tiêu dự án
Mô phỏng cơ chế quản lý lưu trữ vật lý của một Hệ quản trị cơ sở dữ liệu (DBMS), tập trung vào việc quản lý Variable-Length Records (Bản ghi độ dài biến đổi) bằng cấu trúc Slotted Page.

2. Thông số kỹ thuật (Physical Specifications)
Kích thước Page (Page Size): 4096 bytes (4KB).

Ngôn ngữ triển khai: Python (sử dụng thư viện struct để xử lý Binary).

Cấu trúc Page Layout (Từ địa chỉ thấp đến cao):

Page Header (12 bytes): PageID (4B), SlotCount (2B), FreeSpacePointer (2B), Reserved (4B).

Slot Directory: Danh sách các Slot. Mỗi Slot gồm (Offset: 2B, Length: 2B). Vùng này phát triển xuôi từ đầu Page.

Free Space: Vùng trống nằm giữa Slot Directory và Data Area.

Data Area: Chứa dữ liệu bản ghi thực tế. Phát triển ngược từ cuối Page lên trên.

Cơ chế Indirection: Pointer từ bên ngoài trỏ vào SlotID (cố định), SlotID chứa Offset (biến đổi) trỏ đến Record thực tế.

3. Cấu trúc Dữ liệu (Dataset)
Sử dụng 3 bảng chính (Lưu trữ dưới dạng Variable-Length):

Student(student_id, full_name, class_name, email, phone)

Course(course_id, course_name, credits, dept_name)

Enrollment(student_id, course_id, semester, score)
Lưu ý: Các trường như full_name, email có độ dài không cố định.

4. Trạng thái dự án (Current Progress)
[x] Bước 1: Thiết kế vật lý & Chèn dữ liệu.

Đã có class SlottedPage.

Đã có hàm serialize_record và insert_record.

Đã có hàm visualize cơ bản để xem bản đồ Byte.

Đã có hàm save_to_bin xuất file .bin.

[ ] Bước 2: Quản lý động (Delete & Compact) - ĐANG THỰC HIỆN.

Cần hàm delete_record(slot_id) (Lazy deletion).

Cần hàm compact_page() để dồn dữ liệu, cập nhật Offset nhưng giữ nguyên SlotID.

Demo trạng thái trước/sau khi Compact.

[ ] Bước 3: Quản lý Dataset lớn.

Xây dựng HeapFile để quản lý 500.000 - 1.000.000 bản ghi.

Cơ chế đọc/ghi Page từ File nhị phân bằng seek().

[ ] Bước 4: Báo cáo và Đo lường.

Đo thời gian xử lý (Insert, Search, Delete, Compact).

Giải thích ưu/nhược điểm và bài toán Slotted Page giải quyết.

5. Quy tắc lập trình (Guidelines for AI)
Luôn dùng struct: Mọi thao tác ghi vào bytearray phải dùng offset chính xác.

Tính ổn định của SlotID: Trong bất kỳ thao tác dồn trang (Compaction) nào, SlotID trong Directory tuyệt đối không được thay đổi vị trí, chỉ được cập nhật giá trị Offset bên trong nó.

Visualize: Mọi hàm xử lý dữ liệu phải đi kèm khả năng hiển thị thay đổi vật lý của các Byte trong Page.

Error Handling: Phải kiểm tra tràn trang (Page Full) trước khi chèn.