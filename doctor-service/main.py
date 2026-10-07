import sqlite3
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

DB_PATH = "doctors.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                specialization TEXT NOT NULL,
                available INTEGER NOT NULL DEFAULT 1
            )
        """)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM doctors")
        if cursor.fetchone()[0] == 0:
            seed_doctors = [
                (101, "Dr. Ananya Rao", "Cardiology", 1),
                (102, "Dr. Vikram Singh", "Neurology", 1),
                (103, "Dr. Meera Joshi", "Orthopedics", 0)
            ]
            cursor.executemany(
                "INSERT INTO doctors (id, name, specialization, available) VALUES (?, ?, ?, ?)",
                seed_doctors
            )
            conn.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Doctor Service",
    description="Manages doctor information and availability with SQLite database.",
    version="1.0.0",
    lifespan=lifespan
)

class DoctorCreate(BaseModel):
    id: Optional[int] = None
    name: str
    specialization: str
    available: bool = True

def format_doctor_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["available"] = bool(d["available"])
    return d

@app.get("/health")
def health():
    return {"service": "doctor-service", "status": "healthy"}

@app.get("/doctors")
def get_doctors(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, name, specialization, available FROM doctors ORDER BY id ASC")
    rows = cursor.fetchall()
    return [format_doctor_row(row) for row in rows]

@app.get("/doctors/{doctor_id}")
def get_doctor(doctor_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, name, specialization, available FROM doctors WHERE id = ?", (doctor_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return format_doctor_row(row)

@app.post("/doctors", status_code=201)
def create_doctor(doctor: DoctorCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    try:
        available_int = 1 if doctor.available else 0
        if doctor.id is not None:
            cursor.execute(
                "INSERT INTO doctors (id, name, specialization, available) VALUES (?, ?, ?, ?)",
                (doctor.id, doctor.name, doctor.specialization, available_int)
            )
        else:
            cursor.execute(
                "INSERT INTO doctors (name, specialization, available) VALUES (?, ?, ?)",
                (doctor.name, doctor.specialization, available_int)
            )
        db.commit()
        doc_id = doctor.id if doctor.id is not None else cursor.lastrowid
        return {
            "id": doc_id,
            "name": doctor.name,
            "specialization": doctor.specialization,
            "available": doctor.available
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"Doctor with ID {doctor.id} already exists")
