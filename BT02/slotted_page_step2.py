"""
=============================================================================
BÀI TẬP 02 – MÔ PHỎNG STORAGE MANAGEMENT (BƯỚC 2)
Chủ đề: Delete & Compact – Quản lý động Variable-Length Records
=============================================================================

Mở rộng từ slotted_page.py (Bước 1), thêm các cơ chế:
  1. delete_record(slot_id)  – Xóa mềm (Lazy Deletion)
  2. compact_page()          – Dồn trang, thu hồi phân mảnh
  3. visualize() nâng cao    – Bản đồ byte [H][S][.][R] + bảng Slot Directory

Kịch bản Demo 6 bước:
  B1: Khởi tạo Page 4KB
  B2: Chèn 5 bản ghi (A, B, C, D, E) với độ dài khác nhau
  B3: Xóa B và D → thấy "lỗ hổng" dữ liệu
  B4: Thử chèn F (100B) → phát hiện thiếu chỗ liên tục
  B5: compact_page() → dồn A, C, E sát nhau
  B6: Chèn F thành công

=============================================================================
TẠI SAO SLOT ID PHẢI GIỮ NGUYÊN KHI OFFSET THAY ĐỔI?
-----------------------------------------------------------------------------
Trong DBMS thực tế, các thành phần bên ngoài Page (ví dụ: Index B-Tree,
Foreign Key, con trỏ từ Page khác) tham chiếu tới record thông qua
"Record Pointer" có dạng (PageID, SlotID).

Nếu khi compact_page() mà ta thay đổi SlotID (ví dụ: dồn lại từ 0,1,2...),
thì TẤT CẢ các Pointer bên ngoài sẽ trỏ SAI → dữ liệu hỏng.

Do đó, SlotID là KHÔNG ĐỔI (stable identifier). Khi compact:
  - Chỉ thay đổi Offset bên trong Slot Entry (vì record dịch chuyển vị trí)
  - SlotID (vị trí trong Slot Directory) giữ nguyên
  - Pointer bên ngoài vẫn hợp lệ

Đây chính là cơ chế INDIRECTION: Pointer → SlotID → Offset → Data
Tầng SlotID đóng vai trò "trung gian", cho phép di chuyển dữ liệu vật lý
mà không ảnh hưởng đến tham chiếu logic.
=============================================================================
"""

import struct
import os

# ============================================================================
# CONSTANTS – Các hằng số định nghĩa layout của Page
# ============================================================================

PAGE_SIZE = 4096          # Kích thước cố định của một Page (4 KB)

# --- Header Layout (12 bytes) ---
# Offset 0..3  : Page ID          (unsigned int,  4 bytes, format 'I')
# Offset 4..5  : Slot Count       (unsigned short, 2 bytes, format 'H')
# Offset 6..7  : Free Space Ptr   (unsigned short, 2 bytes, format 'H')
# Offset 8..11 : Reserved         (4 bytes, không sử dụng)
HEADER_SIZE = 12

# --- Slot Entry (4 bytes mỗi slot) ---
# Mỗi Slot gồm: Offset (2B) + Length (2B)
# Khi Slot bị xóa mềm: Offset = 0xFFFF (65535, biểu diễn -1 trong unsigned)
SLOT_ENTRY_SIZE = 4

# Giá trị đặc biệt cho Slot đã bị xóa
DELETED_MARKER = 0xFFFF   # Offset = 65535 → slot đã xóa (tương đương -1)


class SlottedPage:
    """
    Lớp mô phỏng một Slotted Page trong hệ quản trị CSDL.
    Phiên bản Bước 2: Hỗ trợ Delete & Compact.

    Quản lý vùng nhớ bytearray 4096 bytes với:
      - Header cố định 12 bytes
      - Slot Directory phát triển từ trên xuống
      - Data Area phát triển từ dưới lên
    """

    def __init__(self, page_id: int = 0):
        """
        Khởi tạo một Page trống.

        Args:
            page_id: Mã định danh của Page (mặc định = 0).
        """
        self.data = bytearray(PAGE_SIZE)
        self.page_id = page_id
        self.slot_count = 0
        self.free_space_ptr = PAGE_SIZE
        self._write_header()

    # ========================================================================
    # HEADER OPERATIONS – Đọc / Ghi Header
    # ========================================================================

    def _write_header(self):
        """Ghi thông tin Header vào 12 bytes đầu tiên của Page."""
        struct.pack_into('<IHHI', self.data, 0,
                         self.page_id,
                         self.slot_count,
                         self.free_space_ptr,
                         0)  # 4 bytes reserved

    def _read_header(self):
        """Đọc Header từ vùng nhớ và cập nhật các thuộc tính của object."""
        self.page_id, self.slot_count, self.free_space_ptr, _ = \
            struct.unpack_from('<IHHI', self.data, 0)

    # ========================================================================
    # SLOT DIRECTORY HELPERS
    # ========================================================================

    def _read_slot(self, slot_id: int):
        """
        Đọc thông tin Slot Entry.

        Returns:
            (offset, length): Offset và Length của record.
                               offset == DELETED_MARKER nếu slot đã xóa.
        """
        slot_pos = HEADER_SIZE + slot_id * SLOT_ENTRY_SIZE
        offset, length = struct.unpack_from('<HH', self.data, slot_pos)
        return offset, length

    def _write_slot(self, slot_id: int, offset: int, length: int):
        """Ghi thông tin Slot Entry."""
        slot_pos = HEADER_SIZE + slot_id * SLOT_ENTRY_SIZE
        struct.pack_into('<HH', self.data, slot_pos, offset, length)

    # ========================================================================
    # INSERT – Chèn Record vào Page
    # ========================================================================

    def insert_record(self, data_bytes: bytes) -> int:
        """
        Chèn một record (dạng bytes) vào Page.

        Bước 2 cải tiến: Kiểm tra đủ không gian liên tục (contiguous free space).
        Nếu không đủ, trả mã lỗi -1 thay vì raise Exception để demo có thể
        xử lý bằng cách gọi compact_page().

        Args:
            data_bytes: Dữ liệu record dạng bytes.

        Returns:
            Slot number nếu thành công, -1 nếu không đủ chỗ.
        """
        record_len = len(data_bytes)

        # Tính vị trí cuối của Slot Directory hiện tại
        slot_dir_end = HEADER_SIZE + (self.slot_count * SLOT_ENTRY_SIZE)
        new_slot_dir_end = slot_dir_end + SLOT_ENTRY_SIZE

        # Tính vị trí bắt đầu của record mới trong Data Area
        new_record_offset = self.free_space_ptr - record_len

        # Kiểm tra không gian trống LIÊN TỤC
        # (free_space_ptr chỉ tính vùng liên tục, không tính lỗ hổng)
        if new_slot_dir_end > new_record_offset:
            return -1  # Không đủ chỗ liên tục

        # Ghi dữ liệu record vào Data Area
        self.data[new_record_offset:new_record_offset + record_len] = data_bytes

        # Ghi Slot Entry mới vào Slot Directory
        struct.pack_into('<HH', self.data, slot_dir_end,
                         new_record_offset, record_len)

        # Cập nhật metadata
        slot_number = self.slot_count
        self.slot_count += 1
        self.free_space_ptr = new_record_offset
        self._write_header()

        print(f"  ✓ Inserted Record vào Slot #{slot_number}")
        print(f"    → Offset = {new_record_offset}, Length = {record_len} bytes")
        print(f"    → Free Space Pointer = {self.free_space_ptr}")

        return slot_number

    # ========================================================================
    # DELETE – Xóa mềm Record (Lazy Deletion)
    # ========================================================================

    def delete_record(self, slot_id: int):
        """
        Xóa mềm (Lazy Deletion) một record khỏi Page.

        Cơ chế:
        ─────────────────────────────────────────────────────────
        1. Tìm đến Slot Entry tương ứng trong Slot Directory.
        2. Đặt Offset = DELETED_MARKER (0xFFFF ≈ -1).
        3. GIỮ NGUYÊN Length (để biết kích thước vùng data cũ).
        4. KHÔNG xóa dữ liệu thực tế trong Data Area.
        5. KHÔNG dịch chuyển bất kỳ dữ liệu nào.

        → Dữ liệu vẫn nằm tại vị trí cũ nhưng bị đánh dấu "đã xóa".
        → Vùng data cũ trở thành "lỗ hổng" (fragmentation).
        → compact_page() sẽ thu hồi các lỗ hổng này sau.

        Tại sao dùng Lazy Deletion?
        - Nhanh: O(1), chỉ cần sửa 2 bytes trong Slot Directory.
        - An toàn: Không di chuyển dữ liệu → không ảnh hưởng record khác.
        - Hiệu quả: Gom nhiều lần xóa, compact 1 lần.
        ─────────────────────────────────────────────────────────

        Args:
            slot_id: ID của Slot cần xóa (0-indexed).

        Raises:
            IndexError: Nếu slot_id ngoài phạm vi.
            ValueError: Nếu slot đã bị xóa trước đó.
        """
        # Kiểm tra phạm vi
        if slot_id < 0 or slot_id >= self.slot_count:
            raise IndexError(
                f"[LỖI] Slot #{slot_id} không tồn tại. "
                f"Hiện có {self.slot_count} slots (0..{self.slot_count - 1})."
            )

        # Đọc Slot Entry hiện tại
        offset, length = self._read_slot(slot_id)

        # Kiểm tra slot đã bị xóa chưa
        if offset == DELETED_MARKER:
            raise ValueError(
                f"[LỖI] Slot #{slot_id} đã bị xóa trước đó!"
            )

        # Thực hiện Lazy Deletion: đặt offset = DELETED_MARKER, giữ nguyên length
        self._write_slot(slot_id, DELETED_MARKER, length)

        print(f"  ✗ Deleted Record tại Slot #{slot_id} (Lazy Deletion)")
        print(f"    → Offset cũ = {offset}, Length = {length} bytes")
        print(f"    → Slot Directory: Offset đã được set = 0xFFFF (DELETED)")
        print(f"    → Dữ liệu vật lý CHƯA bị xóa (sẽ được thu hồi khi compact)")

    # ========================================================================
    # COMPACT – Dồn trang, thu hồi phân mảnh
    # ========================================================================

    def compact_page(self):
        """
        Thu hồi không gian bị phân mảnh do các bản ghi đã xóa để lại.

        Thuật toán Compaction:
        ─────────────────────────────────────────────────────────
        Bước 1: Duyệt Slot Directory, lọc ra các slot "còn sống"
                (offset != DELETED_MARKER).
                Lưu tạm: (slot_id, data_bytes) vào bộ nhớ đệm.

        Bước 2: Xóa sạch vùng Data Area trong bytearray
                (đặt tất cả bytes về 0x00).

        Bước 3: Chèn ngược lại các record vào Data Area theo quy tắc:
                - Bắt đầu từ cuối Page (byte 4095), lần lượt chèn ngược lên.
                - Thứ tự chèn: theo slot_id tăng dần (để dễ theo dõi).

        Bước 4: Cập nhật Offset mới trong Slot Directory.
                *** QUAN TRỌNG: Giữ nguyên Slot ID ban đầu ***
                Lý do: Pointer bên ngoài (ví dụ từ Index B-Tree) tham chiếu
                tới record qua (PageID, SlotID). Nếu thay đổi SlotID,
                tất cả các Pointer bên ngoài sẽ trở thành INVALID.

                → SlotID là stable identifier (không đổi)
                → Chỉ có Offset (vị trí vật lý) thay đổi khi compact
                → Đây chính là ý nghĩa của cơ chế Indirection

        Bước 5: Cập nhật Free Space Pointer trong Header.
        ─────────────────────────────────────────────────────────
        """
        print("  🔄 Bắt đầu COMPACT PAGE...")
        print("  ─────────────────────────────────────────────")

        # ── Bước 1: Thu thập các record còn sống ──
        live_records = []  # List of (slot_id, record_bytes)
        dead_count = 0
        reclaimed_bytes = 0

        for slot_id in range(self.slot_count):
            offset, length = self._read_slot(slot_id)

            if offset == DELETED_MARKER:
                # Slot đã xóa → bỏ qua, tính số bytes thu hồi
                dead_count += 1
                reclaimed_bytes += length
                print(f"    → Slot #{slot_id}: DELETED (thu hồi {length} bytes)")
            else:
                # Slot còn sống → lưu tạm dữ liệu
                record_data = bytes(self.data[offset:offset + length])
                live_records.append((slot_id, record_data))
                print(f"    → Slot #{slot_id}: ALIVE (offset={offset}, len={length})")

        print(f"\n  📊 Thống kê: {len(live_records)} record sống, "
              f"{dead_count} record đã xóa")
        print(f"  📊 Sẽ thu hồi: {reclaimed_bytes} bytes từ các lỗ hổng")

        # ── Bước 2: Xóa sạch vùng Data Area ──
        # Data Area nằm từ free_space_ptr đến PAGE_SIZE - 1
        # Nhưng sau khi xóa record, có các lỗ hổng nên ta xóa toàn bộ
        # vùng từ vị trí thấp nhất có thể (sau slot directory) đến cuối page
        slot_dir_end = HEADER_SIZE + (self.slot_count * SLOT_ENTRY_SIZE)
        for i in range(slot_dir_end, PAGE_SIZE):
            self.data[i] = 0x00
        print(f"\n  🧹 Đã xóa sạch Data Area (bytes {slot_dir_end}..{PAGE_SIZE - 1})")

        # ── Bước 3 & 4: Chèn ngược lại và cập nhật Slot Directory ──
        # Bắt đầu ghi từ cuối trang ngược lên
        write_ptr = PAGE_SIZE

        for slot_id, record_data in live_records:
            record_len = len(record_data)
            # Tính vị trí ghi mới: từ cuối trang trở lên
            new_offset = write_ptr - record_len

            # Ghi record vào vị trí mới
            self.data[new_offset:new_offset + record_len] = record_data

            # Cập nhật Slot Directory với Offset MỚI
            # *** SlotID KHÔNG ĐỔI – chỉ Offset bên trong slot thay đổi ***
            # Đây là điểm mấu chốt của cơ chế Indirection:
            #   - Pointer bên ngoài vẫn tham chiếu (PageID, SlotID) → không đổi
            #   - SlotID trỏ tới Offset mới → record ở vị trí vật lý mới
            old_offset, _ = self._read_slot(slot_id)
            self._write_slot(slot_id, new_offset, record_len)

            print(f"    → Slot #{slot_id}: di chuyển vật lý, Offset MỚI = {new_offset} "
                  f"(SlotID giữ nguyên = {slot_id})")

            write_ptr = new_offset

        # ── Bước 4b: Đặt Length = 0 cho các slot đã xóa ──
        # Sau compact, vùng data của record đã xóa đã bị thu hồi hoàn toàn
        # → Length nên = 0 để tránh tính nhầm trong get_total_free_space()
        for slot_id in range(self.slot_count):
            offset, length = self._read_slot(slot_id)
            if offset == DELETED_MARKER and length > 0:
                self._write_slot(slot_id, DELETED_MARKER, 0)

        # ── Bước 5: Cập nhật Free Space Pointer ──
        old_fsp = self.free_space_ptr
        self.free_space_ptr = write_ptr
        self._write_header()

        print(f"\n  ✅ COMPACT HOÀN TẤT!")
        print(f"    → Free Space Pointer: {old_fsp} → {self.free_space_ptr}")
        print(f"    → Không gian liên tục mới: "
              f"{self.free_space_ptr - slot_dir_end} bytes")
        print(f"    → Đã thu hồi {reclaimed_bytes} bytes phân mảnh")

    # ========================================================================
    # TÍNH TOÁN FREE SPACE
    # ========================================================================

    def get_contiguous_free_space(self) -> int:
        """
        Tính không gian trống LIÊN TỤC (giữa Slot Directory và Data Area).
        Đây là vùng có thể chèn record mới mà không cần compact.
        """
        slot_dir_end = HEADER_SIZE + (self.slot_count * SLOT_ENTRY_SIZE)
        # Trừ thêm SLOT_ENTRY_SIZE vì chèn record mới cần thêm 1 slot entry
        return self.free_space_ptr - slot_dir_end - SLOT_ENTRY_SIZE

    def get_total_free_space(self) -> int:
        """
        Tính tổng không gian trống (bao gồm cả lỗ hổng từ record đã xóa).
        Đây là không gian có thể dùng được SAU KHI compact.
        """
        contiguous = self.get_contiguous_free_space()
        # Cộng thêm bytes từ các slot đã xóa (lỗ hổng)
        fragmented = 0
        for slot_id in range(self.slot_count):
            offset, length = self._read_slot(slot_id)
            if offset == DELETED_MARKER:
                fragmented += length
        return contiguous + fragmented

    # ========================================================================
    # READ – Đọc Record từ Page
    # ========================================================================

    def read_record(self, slot_id: int) -> bytes:
        """
        Đọc record dựa trên slot ID.

        Args:
            slot_id: Chỉ số slot (0-indexed).

        Returns:
            Dữ liệu record dạng bytes.

        Raises:
            IndexError: Nếu slot_id ngoài phạm vi.
            ValueError: Nếu record đã bị xóa.
        """
        if slot_id < 0 or slot_id >= self.slot_count:
            raise IndexError(f"Slot #{slot_id} không tồn tại.")

        offset, length = self._read_slot(slot_id)

        if offset == DELETED_MARKER:
            raise ValueError(f"Slot #{slot_id} đã bị xóa!")

        return bytes(self.data[offset:offset + length])

    # ========================================================================
    # VISUALIZE – Hiển thị trực quan nâng cao
    # ========================================================================

    def visualize(self):
        """
        In ra sơ đồ byte nâng cao của Page, bao gồm:
          1. Bản đồ byte: [H] Header, [S] Slot, [.] Free Space, [R] Record Data
          2. Bảng Slot Directory: ID | Offset | Length | Status
          3. Thống kê bộ nhớ
        """
        self._read_header()

        slot_dir_end = HEADER_SIZE + (self.slot_count * SLOT_ENTRY_SIZE)
        free_space_size = self.free_space_ptr - slot_dir_end
        data_area_size = PAGE_SIZE - self.free_space_ptr

        # ── Tiêu đề ──
        print()
        print("=" * 72)
        print(f"  📄 SLOTTED PAGE VISUALIZATION – Page ID: {self.page_id}")
        print("=" * 72)

        # ══════════════════════════════════════════════════════════════════
        # 1. BẢN ĐỒ BYTE (Byte Map)
        # ══════════════════════════════════════════════════════════════════
        # Mỗi byte được đánh dấu: [H], [S], [.], [R], [X] (lỗ hổng từ xóa)

        # Xây dựng mảng đánh dấu cho từng byte
        byte_map = ['.'] * PAGE_SIZE    # Mặc định = Free Space

        # Header: bytes 0..11
        for i in range(HEADER_SIZE):
            byte_map[i] = 'H'

        # Slot Directory: bytes 12..(slot_dir_end - 1)
        for i in range(HEADER_SIZE, slot_dir_end):
            byte_map[i] = 'S'

        # Record Data & Lỗ hổng (Deleted data vẫn nằm trong vùng data)
        for slot_id in range(self.slot_count):
            offset, length = self._read_slot(slot_id)
            if offset != DELETED_MARKER:
                # Record còn sống → đánh dấu [R]
                for i in range(offset, offset + length):
                    byte_map[i] = 'R'
            else:
                # Record đã xóa → dữ liệu vẫn còn nhưng là "lỗ hổng"
                # Không đánh dấu gì thêm vì ta không biết vùng data cũ ở đâu
                # (offset đã bị ghi đè thành DELETED_MARKER)
                pass

        # Vùng từ free_space_ptr đến cuối page mà không phải Record → có thể
        # là lỗ hổng hoặc vùng trống. Ta để nguyên '.' cho vùng không có record.

        # In bản đồ byte (mỗi dòng 64 bytes)
        print(f"\n  ┌{'─' * 68}┐")
        print(f"  │{'BẢN ĐỒ BYTE (mỗi ký tự = 1 byte)':^68}│")
        print(f"  │{'[H]=Header  [S]=Slot  [.]=Free  [R]=Record':^68}│")
        print(f"  ├{'─' * 68}┤")

        BYTES_PER_LINE = 64
        for line_start in range(0, PAGE_SIZE, BYTES_PER_LINE):
            line_end = min(line_start + BYTES_PER_LINE, PAGE_SIZE)
            line_str = ''.join(byte_map[line_start:line_end])

            # Chỉ in các dòng "thú vị" (không phải toàn bộ Free Space)
            # In 4 dòng đầu (Header + Slot), 2 dòng giữa Free Space, 4 dòng cuối (Data)
            if (line_start < slot_dir_end + BYTES_PER_LINE or
                    line_start >= self.free_space_ptr - BYTES_PER_LINE or
                    set(line_str) != {'.'}):
                addr = f"{line_start:04d}"
                print(f"  │ {addr}: {line_str} │")
            elif line_start == slot_dir_end + BYTES_PER_LINE:
                # Dòng đầu tiên bị bỏ qua → in dấu "..."
                dots_info = f"... ({free_space_size} bytes Free Space) ..."
                print(f"  │ {'':4s}  {dots_info:^62s} │")

        print(f"  └{'─' * 68}┘")

        # ══════════════════════════════════════════════════════════════════
        # 2. BẢNG SLOT DIRECTORY
        # ══════════════════════════════════════════════════════════════════
        print(f"\n  ┌{'─' * 68}┐")
        print(f"  │{'BẢNG SLOT DIRECTORY':^68}│")
        print(f"  ├{'─' * 4}┬{'─' * 10}┬{'─' * 10}┬{'─' * 12}┬{'─' * 28}┤")
        print(f"  │{'ID':^4}│{'Offset':^10}│{'Length':^10}│{'Status':^12}│{'Data Preview':^28}│")
        print(f"  ├{'─' * 4}┼{'─' * 10}┼{'─' * 10}┼{'─' * 12}┼{'─' * 28}┤")

        for slot_id in range(self.slot_count):
            offset, length = self._read_slot(slot_id)

            if offset == DELETED_MARKER:
                status = "🗑 DELETED"
                preview = "(đã xóa)"
            else:
                status = "✅ ACTIVE"
                record_data = self.data[offset:offset + length]
                preview = record_data.decode('utf-8', errors='replace')
                if len(preview) > 24:
                    preview = preview[:21] + "..."

            print(f"  │{slot_id:^4}│{str(offset) if offset != DELETED_MARKER else '0xFFFF':^10}│"
                  f"{length:^10}│{status:^12}│ {preview:<27}│")

        print(f"  └{'─' * 4}┴{'─' * 10}┴{'─' * 10}┴{'─' * 12}┴{'─' * 28}┘")

        # ══════════════════════════════════════════════════════════════════
        # 3. LAYOUT TỔNG QUAN
        # ══════════════════════════════════════════════════════════════════
        print(f"\n  ┌{'─' * 68}┐")
        print(f"  │{'LAYOUT TỔNG QUAN':^68}│")
        print(f"  ├{'─' * 68}┤")
        print(f"  │  Header         : {HEADER_SIZE:>6} bytes  (Bytes 0 – {HEADER_SIZE - 1}){' ' * 22}│")
        print(f"  │  Slot Directory : {slot_dir_end - HEADER_SIZE:>6} bytes  "
              f"(Bytes {HEADER_SIZE} – {slot_dir_end - 1 if slot_dir_end > HEADER_SIZE else HEADER_SIZE}){' ' * max(0, 20 - len(str(slot_dir_end - 1)))}│")
        print(f"  │  Free Space     : {free_space_size:>6} bytes  "
              f"(Bytes {slot_dir_end} – {self.free_space_ptr - 1}){' ' * max(0, 16 - len(str(self.free_space_ptr - 1)))}│")
        print(f"  │  Data Area      : {data_area_size:>6} bytes  "
              f"(Bytes {self.free_space_ptr} – {PAGE_SIZE - 1}){' ' * max(0, 16 - len(str(PAGE_SIZE - 1)))}│")
        print(f"  ├{'─' * 68}┤")

        # Thanh tiến trình
        bar_width = 50
        used_slots = max(1, int((slot_dir_end / PAGE_SIZE) * bar_width))
        used_data = int((data_area_size / PAGE_SIZE) * bar_width)
        used_free = bar_width - used_slots - used_data
        if used_free < 0:
            used_free = 0

        bar = "█" * used_slots + "░" * used_free + "▓" * used_data
        print(f"  │  [{bar}]  │")
        print(f"  │  {'█=Slot+Hdr':<16} {'░=Free':<17} {'▓=Data':<16}     │")
        print(f"  ├{'─' * 68}┤")

        # Thống kê
        contiguous = self.get_contiguous_free_space()
        total_free = self.get_total_free_space()
        usage_pct = ((PAGE_SIZE - total_free - SLOT_ENTRY_SIZE) / PAGE_SIZE) * 100

        print(f"  │  📊 Free Space liên tục  : {contiguous:>6} bytes{' ' * 27}│")
        print(f"  │  📊 Free Space tổng cộng : {total_free:>6} bytes (sau compact){' ' * 12}│")
        print(f"  │  📊 Tỉ lệ sử dụng       : {usage_pct:>6.2f}%{' ' * 28}│")
        print(f"  └{'─' * 68}┘")
        print()


# ============================================================================
# DEMO – Kịch bản minh họa 6 bước
# ============================================================================

def main():
    print()
    print("╔" + "═" * 70 + "╗")
    print("║" + " BƯỚC 2: DELETE & COMPACT – QUẢN LÝ ĐỘNG VARIABLE-LENGTH RECORDS ".center(70) + "║")
    print("╚" + "═" * 70 + "╝")

    # ═══════════════════════════════════════════════════════════════════
    # B1: Khởi tạo Page 4KB
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 72)
    print("  📌 BƯỚC 1: KHỞI TẠO PAGE 4KB")
    print("─" * 72)
    page = SlottedPage(page_id=1)
    print(f"  → Page Size      = {PAGE_SIZE} bytes (4 KB)")
    print(f"  → Header Size    = {HEADER_SIZE} bytes")
    print(f"  → Slot Entry     = {SLOT_ENTRY_SIZE} bytes/slot")
    print(f"  → Free Space Ptr = {page.free_space_ptr}")

    # ═══════════════════════════════════════════════════════════════════
    # B2: Chèn 5 bản ghi (A, B, C, D, E) với độ dài khác nhau
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 72)
    print("  📌 BƯỚC 2: CHÈN 5 BẢN GHI (A, B, C, D, E)")
    print("─" * 72)

    # Tạo 5 record với kích thước khác nhau để LẤP ĐẦY phần lớn Page:
    #   Header = 12B, mỗi Slot = 4B → 5 slots = 20B
    #   Tổng overhead = 12 + 20 = 32B
    #   Tổng data = 800 + 1200 + 600 + 1000 + 400 = 4000B
    #   Tổng sử dụng = 32 + 4000 = 4032B → chỉ còn 64B free liên tục!
    #   Sau khi xóa B(1200B) và D(1000B) → lỗ hổng = 2200B nhưng free liên tục vẫn = 64B
    #   → Record F (100B) không chèn được mà phải compact trước!
    records = {
        'A': b'A' * 800,     # Record A: 800 bytes
        'B': b'B' * 1200,    # Record B: 1200 bytes (sẽ xóa)
        'C': b'C' * 600,     # Record C: 600 bytes
        'D': b'D' * 1000,    # Record D: 1000 bytes (sẽ xóa)
        'E': b'E' * 400,     # Record E: 400 bytes
    }

    slot_ids = {}
    for name, data in records.items():
        print(f"\n  📝 Chèn Record {name} ({len(data)} bytes):")
        slot_id = page.insert_record(data)
        slot_ids[name] = slot_id

    print(f"\n  📋 Bảng Slot ID: {slot_ids}")
    page.visualize()

    # ═══════════════════════════════════════════════════════════════════
    # B3: Xóa bản ghi B và D → lỗ hổng dữ liệu
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 72)
    print("  📌 BƯỚC 3: XÓA BẢN GHI B VÀ D (Lazy Deletion)")
    print("─" * 72)

    print(f"\n  🗑 Xóa Record B (Slot #{slot_ids['B']}):")
    page.delete_record(slot_ids['B'])

    print(f"\n  🗑 Xóa Record D (Slot #{slot_ids['D']}):")
    page.delete_record(slot_ids['D'])

    print("\n  ⚠ Trạng thái sau khi xóa B và D:")
    print("    Record B và D đã bị đánh dấu DELETED trong Slot Directory.")
    print("    Dữ liệu vật lý vẫn còn → tạo ra 'lỗ hổng' (fragmentation).")
    print("    Các lỗ hổng này KHÔNG thể sử dụng cho record mới!")
    page.visualize()

    # ═══════════════════════════════════════════════════════════════════
    # B4: Thử chèn Record F (100 bytes) → kiểm tra thiếu chỗ
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 72)
    print("  📌 BƯỚC 4: THỬ CHÈN RECORD F (100 bytes)")
    print("─" * 72)

    record_f = b'F' * 100  # Record F: 100 bytes

    print(f"\n  📝 Yêu cầu chèn Record F ({len(record_f)} bytes)...")
    print(f"  → Không gian liên tục hiện tại: {page.get_contiguous_free_space()} bytes")
    print(f"  → Tổng không gian (bao gồm lỗ hổng): {page.get_total_free_space()} bytes")

    result = page.insert_record(record_f)

    if result == -1:
        print(f"\n  ❌ KHÔNG ĐỦ KHÔNG GIAN LIÊN TỤC!")
        print(f"     Record F cần: {len(record_f)} bytes")
        print(f"     Không gian liên tục: {page.get_contiguous_free_space()} bytes")
        print(f"     Tổng không gian có thể dùng: {page.get_total_free_space()} bytes")
        print(f"\n  💡 GIẢI PHÁP: Cần gọi compact_page() để thu hồi lỗ hổng!")
        print(f"     Sau compact, dự kiến sẽ có đủ chỗ cho Record F.")
    else:
        print(f"  ✓ Chèn thành công (không cần compact)")

    # ═══════════════════════════════════════════════════════════════════
    # B5: Gọi compact_page() → dồn A, C, E sát nhau
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 72)
    print("  📌 BƯỚC 5: COMPACT PAGE – DỒN TRANG")
    print("─" * 72)

    print("\n  Trước khi compact:")
    print(f"    → Free Space liên tục : {page.get_contiguous_free_space()} bytes")
    print(f"    → Tổng Free Space     : {page.get_total_free_space()} bytes")

    print()
    page.compact_page()

    print("\n  Sau khi compact:")
    print(f"    → Free Space liên tục : {page.get_contiguous_free_space()} bytes")
    print(f"    → Tổng Free Space     : {page.get_total_free_space()} bytes")
    print(f"    → Records A, C, E giờ nằm SÁT NHAU từ cuối Page")
    print(f"    → Các lỗ hổng từ B, D đã được thu hồi")

    page.visualize()

    # ═══════════════════════════════════════════════════════════════════
    # B6: Chèn thành công Record F
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 72)
    print("  📌 BƯỚC 6: CHÈN RECORD F SAU COMPACT")
    print("─" * 72)

    print(f"\n  📝 Chèn Record F ({len(record_f)} bytes):")
    result = page.insert_record(record_f)

    if result == -1:
        print("  ❌ Vẫn không đủ chỗ (Page gần đầy).")
    else:
        slot_ids['F'] = result
        print(f"  ✅ THÀNH CÔNG! Record F đã được chèn vào Slot #{result}")

    print("\n  📋 Trạng thái CUỐI CÙNG của Page:")
    page.visualize()

    # ═══════════════════════════════════════════════════════════════════
    # TỔNG KẾT
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "═" * 72)
    print("  📚 TỔNG KẾT KIẾN THỨC")
    print("═" * 72)
    print("""
  1. LAZY DELETION (Xóa mềm):
     - Chỉ đánh dấu Slot Offset = 0xFFFF, KHÔNG xóa dữ liệu vật lý.
     - Ưu điểm: O(1), nhanh, an toàn.
     - Nhược điểm: Gây phân mảnh (fragmentation).

  2. COMPACTION (Dồn trang):
     - Thu hồi tất cả lỗ hổng, dồn record sát nhau.
     - Chi phí: O(n) – phải copy toàn bộ record còn sống.
     - Khi nào gọi: Khi cần chèn mà không đủ chỗ liên tục.

  3. TẠI SAO SLOT ID KHÔNG ĐỔI?
     - Pointer bên ngoài (Index, FK) tham chiếu: (PageID, SlotID).
     - Nếu đổi SlotID khi compact → pointer INVALID → dữ liệu hỏng.
     - Cơ chế Indirection: Pointer → SlotID → Offset → Data.
     - SlotID là "điểm neo" ổn định, Offset là "con trỏ vật lý" linh hoạt.

  4. CONTIGUOUS vs TOTAL FREE SPACE:
     - Contiguous: Vùng trống liên tục giữa Slot Dir và Data Area.
     - Total: Contiguous + lỗ hổng (chỉ dùng được sau compact).
     - Insert chỉ kiểm tra contiguous free space.
""")
    print("─" * 72)
    print("  ✅ HOÀN TẤT DEMO BƯỚC 2!")
    print("─" * 72)
    print()


if __name__ == "__main__":
    main()
