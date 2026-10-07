import sqlite3
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

DB_PATH = "billing.db"

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
            CREATE TABLE IF NOT EXISTS bills (
                patient_id INTEGER PRIMARY KEY,
                amount REAL NOT NULL,
                status TEXT NOT NULL
            )
        """)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bills")
        if cursor.fetchone()[0] == 0:
            seed_bills = [
                (1, 4500.0, "Paid"),
                (2, 2800.0, "Pending"),
                (3, 6200.0, "Paid")
            ]
            cursor.executemany(
                "INSERT INTO bills (patient_id, amount, status) VALUES (?, ?, ?)",
                seed_bills
            )
            conn.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Billing Service",
    description="Manages patient billing information with SQLite database.",
    version="1.0.0",
    lifespan=lifespan
)

class BillCreate(BaseModel):
    patient_id: int
    amount: float
    status: str

@app.get("/health")
def health():
    return {"service": "billing-service", "status": "healthy"}

@app.get("/billing")
def get_all_bills(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT patient_id, amount, status FROM bills ORDER BY patient_id ASC")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

@app.get("/billing/{patient_id}")
def get_bill(patient_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT patient_id, amount, status FROM bills WHERE patient_id = ?", (patient_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Billing record not found")
    return dict(row)

@app.post("/billing", status_code=201)
def create_or_update_bill(bill: BillCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO bills (patient_id, amount, status)
        VALUES (?, ?, ?)
        ON CONFLICT(patient_id) DO UPDATE SET
            amount=excluded.amount,
            status=excluded.status
    """, (bill.patient_id, bill.amount, bill.status))
    db.commit()
    return {"patient_id": bill.patient_id, "amount": bill.amount, "status": bill.status}
