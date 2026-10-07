import os
import asyncio
import sqlite3
import httpx
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

DB_PATH = "appointments.db"

# Detect whether running inside a Docker container
IS_DOCKER = os.path.exists("/.dockerenv") or os.getenv("RUNNING_IN_DOCKER", "false").lower() == "true"

DEFAULT_PATIENT_URL = "http://patient-service:8001" if IS_DOCKER else "http://localhost:8001"
DEFAULT_DOCTOR_URL = "http://doctor-service:8002" if IS_DOCKER else "http://localhost:8002"
DEFAULT_BILLING_URL = "http://billing-service:8003" if IS_DOCKER else "http://localhost:8003"

PATIENT_SERVICE_URL = os.getenv("PATIENT_SERVICE_URL", DEFAULT_PATIENT_URL)
DOCTOR_SERVICE_URL = os.getenv("DOCTOR_SERVICE_URL", DEFAULT_DOCTOR_URL)
BILLING_SERVICE_URL = os.getenv("BILLING_SERVICE_URL", DEFAULT_BILLING_URL)

http_client: Optional[httpx.AsyncClient] = None

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
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY,
                patient_id INTEGER NOT NULL,
                doctor_id INTEGER NOT NULL,
                appointment_date TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM appointments")
        if cursor.fetchone()[0] == 0:
            seed_appointments = [
                (1001, 1, 101, "2026-10-10 10:00 AM", "Confirmed"),
                (1002, 2, 102, "2026-10-11 02:30 PM", "Confirmed"),
                (1003, 3, 103, "2026-10-12 11:15 AM", "Pending")
            ]
            cursor.executemany(
                "INSERT INTO appointments (id, patient_id, doctor_id, appointment_date, status) VALUES (?, ?, ?, ?, ?)",
                seed_appointments
            )
            conn.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    init_db()
    http_client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=100),
        timeout=10.0
    )
    yield
    if http_client:
        await http_client.aclose()

app = FastAPI(
    title="Appointment Service",
    description="Coordinates appointments and orchestrates patient, doctor, and billing microservices.",
    version="1.0.0",
    lifespan=lifespan
)

class AppointmentCreate(BaseModel):
    id: Optional[int] = None
    patient_id: int
    doctor_id: int
    appointment_date: str
    status: str = "Confirmed"

async def fetch_service_data(client: httpx.AsyncClient, base_url: str, endpoint: str):
    """Fetch from configured service URL."""
    try:
        resp = await client.get(f"{base_url}{endpoint}")
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return {"error": "Not found", "status_code": 404}
    except (httpx.ConnectError, httpx.TimeoutException):
        return {"error": "Service unreachable"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
def health():
    return {"service": "appointment-service", "status": "healthy"}

@app.get("/appointments")
def list_appointments(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, patient_id, doctor_id, appointment_date, status FROM appointments ORDER BY id ASC")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

@app.get("/appointments/{appointment_id}")
async def get_appointment(appointment_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, patient_id, doctor_id, appointment_date, status FROM appointments WHERE id = ?", (appointment_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appt = dict(row)
    patient_id = appt["patient_id"]
    doctor_id = appt["doctor_id"]

    client = http_client if http_client is not None else httpx.AsyncClient(timeout=10.0)
    try:
        patient_task = fetch_service_data(client, PATIENT_SERVICE_URL, f"/patients/{patient_id}")
        doctor_task = fetch_service_data(client, DOCTOR_SERVICE_URL, f"/doctors/{doctor_id}")
        billing_task = fetch_service_data(client, BILLING_SERVICE_URL, f"/billing/{patient_id}")

        patient_data, doctor_data, billing_data = await asyncio.gather(
            patient_task, doctor_task, billing_task
        )
    finally:
        if http_client is None:
            await client.aclose()

    return {
        "appointment_id": appt["id"],
        "appointment_date": appt["appointment_date"],
        "status": appt["status"],
        "patient": patient_data,
        "doctor": doctor_data,
        "billing": billing_data
    }

@app.post("/appointments", status_code=201)
def create_appointment(data: AppointmentCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    try:
        if data.id is not None:
            cursor.execute(
                "INSERT INTO appointments (id, patient_id, doctor_id, appointment_date, status) VALUES (?, ?, ?, ?, ?)",
                (data.id, data.patient_id, data.doctor_id, data.appointment_date, data.status)
            )
        else:
            cursor.execute(
                "INSERT INTO appointments (patient_id, doctor_id, appointment_date, status) VALUES (?, ?, ?, ?)",
                (data.patient_id, data.doctor_id, data.appointment_date, data.status)
            )
        db.commit()
        appt_id = data.id if data.id is not None else cursor.lastrowid
        return {
            "id": appt_id,
            "patient_id": data.patient_id,
            "doctor_id": data.doctor_id,
            "appointment_date": data.appointment_date,
            "status": data.status
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail=f"Appointment ID {data.id} already exists")

@app.get("/", response_class=HTMLResponse)
def demonstration_ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hospital Management Microservices</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --success: #10b981;
            --warning: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background: var(--bg); color: var(--text-main); line-height: 1.5; padding: 2rem 1rem; }
        .container { max-width: 1100px; margin: 0 auto; }
        header { text-align: center; margin-bottom: 2.5rem; }
        header h1 { font-size: 2.25rem; font-weight: 700; color: #1e293b; margin-bottom: 0.5rem; }
        header p { color: var(--text-muted); font-size: 1.1rem; }
        
        .services-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .service-card {
            background: var(--card-bg);
            padding: 1.25rem;
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .service-info h3 { font-size: 0.95rem; font-weight: 600; }
        .service-info span { font-size: 0.8rem; color: var(--text-muted); }
        .badge {
            padding: 0.25rem 0.65rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            background: #dcfce7;
            color: #166534;
        }
        .badge.pending { background: #fef3c7; color: #92400e; }
        
        .search-box {
            background: var(--card-bg);
            padding: 1.75rem;
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 2rem;
            display: flex;
            gap: 1rem;
            align-items: center;
        }
        .search-box input {
            flex: 1;
            padding: 0.75rem 1rem;
            font-size: 1rem;
            border: 1px solid var(--border);
            border-radius: 8px;
            outline: none;
            transition: border 0.2s;
        }
        .search-box input:focus { border-color: var(--primary); }
        .search-box button {
            background: var(--primary);
            color: white;
            border: none;
            padding: 0.75rem 1.75rem;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .search-box button:hover { background: var(--primary-hover); }

        .result-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .result-card {
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border);
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .result-card h2 {
            font-size: 1.15rem;
            font-weight: 600;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .row { display: flex; justify-content: space-between; margin-bottom: 0.6rem; font-size: 0.95rem; }
        .row span.label { color: var(--text-muted); }
        .row span.val { font-weight: 500; }

        .quick-links {
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border);
            padding: 1.5rem;
            text-align: center;
        }
        .quick-links h3 { font-size: 1rem; margin-bottom: 1rem; color: var(--text-muted); }
        .links-group { display: flex; justify-content: center; gap: 1.5rem; flex-wrap: wrap; }
        .links-group a {
            color: var(--primary);
            text-decoration: none;
            font-weight: 500;
            font-size: 0.9rem;
        }
        .links-group a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Hospital Management Microservices</h1>
            <p>End-to-End Orchestration Demonstration UI</p>
        </header>

        <div class="services-bar">
            <div class="service-card">
                <div class="service-info">
                    <h3>Appointment</h3>
                    <span>Port 8000 (Orchestrator)</span>
                </div>
                <span class="badge">SQLite Active</span>
            </div>
            <div class="service-card">
                <div class="service-info">
                    <h3>Patient Service</h3>
                    <span>Port 8001</span>
                </div>
                <span class="badge">SQLite Active</span>
            </div>
            <div class="service-card">
                <div class="service-info">
                    <h3>Doctor Service</h3>
                    <span>Port 8002</span>
                </div>
                <span class="badge">SQLite Active</span>
            </div>
            <div class="service-card">
                <div class="service-info">
                    <h3>Billing Service</h3>
                    <span>Port 8003</span>
                </div>
                <span class="badge">SQLite Active</span>
            </div>
        </div>

        <div class="search-box">
            <input type="number" id="apptIdInput" value="1001" placeholder="Enter Appointment ID (e.g. 1001, 1002, 1003)">
            <button onclick="fetchAppointment()">Fetch Appointment</button>
        </div>

        <div id="resultContainer" class="result-grid">
            <div class="result-card">
                <h2>Appointment Info <span class="badge" id="apptStatus">Confirmed</span></h2>
                <div class="row"><span class="label">Appointment ID:</span><span class="val" id="dispApptId">-</span></div>
                <div class="row"><span class="label">Date & Time:</span><span class="val" id="dispApptDate">-</span></div>
            </div>

            <div class="result-card">
                <h2>Patient Details <span class="badge" id="patientBadge">Fetched</span></h2>
                <div class="row"><span class="label">Patient ID:</span><span class="val" id="dispPatId">-</span></div>
                <div class="row"><span class="label">Name:</span><span class="val" id="dispPatName">-</span></div>
                <div class="row"><span class="label">Age:</span><span class="val" id="dispPatAge">-</span></div>
                <div class="row"><span class="label">Gender:</span><span class="val" id="dispPatGender">-</span></div>
            </div>

            <div class="result-card">
                <h2>Doctor Details <span class="badge" id="docBadge">Fetched</span></h2>
                <div class="row"><span class="label">Doctor ID:</span><span class="val" id="dispDocId">-</span></div>
                <div class="row"><span class="label">Name:</span><span class="val" id="dispDocName">-</span></div>
                <div class="row"><span class="label">Specialization:</span><span class="val" id="dispDocSpec">-</span></div>
                <div class="row"><span class="label">Availability:</span><span class="val" id="dispDocAvail">-</span></div>
            </div>

            <div class="result-card">
                <h2>Billing Details <span class="badge" id="billBadge">Paid</span></h2>
                <div class="row"><span class="label">Patient ID:</span><span class="val" id="dispBillPatId">-</span></div>
                <div class="row"><span class="label">Total Amount:</span><span class="val" id="dispBillAmount">-</span></div>
                <div class="row"><span class="label">Payment Status:</span><span class="val" id="dispBillStatus">-</span></div>
            </div>
        </div>

        <div class="quick-links">
            <h3>Swagger API Documentation</h3>
            <div class="links-group">
                <a href="/docs" target="_blank">Appointment Docs (:8000)</a>
                <a href="http://localhost:8001/docs" target="_blank">Patient Docs (:8001)</a>
                <a href="http://localhost:8002/docs" target="_blank">Doctor Docs (:8002)</a>
                <a href="http://localhost:8003/docs" target="_blank">Billing Docs (:8003)</a>
            </div>
        </div>
    </div>

    <script>
        async function fetchAppointment() {
            const id = document.getElementById('apptIdInput').value;
            try {
                const res = await fetch('/appointments/' + id);
                if (!res.ok) {
                    alert('Appointment ' + id + ' not found or error occurred.');
                    return;
                }
                const data = await res.json();
                
                document.getElementById('dispApptId').textContent = data.appointment_id;
                document.getElementById('dispApptDate').textContent = data.appointment_date;
                document.getElementById('apptStatus').textContent = data.status;

                if (data.patient && !data.patient.error) {
                    document.getElementById('dispPatId').textContent = data.patient.id;
                    document.getElementById('dispPatName').textContent = data.patient.name;
                    document.getElementById('dispPatAge').textContent = data.patient.age;
                    document.getElementById('dispPatGender').textContent = data.patient.gender;
                } else {
                    document.getElementById('dispPatName').textContent = 'Error fetching patient';
                }

                if (data.doctor && !data.doctor.error) {
                    document.getElementById('dispDocId').textContent = data.doctor.id;
                    document.getElementById('dispDocName').textContent = data.doctor.name;
                    document.getElementById('dispDocSpec').textContent = data.doctor.specialization;
                    document.getElementById('dispDocAvail').textContent = data.doctor.available ? 'Available' : 'Unavailable';
                } else {
                    document.getElementById('dispDocName').textContent = 'Error fetching doctor';
                }

                if (data.billing && !data.billing.error) {
                    document.getElementById('dispBillPatId').textContent = data.billing.patient_id;
                    document.getElementById('dispBillAmount').textContent = '₹' + data.billing.amount;
                    document.getElementById('dispBillStatus').textContent = data.billing.status;
                    const b = document.getElementById('billBadge');
                    b.textContent = data.billing.status;
                    b.className = data.billing.status === 'Paid' ? 'badge' : 'badge pending';
                } else {
                    document.getElementById('dispBillStatus').textContent = 'Error fetching bill';
                }
            } catch (err) {
                console.error(err);
                alert('Failed to connect to appointment service.');
            }
        }
        window.onload = fetchAppointment;
    </script>
</body>
</html>"""
