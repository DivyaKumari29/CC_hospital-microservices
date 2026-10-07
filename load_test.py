import asyncio
import statistics
import time
import httpx

URL = "http://localhost:8000/appointments/1001"
WORKLOADS = [1, 2, 4, 8, 16]

async def request(client):
    start = time.perf_counter()
    try:
        response = await client.get(URL, timeout=15)
        elapsed = (time.perf_counter() - start) * 1000
        return response.status_code == 200, elapsed
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        return False, elapsed

async def run_workload(concurrency):
    async with httpx.AsyncClient() as client:
        start = time.perf_counter()
        results = await asyncio.gather(
            *[request(client) for _ in range(concurrency)]
        )
        total_time = time.perf_counter() - start

    successful = sum(ok for ok, _ in results)
    failed = concurrency - successful
    times = [t for ok, t in results if ok]
    avg_response = statistics.mean(times) if times else 0
    throughput = successful / total_time if total_time else 0

    return avg_response, throughput, failed

async def main():
    print("\nHospital Microservices Workload Test")
    print("-" * 75)
    print(f"{'Workload':<10}{'Concurrency':<14}{'Avg RT(ms)':<15}{'Throughput(req/s)':<20}{'Failed':<10}")

    for i, concurrency in enumerate(WORKLOADS, 1):
        avg_rt, throughput, failed = await run_workload(concurrency)
        print(f"W{i:<9}{concurrency:<14}{avg_rt:<15.2f}{throughput:<20.2f}{failed:<10}")

if __name__ == "__main__":
    asyncio.run(main())
