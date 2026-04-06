"""
=============================================================================
BÀI TẬP 02 – MÔ PHỎNG STORAGE MANAGEMENT
Chủ đề: Variable-Length Records & Slotted Page
=============================================================================

Cấu trúc vật lý của một Slotted Page (4096 bytes):

┌─────────────────────────────────────────────────────────┐  Byte 0
│                     PAGE HEADER (12 bytes)               │
│  ┌──────────┬────────────┬─────────────────┬──────────┐ │
│  │ Page ID  │ Slot Count │ Free Space Ptr  │ Reserved │ │
│  │  (4B)    │   (2B)     │     (2B)        │  (4B)    │ │
│  └──────────┴────────────┴─────────────────┴──────────┘ │
├─────────────────────────────────────────────────────────┤  Byte 12
│              SLOT DIRECTORY (grows downward ↓)           │
│  ┌──────────────────┬──────────────────┬─────────┐      │
│  │ Slot 0 (Off|Len) │ Slot 1 (Off|Len) │  ...    │      │
│  │    (2B + 2B)      │    (2B + 2B)      │         │      │
│  └──────────────────┴──────────────────┴─────────┘      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                 FREE SPACE (trống)                       │
│                                                         │
├─────────────────────────────────────────────────────────┤
│              DATA AREA (grows upward ↑)                  │
│  ┌──────────────┬──────────────┬──────────────┐         │
│  │  Record N    │  Record N-1  │  Record ...  │         │
│  └──────────────┴──────────────┴──────────────┘         │
└─────────────────────────────────────────────────────────┘  Byte 4095

Slot Directory phát triển từ đầu trang xuống (sau Header).
Data Area phát triển từ cuối trang ngược lên.
Hai vùng tiến vào nhau, khoảng giữa là Free Space.
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
SLOT_ENTRY_SIZE = 4


class SlottedPage:
    """
    Lớp mô phỏng một Slotted Page trong hệ quản trị CSDL.
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

        Giải thích Offset ban đầu:
        - slot_count = 0          : Chưa có slot nào
        - free_space_ptr = 4096   : Con trỏ Free Space bắt đầu ở cuối trang
                                    (vì Data Area chưa có dữ liệu)
        """
        # Vùng nhớ vật lý – mảng 4096 bytes, khởi tạo toàn bộ bằng 0x00
        self.data = bytearray(PAGE_SIZE)

        self.page_id = page_id
        self.slot_count = 0
        # Free Space Pointer trỏ tới byte đầu tiên của vùng Data Area
        # Ban đầu = PAGE_SIZE (4096), nghĩa là Data Area rỗng
        self.free_space_ptr = PAGE_SIZE

        # Ghi Header ban đầu vào vùng nhớ
        self._write_header()

    # ========================================================================
    # HEADER OPERATIONS – Đọc / Ghi Header
    # ========================================================================

    def _write_header(self):
        """
        Ghi thông tin Header vào 12 bytes đầu tiên của Page.

        Layout:
          Bytes 0-3  : Page ID          (struct format 'I' = unsigned int)
          Bytes 4-5  : Slot Count       (struct format 'H' = unsigned short)
          Bytes 6-7  : Free Space Ptr   (struct format 'H' = unsigned short)
          Bytes 8-11 : Reserved = 0     (struct format 'I' = unsigned int)

        Tổng format: '<IHH I' = little-endian, 4+2+2+4 = 12 bytes
        """
        struct.pack_into('<IHHI', self.data, 0,
                         self.page_id,
                         self.slot_count,
                         self.free_space_ptr,
                         0)  # 4 bytes reserved

    def _read_header(self):
        """
        Đọc Header từ vùng nhớ và cập nhật các thuộc tính của object.
        """
        self.page_id, self.slot_count, self.free_space_ptr, _ = \
            struct.unpack_from('<IHHI', self.data, 0)

    # ========================================================================
    # SERIALIZE – Chuyển đổi dữ liệu sinh viên thành bytes
    # ========================================================================

    @staticmethod
    def serialize_student(student_id: int, name: str, email: str) -> bytes:
        """
        Chuyển dữ liệu sinh viên thành chuỗi bytes với định dạng:
            id|name|email

        Ví dụ: serialize_student(1, "Nguyen Van A", "a@mail.com")
               → b'1|Nguyen Van A|a@mail.com'

        Lưu ý: Do name và email có độ dài khác nhau,
                mỗi record sẽ có kích thước (length) khác nhau
                → đây chính là Variable-Length Record.

        Args:
            student_id: Mã sinh viên (số nguyên).
            name:       Họ tên sinh viên (chuỗi).
            email:      Email sinh viên (chuỗi).

        Returns:
            Chuỗi bytes đã được encode UTF-8.
        """
        record_str = f"{student_id}|{name}|{email}"
        return record_str.encode('utf-8')

    # ========================================================================
    # INSERT – Chèn Record vào Page
    # ========================================================================

    def insert_record(self, data_bytes: bytes) -> int:
        """
        Chèn một record (dạng bytes) vào Page.

        Thuật toán tính Offset:
        ─────────────────────────────────────────────────────────
        1. Tính vị trí kết thúc của Slot Directory hiện tại:
           slot_dir_end = HEADER_SIZE + (slot_count × SLOT_ENTRY_SIZE)

           Ví dụ: Nếu đã có 2 slots:
               slot_dir_end = 12 + (2 × 4) = 20
               → Slot Directory chiếm bytes 12..19
               → Slot mới (slot #2) sẽ bắt đầu tại byte 20

        2. Tính vị trí ghi dữ liệu (Data Area):
           new_record_offset = free_space_ptr - len(data_bytes)

           Ví dụ: free_space_ptr = 4096, record dài 25 bytes
               new_record_offset = 4096 - 25 = 4071
               → Record được ghi vào bytes 4071..4095

        3. Kiểm tra còn đủ chỗ không:
           Cần: slot_dir_end + SLOT_ENTRY_SIZE (cho slot mới) ≤ new_record_offset
           Nếu không đủ → báo lỗi "Page is full"

        4. Ghi record vào Data Area        (tại new_record_offset)
        5. Ghi slot entry vào Slot Directory (tại slot_dir_end)
        6. Cập nhật header: slot_count++, free_space_ptr = new_record_offset
        ─────────────────────────────────────────────────────────

        Args:
            data_bytes: Dữ liệu record dạng bytes.

        Returns:
            Slot number (chỉ số) của record vừa chèn.

        Raises:
            ValueError: Nếu Page không còn đủ không gian.
        """
        record_len = len(data_bytes)

        # ── Bước 1: Tính vị trí cuối của Slot Directory hiện tại ──
        # Slot Directory bắt đầu ngay sau Header (byte 12).
        # Mỗi slot chiếm 4 bytes → tổng cộng slot_count × 4 bytes.
        slot_dir_end = HEADER_SIZE + (self.slot_count * SLOT_ENTRY_SIZE)
        # Sau khi chèn, sẽ thêm 1 slot mới nữa
        new_slot_dir_end = slot_dir_end + SLOT_ENTRY_SIZE

        # ── Bước 2: Tính vị trí bắt đầu của record mới trong Data Area ──
        # Data Area phát triển từ cuối trang ngược lên.
        # free_space_ptr trỏ tới byte thấp nhất của Data Area hiện tại.
        # Record mới sẽ được đặt ngay TRƯỚC vùng data hiện có.
        new_record_offset = self.free_space_ptr - record_len

        # ── Bước 3: Kiểm tra không gian trống ──
        # Vùng Free Space nằm giữa slot_dir_end mới và new_record_offset.
        # Nếu Slot Directory "đụng" Data Area → hết chỗ!
        if new_slot_dir_end > new_record_offset:
            raise ValueError(
                f"[LỖI] Page đã đầy! Cần {record_len + SLOT_ENTRY_SIZE} bytes, "
                f"chỉ còn {self.free_space_ptr - slot_dir_end - SLOT_ENTRY_SIZE} bytes trống."
            )

        # ── Bước 4: Ghi dữ liệu record vào Data Area ──
        # Sao chép record_len bytes vào vùng [new_record_offset .. new_record_offset + record_len)
        self.data[new_record_offset:new_record_offset + record_len] = data_bytes

        # ── Bước 5: Ghi Slot Entry mới vào Slot Directory ──
        # Slot entry gồm: Offset (2B) + Length (2B)
        # Vị trí ghi = slot_dir_end (ngay sau slot cuối cùng hiện tại)
        struct.pack_into('<HH', self.data, slot_dir_end,
                         new_record_offset,   # Offset: vị trí record trong Page
                         record_len)           # Length: kích thước record

        # ── Bước 6: Cập nhật metadata ──
        slot_number = self.slot_count
        self.slot_count += 1
        self.free_space_ptr = new_record_offset

        # Ghi lại Header với giá trị mới
        self._write_header()

        print(f"  ✓ Inserted Record vào Slot #{slot_number}")
        print(f"    → Record Offset = {new_record_offset}, Length = {record_len} bytes")
        print(f"    → Slot Directory End = {new_slot_dir_end}")
        print(f"    → Free Space Pointer cập nhật = {self.free_space_ptr}")
        print(f"    → Free Space còn lại = "
              f"{self.free_space_ptr - new_slot_dir_end} bytes")

        return slot_number

    # ========================================================================
    # READ – Đọc Record từ Page
    # ========================================================================

    def read_record(self, slot_number: int) -> bytes:
        """
        Đọc record dựa trên slot number.

        Args:
            slot_number: Chỉ số slot (0-indexed).

        Returns:
            Dữ liệu record dạng bytes.
        """
        if slot_number < 0 or slot_number >= self.slot_count:
            raise IndexError(f"Slot #{slot_number} không tồn tại. "
                             f"Hiện có {self.slot_count} slots (0..{self.slot_count - 1}).")

        # Tính vị trí của slot entry trong Slot Directory
        slot_offset = HEADER_SIZE + (slot_number * SLOT_ENTRY_SIZE)
        record_offset, record_length = struct.unpack_from('<HH', self.data, slot_offset)

        return bytes(self.data[record_offset:record_offset + record_length])

    # ========================================================================
    # VISUALIZE – Hiển thị trực quan cấu trúc Page
    # ========================================================================

    def visualize(self):
        """
        In ra sơ đồ mô phỏng chi tiết cấu trúc Page, bao gồm:
        - Header (12 bytes đầu tiên)
        - Slot Directory (mỗi slot 4 bytes)
        - Free Space (vùng trống giữa)
        - Data Area (các record từ cuối trang)
        """
        # Đọc lại header để đảm bảo dữ liệu chính xác
        self._read_header()

        # Tính các ranh giới
        slot_dir_end = HEADER_SIZE + (self.slot_count * SLOT_ENTRY_SIZE)
        free_space_size = self.free_space_ptr - slot_dir_end
        data_area_size = PAGE_SIZE - self.free_space_ptr

        # ── In tiêu đề ──
        print()
        print("=" * 72)
        print(f"  📄 SLOTTED PAGE VISUALIZATION – Page ID: {self.page_id}")
        print("=" * 72)

        # ── 1. HEADER ──
        print(f"\n  ┌{'─' * 68}┐")
        print(f"  │{'HEADER (Bytes 0 – 11)':^68}│")
        print(f"  ├{'─' * 68}┤")
        print(f"  │  Page ID          = {self.page_id:<44} │")
        print(f"  │  Slot Count       = {self.slot_count:<44} │")
        print(f"  │  Free Space Ptr   = {self.free_space_ptr:<44} │")
        print(f"  │  Reserved         = 0 (4 bytes){' ' * 32}│")
        print(f"  ├{'─' * 68}┤")

        # ── 2. SLOT DIRECTORY ──
        if self.slot_count > 0:
            first_slot_byte = HEADER_SIZE
            last_slot_byte = slot_dir_end - 1
            print(f"  │{'SLOT DIRECTORY (Bytes ' + str(first_slot_byte) + ' – ' + str(last_slot_byte) + ')':^68}│")
            print(f"  ├{'─' * 68}┤")

            for i in range(self.slot_count):
                slot_pos = HEADER_SIZE + i * SLOT_ENTRY_SIZE
                rec_offset, rec_length = struct.unpack_from('<HH', self.data, slot_pos)

                # Đọc nội dung record để hiển thị
                record_data = self.data[rec_offset:rec_offset + rec_length]
                record_preview = record_data.decode('utf-8', errors='replace')
                # Cắt ngắn nếu quá dài
                if len(record_preview) > 38:
                    record_preview = record_preview[:35] + "..."

                slot_bytes = f"Bytes {slot_pos}–{slot_pos + 3}"
                info = f"Slot #{i}: Offset={rec_offset}, Len={rec_length}"
                print(f"  │  {slot_bytes:<16} │ {info:<47}│")
                print(f"  │  {' ' * 16} │  └─ Data: \"{record_preview}\"{' ' * max(0, 44 - len(record_preview))}│")

            print(f"  ├{'─' * 68}┤")
        else:
            print(f"  │{'SLOT DIRECTORY (trống)':^68}│")
            print(f"  ├{'─' * 68}┤")

        # ── 3. FREE SPACE ──
        free_info = f"FREE SPACE (Bytes {slot_dir_end} – {self.free_space_ptr - 1})"
        free_detail = f"{free_space_size} bytes available"
        print(f"  │{free_info:^68}│")
        print(f"  │{free_detail:^68}│")

        # Thanh tiến trình trực quan
        bar_width = 50
        used_slots = int((slot_dir_end / PAGE_SIZE) * bar_width)
        used_data = int((data_area_size / PAGE_SIZE) * bar_width)
        used_free = bar_width - used_slots - used_data
        if used_free < 0:
            used_free = 0

        bar = "█" * used_slots + "░" * used_free + "▓" * used_data
        print(f"  │  [{bar}]  │")
        print(f"  │  {'█=Slot Dir':<16} {'░=Free Space':<17} {'▓=Data Area':<16}     │")

        print(f"  ├{'─' * 68}┤")

        # ── 4. DATA AREA ──
        if data_area_size > 0:
            data_info = f"DATA AREA (Bytes {self.free_space_ptr} – {PAGE_SIZE - 1})"
            print(f"  │{data_info:^68}│")
            print(f"  ├{'─' * 68}┤")

            # Liệt kê từng record (theo thứ tự slot)
            for i in range(self.slot_count):
                slot_pos = HEADER_SIZE + i * SLOT_ENTRY_SIZE
                rec_offset, rec_length = struct.unpack_from('<HH', self.data, slot_pos)
                record_data = self.data[rec_offset:rec_offset + rec_length].decode('utf-8', errors='replace')

                byte_range = f"Bytes {rec_offset}–{rec_offset + rec_length - 1}"
                print(f"  │  Record #{i} ({byte_range}, {rec_length}B):{' ' * max(0, 38 - len(byte_range))}│")
                # Hiển thị nội dung, cắt dòng nếu cần
                if len(record_data) > 60:
                    print(f"  │    \"{record_data[:57]}...\" │")
                else:
                    padding = 62 - len(record_data)
                    print(f"  │    \"{record_data}\"{' ' * max(0, padding)}│")
        else:
            print(f"  │{'DATA AREA (trống)':^68}│")

        print(f"  └{'─' * 68}┘")

        # ── 5. BẢNG TÓM TẮT ──
        print(f"\n  {'─' * 50}")
        print(f"  📊 TÓM TẮT PHÂN BỔ BỘ NHỚ:")
        print(f"  {'─' * 50}")
        print(f"  │ Header         : {HEADER_SIZE:>6} bytes  (Bytes 0–{HEADER_SIZE - 1})")
        print(f"  │ Slot Directory : {slot_dir_end - HEADER_SIZE:>6} bytes  "
              f"(Bytes {HEADER_SIZE}–{slot_dir_end - 1 if slot_dir_end > HEADER_SIZE else HEADER_SIZE})")
        print(f"  │ Free Space     : {free_space_size:>6} bytes  "
              f"(Bytes {slot_dir_end}–{self.free_space_ptr - 1})")
        print(f"  │ Data Area      : {data_area_size:>6} bytes  "
              f"(Bytes {self.free_space_ptr}–{PAGE_SIZE - 1})")
        print(f"  │ {'─' * 48}")
        print(f"  │ TOTAL          : {PAGE_SIZE:>6} bytes")
        usage_pct = ((HEADER_SIZE + (slot_dir_end - HEADER_SIZE) + data_area_size) / PAGE_SIZE) * 100
        print(f"  │ Usage          : {usage_pct:>6.2f}%")
        print(f"  {'─' * 50}")
        print()

    # ========================================================================
    # SAVE – Xuất Page ra file nhị phân
    # ========================================================================

    def save_to_bin(self, filename: str):
        """
        Xuất toàn bộ 4096 bytes của Page ra file nhị phân (.bin).

        Args:
            filename: Đường dẫn file đích (ví dụ: 'page_demo.bin').
        """
        with open(filename, 'wb') as f:
            f.write(self.data)

        file_size = os.path.getsize(filename)
        print(f"  💾 Đã lưu Page vào '{filename}' ({file_size} bytes)")


# ============================================================================
# DEMO – Kịch bản minh họa
# ============================================================================

def main():
    print()
    print("╔" + "═" * 70 + "╗")
    print("║" + " BÀI TẬP 02: MÔ PHỎNG SLOTTED PAGE – VARIABLE-LENGTH RECORDS ".center(70) + "║")
    print("╚" + "═" * 70 + "╝")

    # ── Bước 1: Khởi tạo Page ──
    print("\n" + "─" * 72)
    print("  🔧 KHỞI TẠO PAGE (ID = 1)")
    print("─" * 72)
    page = SlottedPage(page_id=1)
    print(f"  → Page Size      = {PAGE_SIZE} bytes")
    print(f"  → Header Size    = {HEADER_SIZE} bytes")
    print(f"  → Slot Entry     = {SLOT_ENTRY_SIZE} bytes/slot")
    print(f"  → Free Space Ptr = {page.free_space_ptr} (ban đầu = cuối trang)")

    # Visualize trang trống
    page.visualize()

    # ── Bước 2: Chuẩn bị dữ liệu 3 sinh viên với độ dài khác nhau ──
    students = [
        (1, "Le Van An", "an@gmail.com"),                                    # Ngắn
        (2, "Nguyen Thi Bich Ngoc", "bichngoc.nguyen2024@university.edu"),   # Trung bình
        (3, "Tran Quang Huy Hoang Phuc", "huyhoangphuc.tran@corporation.enterprise.co.jp"),  # Dài
    ]

    # ── Bước 3: Chèn từng sinh viên và visualize ──
    for i, (sid, name, email) in enumerate(students):
        print("\n" + "─" * 72)
        print(f"  📝 CHÈN SINH VIÊN #{i + 1}: {name}")
        print("─" * 72)

        # Serialize sinh viên → bytes
        record_bytes = SlottedPage.serialize_student(sid, name, email)
        print(f"  → Serialized: {record_bytes}")
        print(f"  → Kích thước : {len(record_bytes)} bytes")
        print()

        # Chèn vào Page
        slot_num = page.insert_record(record_bytes)

        # Visualize sau mỗi lần chèn
        page.visualize()

    # ── Bước 4: Đọc lại các record để xác minh ──
    print("\n" + "─" * 72)
    print("  🔍 XÁC MINH – ĐỌC LẠI CÁC RECORD")
    print("─" * 72)
    for i in range(page.slot_count):
        raw = page.read_record(i)
        decoded = raw.decode('utf-8')
        parts = decoded.split('|')
        print(f"  Slot #{i}: ID={parts[0]}, Name=\"{parts[1]}\", Email=\"{parts[2]}\"")

    # ── Bước 5: Xuất file .bin ──
    print("\n" + "─" * 72)
    print("  📦 XUẤT FILE NHỊ PHÂN")
    print("─" * 72)
    bin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "page_demo.bin")
    page.save_to_bin(bin_path)

    print("\n" + "─" * 72)
    print("  ✅ HOÀN TẤT DEMO!")
    print("─" * 72)
    print()


if __name__ == "__main__":
    main()
