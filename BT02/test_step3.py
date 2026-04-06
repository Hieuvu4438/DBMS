"""Quick test for step3 with 1000 records before running 500K"""
import sys, io, os, time

# Suppress step2 module-level output
old = sys.stdout
sys.stdout = io.StringIO()
from slotted_page_step3 import (
    HeapFileManager, generate_dataset, serialize_student,
    deserialize_student, bulk_load, PAGE_SIZE
)
sys.stdout = old

base = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(base, "test_data.csv")
db_path = os.path.join(base, "test_db.db")

# Cleanup
for f in [csv_path, db_path]:
    if os.path.exists(f):
        os.remove(f)

# Test 1: Generate small dataset
print("=== Test 1: Generate 1000 records ===")
generate_dataset(csv_path, 1000)

# Test 2: Bulk load
print("\n=== Test 2: Bulk load 1000 records ===")
with HeapFileManager(db_path) as mgr:
    bulk_load(mgr, csv_path)
    pages_after = mgr.total_pages
    print(f"Pages: {pages_after}")
    
    # Test 3: Read random records
    print("\n=== Test 3: Read records ===")
    for pid in [0, 1, pages_after - 1]:
        data = mgr.get_record(pid, 0)
        student = deserialize_student(data)
        print(f"  Page {pid}, Slot 0: ID={student['student_id']}, Name={student['full_name']}")

# Test 4: Persistence
print("\n=== Test 4: Persistence ===")
with HeapFileManager(db_path) as mgr2:
    print(f"Reopened: {mgr2.total_pages} pages")
    data = mgr2.get_record(0, 0)
    s = deserialize_student(data)
    print(f"  First record: ID={s['student_id']}, Name={s['full_name']}")
    
    # Count all records via scan
    count = sum(1 for _ in mgr2.scan_all_records())
    print(f"  Total records via scan: {count}")
    assert count == 1000, f"Expected 1000, got {count}"

# Cleanup test files
for f in [csv_path, db_path]:
    if os.path.exists(f):
        os.remove(f)

print("\n=== ALL TESTS PASSED! ===")
