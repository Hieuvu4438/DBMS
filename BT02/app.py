from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import os

from slotted_page_step2 import SlottedPage, PAGE_SIZE, HEADER_SIZE, SLOT_ENTRY_SIZE, DELETED_MARKER
from slotted_page_step3 import serialize_student, deserialize_student

app = FastAPI(title="Slotted Page Visualizer")

# Allow Frontend to hit the Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory page for DEMO purpose
page = SlottedPage(page_id=0)

class StudentInput(BaseModel):
    id: int
    name: str
    email: str

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/reset")
def reset_page():
    global page
    page = SlottedPage(page_id=0)
    return {"status": "success"}

@app.get("/page-status")
def get_status():
    slots = []
    for slot_id in range(page.slot_count):
        offset, length = page._read_slot(slot_id)
        status = "DELETED" if offset == DELETED_MARKER else "ACTIVE"
        data_preview = ""
        student_data = None
        if status == "ACTIVE":
            try:
                record_bytes = page.read_record(slot_id)
                student_data = deserialize_student(record_bytes)
                data_preview = f"ID: {student_data['student_id']} | {student_data['full_name']}"
            except Exception as e:
                data_preview = f"(Parse error) {e}"
                
        slots.append({
            "slot_id": slot_id,
            "offset": "0xFFFF" if offset == DELETED_MARKER else offset,
            "length": length,
            "status": status,
            "data": data_preview
        })
        
    return {
        "page_id": page.page_id,
        "slot_count": page.slot_count,
        "free_space_ptr": page.free_space_ptr,
        "contiguous_free": page.get_contiguous_free_space(),
        "total_free": page.get_total_free_space(),
        "usage_percent": round(((PAGE_SIZE - page.get_total_free_space() - SLOT_ENTRY_SIZE) / PAGE_SIZE) * 100, 2),
        "slots": slots
    }

@app.post("/insert")
def insert_record(student: StudentInput):
    # Dùng string cố định cho lớp và SDT để không cần nhập quá nhiều
    rec_bytes = serialize_student(student.id, student.name, "HTTT01", student.email, "0901234567")
    slot = page.insert_record(rec_bytes)
    if slot == -1:
        return {"status": "error", "message": "Không đủ không gian liên tục (Contiguous Space). Vui lòng Compact Page trước."}
    return {"status": "success", "slot": slot}

@app.post("/delete/{slot_id}")
def delete_record(slot_id: int):
    try:
        page.delete_record(slot_id)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/compact")
def compact():
    page.compact_page()
    return {"status": "success"}

@app.get("/byte-map")
def get_byte_map():
    bmap = ['.'] * PAGE_SIZE
    meta = ['Free Space'] * PAGE_SIZE
    
    # 1. Header
    for i in range(12): 
        bmap[i] = 'H'
        meta[i] = 'Page Header (12 bytes)'
        
    # 2. Slot directory
    slot_dir_end = 12 + page.slot_count * 4
    for i in range(12, slot_dir_end): 
        bmap[i] = 'S'
        meta[i] = 'Slot Directory'
        
    # 3. Data Area (Active Records)
    for slot_id in range(page.slot_count):
        offset, length = page._read_slot(slot_id)
        if offset != DELETED_MARKER:
            try:
                rec_bytes = page.read_record(slot_id)
                rec = deserialize_student(rec_bytes)
                info = f"Slot #{slot_id} | {rec['full_name']} ({rec['email']})"
            except:
                info = f"Slot #{slot_id}"
                
            for i in range(offset, min(offset + length, PAGE_SIZE)):
                bmap[i] = 'R'
                meta[i] = info
                
    # 4. Fragments (Lỗ hổng)
    for i in range(page.free_space_ptr, PAGE_SIZE):
        if bmap[i] != 'R':
            bmap[i] = 'X'
            meta[i] = 'Fragment (Lỗ hổng đã xóa)'
            
    return {"map": bmap, "meta": meta}

if __name__ == "__main__":
    print("Khởi động máy chủ Slotted Page Visualizer...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
