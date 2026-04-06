"""
=============================================================================
BÀI TẬP 02 – MÔ PHỎNG STORAGE MANAGEMENT (BƯỚC 3)
Chủ đề: Heap File Manager – Quản lý Dataset lớn (500.000+ bản ghi)
=============================================================================

Mở rộng từ Bước 1 (SlottedPage) và Bước 2 (Delete & Compact), bước này
xây dựng hệ thống Heap File hoàn chỉnh có thể:

  1. HeapFileManager  – Quản lý file nhị phân chứa nhiều Slotted Page
  2. Data Generator   – Tạo 500.000 bản ghi Student giả lập (CSV)
  3. Bulk Load        – Nạp streaming từ CSV vào Heap File
  4. Benchmark        – Đo thời gian Insert, Random Access, Persistence

Kiến trúc Heap File:
─────────────────────────────────────────────────────────
  database.db  (file nhị phân)
  ┌─────────────┬─────────────┬─────────────┬─────────┐
  │   Page 0    │   Page 1    │   Page 2    │  ...    │
  │  (4096 B)   │  (4096 B)   │  (4096 B)   │         │
  └─────────────┴─────────────┴─────────────┴─────────┘
  Offset:  0        4096         8192       ...

  Mỗi Page là một Slotted Page với cấu trúc từ Bước 1 & 2.
  Truy cập Page N: file.seek(N * 4096)
  
  Record Pointer = (PageID, SlotID) → duy nhất xác định 1 bản ghi
─────────────────────────────────────────────────────────

Cơ chế nạp dữ liệu theo luồng (Streaming):
  - Đọc CSV từng dòng bằng csv.reader (không load toàn bộ vào RAM)
  - Giữ tối đa 1 Page trong bộ nhớ đệm (Page Cache)
  - Ghi page xuống đĩa khi đầy, rồi tạo page mới
  → RAM usage ≈ O(1), không phụ thuộc số bản ghi

Tính nhất quán (Consistency):
  - Mọi Page đều ghi đầy đủ 4096 bytes xuống file
  - Header chứa page_id, slot_count, free_space_ptr
  - Có thể tắt chương trình → mở lại → đọc tiếp các Page cũ
=============================================================================
"""

import struct
import os
import csv
import time
import random
import string

# ============================================================================
# Import từ Bước 2 – Tái sử dụng SlottedPage và các hằng số
# ============================================================================

from slotted_page_step2 import (
    SlottedPage,
    PAGE_SIZE,
    HEADER_SIZE,
    SLOT_ENTRY_SIZE,
    DELETED_MARKER
)


# ============================================================================
# CLASS: HeapFileManager
# ============================================================================

class HeapFileManager:
    """
    Quản lý một Heap File – file nhị phân chứa chuỗi các Slotted Page.

    Heap File là cấu trúc lưu trữ đơn giản nhất trong DBMS:
    - Các Page xếp nối tiếp nhau trong file
    - Insert: luôn thêm vào Page cuối (hoặc tạo Page mới)
    - Truy cập: theo (page_id, slot_id)
    - Không có Index → tìm kiếm tuần tự (Full Table Scan)

    Attributes:
        db_path:     Đường dẫn file nhị phân (.db)
        total_pages: Tổng số Page hiện có trong file
        stats:       Thống kê I/O (pages read/written, compactions, ...)
    """

    def __init__(self, db_path: str):
        """
        Khởi tạo HeapFileManager.

        Args:
            db_path: Đường dẫn tới file nhị phân (ví dụ: 'database.db').
                     Nếu file đã tồn tại → đọc lại metadata.
                     Nếu chưa tồn tại → sẽ tạo khi gọi open().
        """
        self.db_path = db_path
        self.total_pages = 0
        self._file = None

        # ── Page Cache ──
        # Giữ 1 Page trong bộ nhớ đệm để tránh đọc/ghi đĩa liên tục.
        # Khi bulk load, hầu hết insert đều vào Page cuối → cache hit rate ≈ 100%.
        self._cached_page = None
        self._cached_page_id = -1
        self._cached_dirty = False

        # ── I/O Statistics ──
        self.stats = {
            'pages_read': 0,
            'pages_written': 0,
            'compactions': 0,
            'new_pages_created': 0,
            'records_inserted': 0,
        }

        # Kiểm tra file đã tồn tại → xác định số Page
        if os.path.exists(db_path):
            file_size = os.path.getsize(db_path)
            self.total_pages = file_size // PAGE_SIZE

    # ========================================================================
    # CONTEXT MANAGER – Mở / Đóng file an toàn
    # ========================================================================

    def open(self):
        """
        Mở file nhị phân. Tạo file mới nếu chưa tồn tại.
        Sử dụng mode 'r+b' (read+write binary) để hỗ trợ seek().
        """
        if not os.path.exists(self.db_path):
            # Tạo file trống
            with open(self.db_path, 'wb'):
                pass
        self._file = open(self.db_path, 'r+b')
        return self

    def close(self):
        """Đóng file, đảm bảo flush dữ liệu trước khi đóng."""
        self._flush_cache()
        if self._file:
            self._file.close()
            self._file = None

    def __enter__(self):
        """Hỗ trợ 'with HeapFileManager(...) as mgr:'"""
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ========================================================================
    # PAGE I/O – Đọc / Ghi Page từ đĩa
    # ========================================================================

    def _flush_cache(self):
        """Ghi Page hiện tại trong cache xuống đĩa nếu đã thay đổi (dirty)."""
        if self._cached_dirty and self._cached_page is not None:
            self._write_page_raw(self._cached_page_id, self._cached_page)
            self._cached_dirty = False

    def _read_page(self, page_id: int) -> SlottedPage:
        """
        Đọc một Page từ file nhị phân.

        Cơ chế:
        ─────────────────────────────────────────────────────
        1. Kiểm tra Page Cache → nếu hit thì trả về ngay
        2. Flush cache hiện tại nếu dirty
        3. file.seek(page_id * 4096)  → nhảy tới vị trí Page
        4. file.read(4096)            → đọc đúng 4KB
        5. Tạo đối tượng SlottedPage từ raw bytes
        6. Gọi _read_header() để parse metadata
        7. Cập nhật cache
        ─────────────────────────────────────────────────────

        Args:
            page_id: ID của Page cần đọc (0-indexed).

        Returns:
            Đối tượng SlottedPage đã được nạp dữ liệu.

        Raises:
            IOError: Nếu không đọc đủ 4096 bytes.
        """
        # Cache hit → trả về ngay, không cần I/O
        if self._cached_page_id == page_id:
            return self._cached_page

        # Flush cache hiện tại trước khi đọc page mới
        self._flush_cache()

        # Seek tới vị trí của Page trong file
        # Mỗi Page chiếm đúng PAGE_SIZE bytes, xếp nối tiếp nhau
        self._file.seek(page_id * PAGE_SIZE)
        raw = self._file.read(PAGE_SIZE)

        if len(raw) < PAGE_SIZE:
            raise IOError(
                f"[LỖI] Đọc Page #{page_id} không đủ: "
                f"cần {PAGE_SIZE} bytes, chỉ đọc được {len(raw)} bytes."
            )

        # Tạo đối tượng SlottedPage mà KHÔNG gọi __init__
        # (vì __init__ sẽ tạo Page trống, ta muốn nạp dữ liệu từ đĩa)
        page = SlottedPage.__new__(SlottedPage)
        page.data = bytearray(raw)
        page._read_header()  # Parse header → page_id, slot_count, free_space_ptr

        # Cập nhật cache
        self._cached_page = page
        self._cached_page_id = page_id
        self._cached_dirty = False
        self.stats['pages_read'] += 1

        return page

    def _write_page_raw(self, page_id: int, page: SlottedPage):
        """
        Ghi ngược dữ liệu từ đối tượng SlottedPage xuống file nhị phân.

        Cơ chế:
        ─────────────────────────────────────────────────────
        1. file.seek(page_id * 4096)  → nhảy tới vị trí Page
        2. file.write(page.data)      → ghi đúng 4096 bytes
        3. file.flush()               → đảm bảo dữ liệu xuống đĩa
        ─────────────────────────────────────────────────────

        Lưu ý: Nếu page_id nằm ngoài file hiện tại (Page mới),
        Python sẽ tự động mở rộng file khi write.

        Args:
            page_id: ID của Page cần ghi.
            page:    Đối tượng SlottedPage chứa dữ liệu.
        """
        self._file.seek(page_id * PAGE_SIZE)
        self._file.write(page.data)
        self._file.flush()
        self.stats['pages_written'] += 1

    def _write_page(self, page_id: int, page: SlottedPage):
        """Ghi Page – nếu là cached page thì chỉ đánh dấu dirty."""
        if self._cached_page_id == page_id:
            self._cached_dirty = True
        else:
            self._write_page_raw(page_id, page)

    # ========================================================================
    # SILENT OPERATIONS – Thao tác không in (cho Bulk Load hiệu suất cao)
    # ========================================================================
    # Các phương thức SlottedPage gốc (insert_record, compact_page) đều in
    # ra console. Khi nạp 500.000 bản ghi, hàng triệu lệnh print sẽ cực kỳ
    # chậm. Do đó, ta tạo các phiên bản "silent" chỉ thực hiện logic thuần túy.

    @staticmethod
    def _insert_silent(page: SlottedPage, data_bytes: bytes) -> int:
        """
        Chèn record vào Page WITHOUT printing.
        Logic giống hệt SlottedPage.insert_record() nhưng bỏ print.

        Returns:
            Slot number nếu thành công, -1 nếu không đủ chỗ.
        """
        record_len = len(data_bytes)
        slot_dir_end = HEADER_SIZE + (page.slot_count * SLOT_ENTRY_SIZE)
        new_slot_dir_end = slot_dir_end + SLOT_ENTRY_SIZE
        new_record_offset = page.free_space_ptr - record_len

        if new_slot_dir_end > new_record_offset:
            return -1

        page.data[new_record_offset:new_record_offset + record_len] = data_bytes
        struct.pack_into('<HH', page.data, slot_dir_end,
                         new_record_offset, record_len)

        slot_number = page.slot_count
        page.slot_count += 1
        page.free_space_ptr = new_record_offset
        page._write_header()

        return slot_number

    @staticmethod
    def _compact_silent(page: SlottedPage):
        """
        Dồn trang WITHOUT printing.
        Logic giống hệt SlottedPage.compact_page() nhưng bỏ print.
        """
        # Thu thập record còn sống
        live_records = []
        for sid in range(page.slot_count):
            offset, length = page._read_slot(sid)
            if offset != DELETED_MARKER:
                live_records.append((sid, bytes(page.data[offset:offset + length])))

        # Xóa sạch Data Area
        slot_dir_end = HEADER_SIZE + (page.slot_count * SLOT_ENTRY_SIZE)
        page.data[slot_dir_end:PAGE_SIZE] = b'\x00' * (PAGE_SIZE - slot_dir_end)

        # Ghi ngược lại từ cuối Page
        write_ptr = PAGE_SIZE
        for sid, rec_data in live_records:
            new_offset = write_ptr - len(rec_data)
            page.data[new_offset:new_offset + len(rec_data)] = rec_data
            page._write_slot(sid, new_offset, len(rec_data))
            write_ptr = new_offset

        # Reset length cho các slot đã xóa
        for sid in range(page.slot_count):
            offset, length = page._read_slot(sid)
            if offset == DELETED_MARKER and length > 0:
                page._write_slot(sid, DELETED_MARKER, 0)

        page.free_space_ptr = write_ptr
        page._write_header()

    # ========================================================================
    # INSERT RECORD – Chèn bản ghi vào Heap File
    # ========================================================================

    def insert_record(self, record_bytes: bytes) -> tuple:
        """
        Chèn một bản ghi vào Heap File.

        Thuật toán:
        ─────────────────────────────────────────────────────────
        1. Nếu chưa có Page nào → tạo Page đầu tiên (Page 0)
        2. Lấy Page cuối cùng (từ cache hoặc từ đĩa)
        3. Thử chèn vào Page cuối:
           a. Nếu thành công → trả về (page_id, slot_id)
           b. Nếu thất bại (hết chỗ liên tục):
              - Kiểm tra có lỗ hổng không (total > contiguous)
              - Nếu có → compact_page() rồi thử lại
              - Nếu vẫn thất bại → tạo Page MỚI, chèn vào đó
        ─────────────────────────────────────────────────────────

        Args:
            record_bytes: Dữ liệu bản ghi đã serialize (bytes).

        Returns:
            Tuple (page_id, slot_id): Record Pointer duy nhất.

        Raises:
            ValueError: Nếu record lớn hơn dung lượng 1 Page.
        """
        # Kiểm tra record có vừa 1 Page không
        max_record_size = PAGE_SIZE - HEADER_SIZE - SLOT_ENTRY_SIZE
        if len(record_bytes) > max_record_size:
            raise ValueError(
                f"Record quá lớn ({len(record_bytes)} bytes), "
                f"tối đa {max_record_size} bytes/record."
            )

        # Nếu chưa có Page nào → tạo Page đầu tiên
        if self.total_pages == 0:
            page = SlottedPage(page_id=0)
            self._cached_page = page
            self._cached_page_id = 0
            self._cached_dirty = True
            self.total_pages = 1
            self.stats['new_pages_created'] += 1

        # ── Lấy Page cuối cùng ──
        last_pid = self.total_pages - 1
        page = self._read_page(last_pid)

        # ── Thử chèn ──
        slot = self._insert_silent(page, record_bytes)
        if slot != -1:
            self._cached_dirty = True
            self.stats['records_inserted'] += 1
            return (last_pid, slot)

        # ── Page đầy → thử compact nếu có lỗ hổng ──
        # Kiểm tra: tổng free space > contiguous free space?
        # Nếu có → có lỗ hổng từ record đã xóa → compact có thể giúp
        total_free = page.get_total_free_space()
        contiguous_free = page.get_contiguous_free_space()

        if total_free > contiguous_free and total_free >= len(record_bytes):
            self._compact_silent(page)
            self.stats['compactions'] += 1

            slot = self._insert_silent(page, record_bytes)
            if slot != -1:
                self._cached_dirty = True
                self.stats['records_inserted'] += 1
                return (last_pid, slot)

        # ── Compact không đủ hoặc không có lỗ hổng → tạo Page mới ──
        self._flush_cache()  # Ghi Page cũ xuống đĩa trước

        new_pid = self.total_pages
        new_page = SlottedPage(page_id=new_pid)

        slot = self._insert_silent(new_page, record_bytes)
        if slot == -1:
            raise ValueError(
                f"Không thể chèn record {len(record_bytes)} bytes vào Page trống!"
            )

        self._cached_page = new_page
        self._cached_page_id = new_pid
        self._cached_dirty = True
        self.total_pages += 1
        self.stats['new_pages_created'] += 1
        self.stats['records_inserted'] += 1

        return (new_pid, slot)

    # ========================================================================
    # GET RECORD – Truy xuất bản ghi
    # ========================================================================

    def get_record(self, page_id: int, slot_id: int) -> bytes:
        """
        Truy xuất một bản ghi cụ thể bằng Record Pointer (page_id, slot_id).

        Cơ chế:
        ─────────────────────────────────────────────────────
        1. Đọc Page từ đĩa (hoặc cache): _read_page(page_id)
        2. Đọc Slot Entry: _read_slot(slot_id)
        3. Kiểm tra slot chưa bị xóa (offset != DELETED_MARKER)
        4. Trích xuất record data từ Data Area
        ─────────────────────────────────────────────────────

        Args:
            page_id: ID của Page chứa bản ghi.
            slot_id: ID của Slot trong Page.

        Returns:
            Dữ liệu bản ghi (bytes).

        Raises:
            IndexError: page_id hoặc slot_id ngoài phạm vi.
            ValueError: Bản ghi đã bị xóa.
        """
        if page_id < 0 or page_id >= self.total_pages:
            raise IndexError(f"Page #{page_id} không tồn tại. "
                             f"Tổng: {self.total_pages} pages.")

        page = self._read_page(page_id)

        if slot_id < 0 or slot_id >= page.slot_count:
            raise IndexError(f"Slot #{slot_id} không tồn tại trong Page #{page_id}. "
                             f"Tổng: {page.slot_count} slots.")

        offset, length = page._read_slot(slot_id)
        if offset == DELETED_MARKER:
            raise ValueError(f"Record ({page_id}, {slot_id}) đã bị xóa.")

        return bytes(page.data[offset:offset + length])

    # ========================================================================
    # SCAN – Duyệt toàn bộ bản ghi (Full Table Scan)
    # ========================================================================

    def scan_all_records(self):
        """
        Generator: duyệt tuần tự tất cả bản ghi trong Heap File.
        Trả về (page_id, slot_id, record_bytes) cho mỗi bản ghi còn sống.

        Sử dụng pattern Generator/yield để tiết kiệm RAM:
        chỉ load 1 Page tại một thời điểm.
        """
        for pid in range(self.total_pages):
            page = self._read_page(pid)
            for sid in range(page.slot_count):
                offset, length = page._read_slot(sid)
                if offset != DELETED_MARKER:
                    yield (pid, sid, bytes(page.data[offset:offset + length]))

    # ========================================================================
    # FLUSH – Đảm bảo dữ liệu được ghi xuống đĩa
    # ========================================================================

    def flush(self):
        """Flush cache và file buffer xuống đĩa."""
        self._flush_cache()
        if self._file:
            self._file.flush()

    # ========================================================================
    # INFO – Thống kê trạng thái
    # ========================================================================

    def print_stats(self):
        """In thống kê chi tiết về HeapFile và I/O."""
        file_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        file_mb = file_size / (1024 * 1024)

        print(f"\n  {'=' * 60}")
        print(f"  HEAP FILE STATISTICS")
        print(f"  {'=' * 60}")
        print(f"  File             : {self.db_path}")
        print(f"  File size        : {file_size:,} bytes ({file_mb:.2f} MB)")
        print(f"  Total pages      : {self.total_pages:,}")
        print(f"  Page size        : {PAGE_SIZE:,} bytes")
        print(f"  {'─' * 60}")
        print(f"  Records inserted : {self.stats['records_inserted']:,}")
        print(f"  Pages read       : {self.stats['pages_read']:,}")
        print(f"  Pages written    : {self.stats['pages_written']:,}")
        print(f"  Pages created    : {self.stats['new_pages_created']:,}")
        print(f"  Compactions      : {self.stats['compactions']:,}")
        print(f"  {'=' * 60}\n")


# ============================================================================
# DATA GENERATOR – Tạo dữ liệu Student giả lập
# ============================================================================

# Danh sách tên Việt Nam để tạo dữ liệu thực tế
FIRST_NAMES = [
    "Nguyen", "Tran", "Le", "Pham", "Hoang", "Vu", "Vo", "Dang", "Bui", "Do",
    "Ho", "Ngo", "Duong", "Ly", "Trinh", "Mai", "Huynh", "Dinh", "Lam", "Dao",
    "Ta", "Luong", "Quach", "Chau", "Ha", "Phan", "Truong", "La", "Tong", "Cao"
]

MIDDLE_NAMES = [
    "Van", "Thi", "Duc", "Minh", "Quang", "Thanh", "Ngoc", "Thu", "Huu", "Dinh",
    "Xuan", "Hong", "Bao", "Anh", "Kim", "Tuan", "Phuong", "Trung", "Hai", "Nhat",
    "Duy", "Khanh", "Hoai", "Gia", "Thien", "Yen", "My", "Cam", "Tuyet", "Thuy"
]

GIVEN_NAMES = [
    "An", "Binh", "Cuong", "Dung", "Huy", "Khanh", "Linh", "Mai", "Nam", "Phat",
    "Quan", "Son", "Tam", "Uyen", "Vy", "Yen", "Phuc", "Dat", "Long", "Tien",
    "Thao", "Nhi", "Trang", "Ha", "Hung", "Khoa", "Lam", "Minh", "Phu", "Tai"
]

CLASS_NAMES = [
    "CNTT01", "CNTT02", "CNTT03", "KHMT01", "KHMT02", "KHMT03",
    "HTTT01", "HTTT02", "KTPM01", "KTPM02", "KTPM03",
    "TTMMT01", "TTMMT02", "ATTT01", "ATTT02", "TGMT01", "TGMT02"
]

EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com",
    "university.edu.vn", "student.edu.vn",
    "company.co.jp", "enterprise.com.au",
    "email.vn", "mail.com"
]


def generate_dataset(filepath: str, num_records: int = 500_000):
    """
    Tạo file CSV chứa dữ liệu Student giả lập.

    Bảng: Student(student_id, full_name, class_name, email, phone)

    Đặc điểm dữ liệu:
    - full_name: 2-4 từ (Variable-Length), 10-40 bytes
    - email: tên + số ngẫu nhiên + domain (Variable-Length), 20-60 bytes
    - phone: 10-11 số
    → Mỗi record sau serialize: khoảng 60-120 bytes (Variable-Length)

    Args:
        filepath:    Đường dẫn file CSV đầu ra.
        num_records: Số bản ghi cần tạo (mặc định 500.000).
    """
    print(f"\n  Generating {num_records:,} student records...")
    print(f"  Output: {filepath}")

    start_time = time.time()

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['student_id', 'full_name', 'class_name', 'email', 'phone'])

        for i in range(1, num_records + 1):
            # ── full_name: 2-4 phần (Variable-Length) ──
            # Số lượng middle name ngẫu nhiên → tên dài ngắn khác nhau
            num_middle = random.randint(0, 2)
            name_parts = [random.choice(FIRST_NAMES)]
            for _ in range(num_middle):
                name_parts.append(random.choice(MIDDLE_NAMES))
            name_parts.append(random.choice(GIVEN_NAMES))
            full_name = " ".join(name_parts)

            # ── class_name ──
            class_name = random.choice(CLASS_NAMES)

            # ── email (Variable-Length) ──
            # Tạo email từ tên + số ngẫu nhiên → độ dài thay đổi
            email_user = full_name.lower().replace(" ", ".")
            email_suffix = str(random.randint(1, 9999))
            email = f"{email_user}{email_suffix}@{random.choice(EMAIL_DOMAINS)}"

            # ── phone ──
            phone = f"0{random.randint(3, 9)}{random.randint(10000000, 99999999)}"

            writer.writerow([i, full_name, class_name, email, phone])

            # Progress bar mỗi 100.000 bản ghi
            if i % 100_000 == 0:
                elapsed = time.time() - start_time
                pct = (i / num_records) * 100
                rate = i / elapsed if elapsed > 0 else 0
                print(f"    [{pct:5.1f}%] {i:>10,} / {num_records:,} records "
                      f"({elapsed:.1f}s, {rate:,.0f} rec/s)")

    elapsed = time.time() - start_time
    file_size = os.path.getsize(filepath)
    print(f"\n  Done! {num_records:,} records generated in {elapsed:.2f}s")
    print(f"  CSV file size: {file_size / (1024 * 1024):.2f} MB")


# ============================================================================
# SERIALIZATION – Chuyển đổi dữ liệu Student thành bytes
# ============================================================================

def serialize_student(student_id, full_name, class_name, email, phone):
    """
    Serialize bản ghi Student thành chuỗi bytes.

    Format: "id|full_name|class_name|email|phone"
    Encode: UTF-8

    Ví dụ: "1|Nguyen Van An|CNTT01|nguyen.van.an123@gmail.com|0912345678"
    → bytes object, độ dài 50-100 bytes (Variable-Length)
    """
    record = f"{student_id}|{full_name}|{class_name}|{email}|{phone}"
    return record.encode('utf-8')


def deserialize_student(record_bytes: bytes) -> dict:
    """
    Deserialize bytes thành dictionary Student.

    Args:
        record_bytes: Dữ liệu record đã serialize.

    Returns:
        Dict với keys: student_id, full_name, class_name, email, phone
    """
    parts = record_bytes.decode('utf-8').split('|')
    return {
        'student_id': int(parts[0]),
        'full_name': parts[1],
        'class_name': parts[2],
        'email': parts[3],
        'phone': parts[4]
    }


# ============================================================================
# BULK LOAD – Nạp dữ liệu từ CSV vào Heap File
# ============================================================================

def bulk_load(manager: HeapFileManager, csv_path: str):
    """
    Nạp dữ liệu từ file CSV vào HeapFileManager theo luồng (streaming).

    Cơ chế Streaming:
    ─────────────────────────────────────────────────────────
    - Đọc CSV từng dòng bằng csv.reader (KHÔNG đọc toàn bộ file vào RAM)
    - Mỗi dòng → serialize → insert_record()
    - HeapFileManager tự quản lý Page: đầy → tạo mới
    - RAM usage ≈ O(1) bất kể số bản ghi là 500K hay 10M
    ─────────────────────────────────────────────────────────

    Args:
        manager:  HeapFileManager đã mở.
        csv_path: Đường dẫn file CSV nguồn.
    """
    print(f"\n  {'=' * 60}")
    print(f"  BULK LOAD: {csv_path} → {manager.db_path}")
    print(f"  {'=' * 60}")

    start_time = time.time()
    count = 0
    last_report_time = start_time

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Bỏ qua header row

        for row in reader:
            student_id, full_name, class_name, email, phone = row

            # Serialize bản ghi thành bytes (Variable-Length)
            record_bytes = serialize_student(
                student_id, full_name, class_name, email, phone
            )

            # Chèn vào Heap File
            manager.insert_record(record_bytes)
            count += 1

            # Progress report mỗi 50.000 bản ghi
            if count % 50_000 == 0:
                now = time.time()
                elapsed = now - start_time
                interval = now - last_report_time
                rate = count / elapsed if elapsed > 0 else 0
                interval_rate = 50_000 / interval if interval > 0 else 0

                print(f"    [{count:>10,} records] "
                      f"Elapsed: {elapsed:7.2f}s | "
                      f"Avg: {rate:>9,.0f} rec/s | "
                      f"Current: {interval_rate:>9,.0f} rec/s | "
                      f"Pages: {manager.total_pages:,}")

                last_report_time = now

    # Đảm bảo dữ liệu cuối cùng được ghi xuống đĩa
    manager.flush()
    elapsed = time.time() - start_time

    # ── Báo cáo kết quả ──
    file_size = os.path.getsize(manager.db_path)
    file_mb = file_size / (1024 * 1024)
    avg_rate = count / elapsed if elapsed > 0 else 0

    print(f"\n  {'─' * 60}")
    print(f"  BULK LOAD COMPLETE!")
    print(f"  {'─' * 60}")
    print(f"  Total records loaded : {count:>12,}")
    print(f"  Total time           : {elapsed:>12.2f} seconds")
    print(f"  Average speed        : {avg_rate:>12,.0f} records/second")
    print(f"  Total pages          : {manager.total_pages:>12,}")
    print(f"  Database file size   : {file_mb:>12.2f} MB ({file_size:,} bytes)")
    print(f"  Avg record size      : {file_size / count if count else 0:>12.1f} bytes/record")
    print(f"  Avg records per page : {count / manager.total_pages if manager.total_pages else 0:>12.1f}")
    print(f"  {'─' * 60}")

    return count, elapsed


# ============================================================================
# BENCHMARK – Đo hiệu năng truy xuất ngẫu nhiên
# ============================================================================

def benchmark_random_access(manager: HeapFileManager, num_queries: int = 1000,
                            record_pointers: list = None):
    """
    Đo thời gian phản hồi (Latency) khi truy xuất ngẫu nhiên.

    Cơ chế:
    - Chọn ngẫu nhiên num_queries cặp (page_id, slot_id)
    - Gọi get_record() → đo thời gian mỗi query
    - Tính min/max/avg latency

    Args:
        manager:         HeapFileManager đã mở.
        num_queries:     Số lần truy vấn.
        record_pointers: Danh sách (page_id, slot_id) để test.
                         Nếu None → tạo ngẫu nhiên.
    """
    print(f"\n  {'=' * 60}")
    print(f"  RANDOM ACCESS BENCHMARK ({num_queries:,} queries)")
    print(f"  {'=' * 60}")

    # Tạo danh sách các Record Pointer ngẫu nhiên để test
    if record_pointers is None:
        record_pointers = []
        # Sample các page ngẫu nhiên, slot 0 (luôn tồn tại)
        for _ in range(num_queries):
            pid = random.randint(0, manager.total_pages - 1)
            record_pointers.append((pid, 0))

    latencies = []
    success = 0
    errors = 0

    for pid, sid in record_pointers:
        try:
            t_start = time.perf_counter()
            data = manager.get_record(pid, sid)
            t_end = time.perf_counter()

            latency_us = (t_end - t_start) * 1_000_000  # microseconds
            latencies.append(latency_us)
            success += 1
        except (IndexError, ValueError):
            errors += 1

    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        # Percentile P50, P95, P99
        sorted_lat = sorted(latencies)
        p50 = sorted_lat[len(sorted_lat) // 2]
        p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
        p99 = sorted_lat[int(len(sorted_lat) * 0.99)]

        print(f"\n  Results:")
        print(f"  {'─' * 50}")
        print(f"  Successful queries : {success:>10,}")
        print(f"  Failed queries     : {errors:>10,}")
        print(f"  {'─' * 50}")
        print(f"  Latency (microseconds):")
        print(f"    Min              : {min_lat:>10.1f} us")
        print(f"    Avg              : {avg_lat:>10.1f} us")
        print(f"    P50 (Median)     : {p50:>10.1f} us")
        print(f"    P95              : {p95:>10.1f} us")
        print(f"    P99              : {p99:>10.1f} us")
        print(f"    Max              : {max_lat:>10.1f} us")
        print(f"  {'─' * 50}")
        print(f"  Throughput         : {1_000_000 / avg_lat:>10,.0f} reads/second")
        print(f"  {'=' * 60}")
    else:
        print("  No successful queries.")


# ============================================================================
# PERSISTENCE TEST – Kiểm tra tính nhất quán sau khi đóng/mở file
# ============================================================================

def test_persistence(db_path: str, sample_pointers: list):
    """
    Kiểm tra tính nhất quán: đóng file → mở lại → đọc bản ghi cũ.

    Đây là yêu cầu quan trọng: dữ liệu đã ghi phải tồn tại sau khi
    tắt chương trình. HeapFileManager chỉ dựa vào file nhị phân,
    không cần metadata ngoài → mở lại là đọc được ngay.

    Args:
        db_path:         Đường dẫn file .db
        sample_pointers: Danh sách (page_id, slot_id) để kiểm tra.
    """
    print(f"\n  {'=' * 60}")
    print(f"  PERSISTENCE TEST")
    print(f"  {'=' * 60}")
    print(f"  Mở lại file: {db_path}")

    # Tạo HeapFileManager MỚI từ file đã có trên đĩa
    with HeapFileManager(db_path) as mgr:
        print(f"  Total pages detected: {mgr.total_pages:,}")
        print(f"\n  Verifying {len(sample_pointers)} sample records...")

        ok = 0
        fail = 0
        for pid, sid in sample_pointers:
            try:
                data = mgr.get_record(pid, sid)
                student = deserialize_student(data)
                ok += 1
            except Exception as e:
                fail += 1
                print(f"    [FAIL] ({pid}, {sid}): {e}")

        print(f"\n  Results: {ok} OK, {fail} FAIL out of {len(sample_pointers)}")
        if fail == 0:
            print(f"  PERSISTENCE TEST PASSED! Data is consistent after reopen.")
        else:
            print(f"  PERSISTENCE TEST FAILED! {fail} records could not be read.")

        # In 5 mẫu bản ghi để minh họa
        print(f"\n  Sample records from reopened file:")
        print(f"  {'─' * 60}")
        for i, (pid, sid) in enumerate(sample_pointers[:5]):
            try:
                data = mgr.get_record(pid, sid)
                student = deserialize_student(data)
                print(f"    ({pid:>5}, {sid:>3}) → ID={student['student_id']}, "
                      f"Name=\"{student['full_name']}\", "
                      f"Class={student['class_name']}")
            except Exception as e:
                print(f"    ({pid:>5}, {sid:>3}) → Error: {e}")

    print(f"  {'=' * 60}\n")


# ============================================================================
# DEMO – Kịch bản minh họa Bước 3
# ============================================================================

def main():
    print()
    print("=" * 72)
    print("  STEP 3: HEAP FILE MANAGER")
    print("  Quan ly Dataset lon (500.000+ ban ghi)")
    print("=" * 72)

    # ── Cấu hình ──
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "data_source.csv")
    db_path = os.path.join(base_dir, "database.db")
    NUM_RECORDS = 500_000    # Số bản ghi cần tạo
    NUM_QUERIES = 1_000      # Số lần truy vấn ngẫu nhiên

    # Xóa file cũ nếu có (để demo từ đầu)
    for f in [csv_path, db_path]:
        if os.path.exists(f):
            os.remove(f)
            print(f"  Cleaned up: {f}")

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1: Tạo Dataset
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "-" * 72)
    print("  PHASE 1: GENERATE DATASET")
    print("-" * 72)
    generate_dataset(csv_path, NUM_RECORDS)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2: Bulk Load vào Heap File
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "-" * 72)
    print("  PHASE 2: BULK LOAD INTO HEAP FILE")
    print("-" * 72)

    # Lưu danh sách Record Pointer để dùng cho benchmark và persistence test
    sample_pointers = []

    with HeapFileManager(db_path) as mgr:
        count, elapsed = bulk_load(mgr, csv_path)
        mgr.print_stats()

        # Thu thập mẫu Record Pointer từ các Page ngẫu nhiên
        random.seed(42)  # Reproducible sampling
        for _ in range(100):
            pid = random.randint(0, mgr.total_pages - 1)
            sample_pointers.append((pid, 0))

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3: Benchmark truy xuất ngẫu nhiên
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "-" * 72)
    print("  PHASE 3: RANDOM ACCESS BENCHMARK")
    print("-" * 72)

    with HeapFileManager(db_path) as mgr:
        # Tạo danh sách truy vấn ngẫu nhiên
        random.seed(123)
        query_pointers = []
        for _ in range(NUM_QUERIES):
            pid = random.randint(0, mgr.total_pages - 1)
            query_pointers.append((pid, 0))

        benchmark_random_access(mgr, NUM_QUERIES, query_pointers)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 4: Kiểm tra tính nhất quán (Persistence Test)
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "-" * 72)
    print("  PHASE 4: PERSISTENCE TEST (REOPEN & VERIFY)")
    print("-" * 72)

    test_persistence(db_path, sample_pointers)

    # ═══════════════════════════════════════════════════════════════════
    # TỔNG KẾT
    # ═══════════════════════════════════════════════════════════════════
    file_size = os.path.getsize(db_path)
    file_mb = file_size / (1024 * 1024)

    print("\n" + "=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    print(f"""
  1. DATA GENERATION:
     - {NUM_RECORDS:,} student records with variable-length fields
     - CSV file: {os.path.getsize(csv_path) / (1024*1024):.2f} MB

  2. HEAP FILE:
     - Database: {db_path}
     - Size: {file_mb:.2f} MB ({file_size:,} bytes)
     - Organized as sequential Slotted Pages (4KB each)

  3. ARCHITECTURE:
     +------------------+
     |  CSV Data Source  |  (streaming read, line by line)
     +--------+---------+
              |
              v
     +------------------+
     | HeapFileManager   |  (manages binary file)
     |  +--- Page Cache  |  (1 page in memory)
     |  +--- File I/O    |  (seek + read/write 4KB blocks)
     +--------+---------+
              |
              v
     +------------------+
     |   database.db     |  (binary file on disk)
     |  [Page0][Page1].. |  (contiguous 4KB pages)
     +------------------+

  4. KEY CONCEPTS:
     - Streaming: O(1) RAM regardless of dataset size
     - Page Cache: Minimizes disk I/O during sequential inserts
     - Persistence: File format is self-describing (headers in each page)
     - Record Pointer: (PageID, SlotID) uniquely identifies any record
""")
    print("-" * 72)
    print("  STEP 3 COMPLETE!")
    print("-" * 72)
    print()


if __name__ == "__main__":
    main()
