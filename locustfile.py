from locust import HttpUser, task, between
import random

class HospitalUser(HttpUser):
    # Wait between 0.1 and 0.5 seconds between tasks
    wait_time = between(0.1, 0.5)

    @task(3)
    def test_appointment_details(self):
        """End-to-end aggregated appointment endpoint (triggers calls to patient, doctor, and billing services)."""
        appointment_id = random.choice([1001, 1002, 1003])
        self.client.get(f"/appointments/{appointment_id}", name="/appointments/[id]")

    @task(1)
    def test_health(self):
        """Check appointment service health."""
        self.client.get("/health", name="/health")

    @task(1)
    def test_list_appointments(self):
        """List all appointments."""
        self.client.get("/appointments", name="/appointments")
