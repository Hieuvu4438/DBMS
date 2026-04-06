"""Verify persistence of database.db"""
import sys, io
old = sys.stdout
sys.stdout = io.StringIO()
from slotted_page_step3 import HeapFileManager, deserialize_student
sys.stdout = old

with HeapFileManager('database.db') as mgr:
    print('Pages: %d' % mgr.total_pages)
    for pid in [0, 100, 1000, 5000, mgr.total_pages - 1]:
        data = mgr.get_record(pid, 0)
        s = deserialize_student(data)
        print('  Page %5d, Slot 0: ID=%s, Name=%s' % (pid, s['student_id'], s['full_name']))
    print('Persistence OK!')
