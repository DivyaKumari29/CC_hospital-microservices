import matplotlib.pyplot as plt

workloads = ['W1 (1)', 'W2 (2)', 'W3 (4)', 'W4 (8)', 'W5 (16)']
concurrency = [1, 2, 4, 8, 16]

# End-to-end aggregated microservice endpoint (/appointments/[id])
avg_rt_endpoint = [17.15, 19.49, 19.75, 22.00, 26.04]
throughput_endpoint = [2.5, 4.2, 7.6, 14.4, 25.3]

# Overall system aggregated
avg_rt_system = [14.60, 14.74, 15.17, 16.24, 19.53]
throughput_system = [3.2, 5.8, 12.2, 24.7, 43.0]

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

# 1. Concurrency vs Average Response Time
plt.figure(figsize=(8, 5))
plt.plot(concurrency, avg_rt_endpoint, marker='o', linewidth=2.5, color='#2563eb', label='Aggregated Endpoint (/appointments/[id])')
plt.plot(concurrency, avg_rt_system, marker='s', linewidth=2.0, linestyle='--', color='#10b981', label='Overall System')
plt.title('Concurrent Requests vs Average Response Time', fontsize=14, fontweight='bold', pad=15)
plt.xlabel('Concurrent Users / Concurrency', fontsize=12)
plt.ylabel('Average Response Time (ms)', fontsize=12)
plt.xticks(concurrency)
plt.ylim(10, 30)
for x, y in zip(concurrency, avg_rt_endpoint):
    plt.annotate(f"{y:.2f} ms", (x, y), textcoords="offset points", xytext=(0, 8), ha='center', fontsize=9, fontweight='semibold')
plt.legend(frameon=True)
plt.tight_layout()
plt.savefig('graph1_response_time.png', dpi=300)
plt.close()

# 2. Concurrency vs Throughput
plt.figure(figsize=(8, 5))
plt.plot(concurrency, throughput_system, marker='o', linewidth=2.5, color='#8b5cf6', label='Total System Throughput (RPS)')
plt.plot(concurrency, throughput_endpoint, marker='^', linewidth=2.0, linestyle='--', color='#f59e0b', label='Endpoint Throughput (/appointments/[id])')
plt.title('Concurrent Requests vs Throughput', fontsize=14, fontweight='bold', pad=15)
plt.xlabel('Concurrent Users / Concurrency', fontsize=12)
plt.ylabel('Throughput (Requests/sec)', fontsize=12)
plt.xticks(concurrency)
for x, y in zip(concurrency, throughput_system):
    plt.annotate(f"{y:.1f} RPS", (x, y), textcoords="offset points", xytext=(0, 8), ha='center', fontsize=9, fontweight='semibold')
plt.legend(frameon=True)
plt.tight_layout()
plt.savefig('graph2_throughput.png', dpi=300)
plt.close()

print("Graphs successfully generated: graph1_response_time.png and graph2_throughput.png")
