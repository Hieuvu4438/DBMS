# BÁO CÁO CHUYÊN SÂU: BƯỚC 2 - QUẢN LÝ XOÁ VÀ DỒN PHÂN MẢNH TRANG (DELETE & COMPACT)
**(Dựa trên phân tích mã nguồn `slotted_page_step2.py`)**

Tiếp nối lý thuyết tại Bước 1, mã nguồn `slotted_page_step2.py` nâng cấp hệ thống Slotted Page cơ bản để giải quyết hai vấn đề nảy sinh trong thực tế thay đổi dữ liệu: **Xóa bản ghi (Deletion)** và **Dồn trang - Xử lý phân mảnh (Compact/Defragmentation)**.

---

## 1. CƠ CHẾ XÓA MỀM (LAZY DELETION)

### Tại sao không xóa thật ngay lập tức?
Khi xóa 1 Record nằm ở giữa Page, nếu làm theo kiểu mảng thông thường: Máy tính sẽ phải dời tất cả phần dữ liệu nằm bên trên tụt xuống dưới. Tốc độ sẽ vô cùng chậm (độ phức tạp O(N)). 

### Giải pháp kỹ thuật trong code:
*   Mã nguồn dùng kỹ thuật **Xóa mềm (Lazy Deletion)**.
*   Thay vì đụng chạm vào 100~500 bytes của Record trong `Data Area`, DBMS chỉ cần trèo lên khu vực thẻ nhớ `Slot Directory` dài 4 bytes.
*   Trong Slot Directory chèn số `0xFFFF` (giá trị 65535, đại diện cho chỉ số `-1`) đè lên con số Offset cũ.
*   **Chi phí:** Thời gian cực nhanh O(1).
*   **Hậu quả:** Khối dữ liệu thực sự (bản ghi A chẳng hạn) vẫn còn chình ình nằm nguyên ở đáy trang. Nó đã trở thành một cục "Lỗ hổng không gian chết" (Fragmentation). Cục rỗng này nằm chặn giữa nên ta không thể đút bản ghi mới vào khoảng hở (Slotted Page yêu cầu vùng `Contiguous Space` - không gian liên tục).

---

## 2. QUỸ ĐẠO DỒN BỘ NHỚ (COMPACTION / DEFRAGMENTATION)

Để quét sạch các "Lỗ hổng không gian chết", DBMS phải tiến hành thuật toán "Dọn dẹp mảng" gọi là `compact_page()`. Tác vụ này gây tốn CPU vì phải sao chép dữ liệu, nên nó chỉ được gọi khi CSDL có yêu cầu chèn nhưng Page báo lỗi "Hết dung lượng liên tục".

### Luồng xử lý kỹ thuật thuật toán Compact:
1.  **Lọc dữ liệu:** Quét qua Slot Directory. Với những slot có bù trừ Offset ≠ `0xFFFF` (Slot còn sống), copy bọc tạm cục bytes đó vào bộ nhớ Ram đệm (Buffer).
2.  **Khởi tạo lại mảng:** Làm sạch phần đáy của 4096 bytes gốc (Data Area được quy về số 0x00).
3.  **Nạp lại từng phần:** Quét vòng lặp đổ lần lượt các Record còn sống ở bước 1 vào lại từ đáy Page đẩy ngược lên. Bây giờ chúng sẽ xếp hạng "khít rịt" với nhau, các "lỗ hổng" đã biến mất, dồn khoảng trống lớn lên đầu trang (Tăng bộ `Contiguous Free Space`).
4.  **Cập nhật Thẻ Bài Slot (QUAN TRỌNG NHẤT):** Vị trí mới của bản ghi C khi bị đẩy sát bản ghi A sẽ bị thay đổi thông số lưu vật lý (`Offset`). DBMS sẽ cập nhật `Offset thẻ từ` cho `Slot` của bản ghi C.

---

## 3. VAI TRÒ CỦA INDIRECTION KHI DỒN TRANG

Điểm kỳ diệu nằm ở bước Update thẻ Slot: **Chỉ có Offset (Vị trí đệm RAM) thay đổi, nhưng số thứ tự Slot ID không hề bị thay thế.**

*   Giả sử: Bản ghi C lúc khởi tạo là `Slot ID: 3`, nằm ở `Offset: 3400`. Khi có Lệnh dồn trang, Bản Ghi C bị kéo tụt xuống `Offset: 3800` để ép lỗ hổng lấp khoảng trống. `Slot ID: 3` của C không bao giờ bị giáng chức hay mất vị thế. Bản thân `Slot ID: 3` nằm ở Directory chỉ đổi thẻ lưu nháp giá trị bù trừ.
*   Bảo Vệ Tính Vẹn Toàn Của Index CSDL: Bên ngoài Page nọ có "Cây tìm kiếm B-Tree", nó luôn được lưu trỏ đến toạ độ `Page: X, Slot: 3`. Nếu hàm Compaction thay đổi chỉ số Slot gốc, cây B-Tree sẽ chết và đứt gãy mạch dẫn. Cơ chế gián tiếp (Indirection) cứu hệ thống khỏi cảnh ngộ đó.

---

## 4. KHÁI NIỆM "TOTAL FREE SPACE" VS "CONTIGUOUS FREE SPACE"

Trong quá trình bảo trì Trang, DBMS liên tục kiểm tra 2 khía cạnh thể tích:
*   `Total Free Space`: Bằng tổng những Lỗ Hổng cộng lại với Không Gian Trống Liên Hiện Có. Đo rẽ bằng con mắt lý thuyết nếu dồn lại thì trống bao nhiêu.
*   `Contiguous Free Space`: Khoảng xanh liên tục 1 khối ở giữa Page. Con số này mới là trọng tâm cho thao tác `Insert`.

**Ví dụ:** `Total space = 100 Bytes` nhưng `Contiguous space = 30 Bytes` (Bị che mất do phân mảnh lỗ hổng 70 Bytes ở phía dưới). CSDL khi có nhu cầu chèn 50 byte vào, lúc này nó gặp tình trạng "Không gian liên tục quá nhỏ nhưng Không gian rỗng sau dồn thì chứa đủ". Do vậy nó sẽ kích hoạt quá trình gọi hàm dồn `compact_page()` xử lý rồi mới nhét 50 Bytes xuống.
