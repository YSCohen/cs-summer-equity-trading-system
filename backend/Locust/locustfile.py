from locust import HttpUser, task, between

class EquityTradingUser(HttpUser):
    # Simulates a user waiting 1 to 3 seconds between actions
    wait_time = between(1, 3)

    @task
    def check_health(self):
        self.client.get("/docs")
