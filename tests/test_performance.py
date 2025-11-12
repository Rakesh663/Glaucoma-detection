"""
Performance tests using Locust
"""
from locust import HttpUser, task, between, events
import io
from PIL import Image
import random


class GlaucomaAPIUser(HttpUser):
    """
    Locust user for load testing the Glaucoma Detection API
    """

    # Wait time between tasks (in seconds)
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts"""
        # Generate test image
        self.test_image = self._create_test_image()

        # Optional: Authenticate
        # self.client.post("/auth/login", json={"username": "test", "password": "test"})

    def _create_test_image(self):
        """Create a test image for predictions"""
        # Create a simple RGB image
        img = Image.new('RGB', (224, 224), color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

        # Convert to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        return img_bytes.getvalue()

    @task(10)
    def get_health(self):
        """Health check endpoint - high frequency"""
        self.client.get("/health")

    @task(5)
    def get_root(self):
        """Root endpoint - medium frequency"""
        self.client.get("/")

    @task(1)
    def get_metrics(self):
        """Metrics endpoint - low frequency"""
        self.client.get("/metrics")

    @task(50)
    def predict_image(self):
        """Single image prediction - highest frequency"""
        files = {"file": ("test.png", self.test_image, "image/png")}
        with self.client.post("/predict", files=files, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 503:
                # Model not loaded - mark as failure but don't count against error rate
                response.failure("Model not loaded")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(15)
    def predict_batch(self):
        """Batch prediction - medium-high frequency"""
        # Create batch of 5 images
        files = [
            ("files", (f"test{i}.png", self._create_test_image(), "image/png"))
            for i in range(5)
        ]

        with self.client.post("/batch-predict", files=files, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                # Verify all images were processed
                if data["total_images"] == 5:
                    response.success()
                else:
                    response.failure(f"Expected 5 images, got {data['total_images']}")
            elif response.status_code == 503:
                response.failure("Model not loaded")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(20)
    def predict_with_cache_disabled(self):
        """Prediction with caching disabled"""
        files = {"file": ("test.png", self.test_image, "image/png")}
        params = {"use_cache": "false"}

        with self.client.post("/predict", files=files, params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("cached") == False:
                    response.success()
                else:
                    response.failure("Expected cached=false")
            elif response.status_code == 503:
                response.failure("Model not loaded")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")


# Event listeners for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the load test starts"""
    print("=" * 60)
    print("Load Test Starting")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the load test stops"""
    print("=" * 60)
    print("Load Test Complete")
    print("=" * 60)

    # Print summary statistics
    stats = environment.stats
    print(f"\nTotal Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"Min Response Time: {stats.total.min_response_time}ms")
    print(f"Max Response Time: {stats.total.max_response_time}ms")
    print(f"Requests/sec: {stats.total.total_rps:.2f}")


# Locust configuration for different scenarios

class StressTestUser(GlaucomaAPIUser):
    """
    User class for stress testing (higher load)
    """
    wait_time = between(0.1, 0.5)


class SpikeTestUser(GlaucomaAPIUser):
    """
    User class for spike testing (sudden load)
    """
    wait_time = between(0, 0.1)


class SoakTestUser(GlaucomaAPIUser):
    """
    User class for soak testing (prolonged load)
    """
    wait_time = between(2, 5)


# Run with:
# locust -f tests/test_performance.py --host=http://localhost:8000

# Different test scenarios:
# 1. Load Test: locust -f test_performance.py --users 100 --spawn-rate 10 --run-time 5m
# 2. Stress Test: locust -f test_performance.py --users 500 --spawn-rate 50 --run-time 10m --user-classes StressTestUser
# 3. Spike Test: locust -f test_performance.py --users 1000 --spawn-rate 100 --run-time 2m --user-classes SpikeTestUser
# 4. Soak Test: locust -f test_performance.py --users 50 --spawn-rate 5 --run-time 2h --user-classes SoakTestUser
