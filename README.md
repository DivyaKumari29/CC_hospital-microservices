# Hospital Management Microservices

## Important note
The supplied lab manual requires exactly three independent microservices. This implementation intentionally uses four microservices because the project requirement was changed to four. If the evaluator strictly enforces the manual, merge Doctor Service into Appointment Service before final submission.

## Services

1. Patient Service - patient information
2. Doctor Service - doctor information
3. Billing Service - billing information
4. Appointment Service - coordinates appointments and performs end-to-end communication

The Appointment Service also hosts the demonstration UI so the UI does not become a fifth microservice.

## Architecture

Client/UI
   |
   v
Appointment Service
   |--------- Patient Service
   |--------- Doctor Service
   |--------- Billing Service

All containers communicate over `hospital-network`.

## Run

```bash
docker compose up --build
```

Check:

```bash
docker compose ps
```

## UI

Open:

http://localhost:8000

## Swagger

- Appointment: http://localhost:8000/docs
- Patient: http://localhost:8001/docs
- Doctor: http://localhost:8002/docs
- Billing: http://localhost:8003/docs

## End-to-end test

Open:

http://localhost:8000/appointments/1001

The Appointment Service calls the other three services using Docker service names.

## Workload test

Install locally:

```bash
pip install httpx
```

Run:

```bash
python load_test.py
```

Workloads:

W1 = 1 concurrent request
W2 = 2 concurrent requests
W3 = 4 concurrent requests
W4 = 8 concurrent requests
W5 = 16 concurrent requests

## Resource monitoring

Run:

```bash
docker stats
```

Record CPU and memory utilization for all containers during each workload.

## Required observation table

| Workload | Concurrency | Response Time | Throughput | Failed | CPU | Memory |
|---|---:|---:|---:|---:|---:|---:|
| W1 | 1 | measured | measured | measured | measured | measured |
| W2 | 2 | measured | measured | measured | measured | measured |
| W3 | 4 | measured | measured | measured | measured | measured |
| W4 | 8 | measured | measured | measured | measured | measured |
| W5 | 16 | measured | measured | measured | measured | measured |

Do not invent performance values. Fill this table using actual measurements from the experiment.

## Required graphs

1. Concurrent Requests vs Average Response Time
2. Concurrent Requests vs Throughput
3. Concurrent Requests vs CPU Utilization
4. Concurrent Requests vs Memory Utilization

## Checkpoint mapping

Checkpoint 1: Four FastAPI services and REST endpoints
Checkpoint 2: Four Dockerfiles and Docker Compose
Checkpoint 3: Docker network and service-name communication
Checkpoint 4: W1-W5 workload testing and docker stats
Checkpoint 5: observation table, graphs, analysis and demonstration
