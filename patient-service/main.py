import sqlite3
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

DB_PATH = "patients.db"

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
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL
            )
        """)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM patients")
        if cursor.fetchone()[0] == 0:
            seed_patients = [
                (1, "Rahul Sharma", 35, "Male"),
                (2, "Priya Patil", 28, "Female"),
                (3, "Arjun Kumar", 42, "Male")
            ]
            cursor.executemany(
                "INSERT INTO patients (id, name, age, gender) VALUES (?, ?, ?, ?)",
                seed_patients
            )
            conn.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Patient Service",
    description="Manages patient information with SQLite database.",
    version="1.0.0",
    lifespan=lifespan
)

class PatientCreate(BaseModel):
    id: Optional[int] = None
    name: str
    age: int
    gender: str

@app.get("/health")
def health():
    return {"service": "patient-service", "status": "healthy"}

@app.get("/patients")
def get_patients(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, name, age, gender FROM patients ORDER BY id ASC")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

@app.get("/patients/{patient_id}")
def get_patient(patient_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, name, age, gender FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")
    return dict(row)

@app.post("/patients", status_code=201)
def create_patient(patient: PatientCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    try:
        if patient.id is not None:
            cursor.execute(
                "INSERT INTO patients (id, name, age, gender) VALUES (?, ?, ?, ?)",
                (patient.id, patient.name, patient.age, patient.gender)
            )
        else:
            cursor.execute(
                "INSERT INTO patients (name, age, gender) VALUES (?, ?, ?)",
                (patient.name, patient.age, patient.gender)
            )
        db.commit()
        patient_id = patient.id if patient.id is not None else cursor.lastrowid
        return {"id": patient_id, "name": patient.name, "age": patient.age, "gender": patient.gender}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"Patient with ID {patient.id} already exists")
