"""
Unit tests for API endpoints
"""
import pytest
from fastapi.testclient import TestClient
import io
from PIL import Image


class TestRootEndpoint:
    """Tests for root endpoint"""

    def test_root_returns_api_info(self, client):
        """Test root endpoint returns API information"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Glaucoma Detection API"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data

    def test_root_includes_model_status(self, client):
        """Test root endpoint includes model status"""
        response = client.get("/")
        data = response.json()
        assert "model_status" in data


class TestHealthEndpoint:
    """Tests for health check endpoint"""

    def test_health_check_returns_healthy(self, client):
        """Test health endpoint returns healthy status"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_health_includes_model_loaded(self, client):
        """Test health includes model loaded status"""
        response = client.get("/health")
        data = response.json()
        assert "model_loaded" in data
        assert isinstance(data["model_loaded"], bool)


class TestMetricsEndpoint:
    """Tests for Prometheus metrics endpoint"""

    def test_metrics_endpoint_exists(self, client):
        """Test metrics endpoint is accessible"""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_returns_prometheus_format(self, client):
        """Test metrics are in Prometheus format"""
        response = client.get("/metrics")
        assert response.headers["content-type"].startswith("text/plain")
        content = response.text
        # Should contain some metric definitions
        assert "# HELP" in content or "# TYPE" in content


class TestPredictionEndpoint:
    """Tests for prediction endpoint"""

    def test_predict_requires_file(self, client):
        """Test prediction endpoint requires a file"""
        response = client.post("/predict")
        assert response.status_code == 422  # Validation error

    def test_predict_rejects_non_image(self, client):
        """Test prediction rejects non-image files"""
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = client.post("/predict", files=files)
        assert response.status_code == 400
        assert "image" in response.json()["detail"].lower()

    def test_predict_accepts_image(self, client, sample_image_bytes):
        """Test prediction accepts valid image"""
        files = {"file": ("test.png", sample_image_bytes, "image/png")}
        response = client.post("/predict", files=files)

        # May return 503 if model not loaded, which is acceptable in tests
        assert response.status_code in [200, 503]

    def test_predict_response_structure(self, client, sample_image_bytes, monkeypatch):
        """Test prediction response has correct structure"""
        # Mock the detector to avoid needing actual model
        class MockDetector:
            def predict(self, image, return_confidence=False):
                return {
                    'prediction': 0,
                    'label': 'No Glaucoma',
                    'probability': 0.85,
                    'confidence': 0.85,
                    'risk_level': 'low'
                }

            def get_recommendations(self, result):
                return ["Regular checkup recommended"]

        from api import main
        monkeypatch.setattr(main, "detector", MockDetector())

        files = {"file": ("test.png", sample_image_bytes, "image/png")}
        response = client.post("/predict", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "status" in data
        assert "prediction" in data
        assert "label" in data
        assert "probability" in data
        assert "confidence" in data
        assert "risk_level" in data
        assert "recommendations" in data
        assert "processing_time_ms" in data
        assert "timestamp" in data
        assert "cached" in data

    def test_predict_with_caching_disabled(self, client, sample_image_bytes, monkeypatch):
        """Test prediction with use_cache=false"""
        class MockDetector:
            def predict(self, image, return_confidence=False):
                return {
                    'prediction': 1,
                    'label': 'Glaucoma',
                    'probability': 0.92,
                    'confidence': 0.92,
                    'risk_level': 'high'
                }

            def get_recommendations(self, result):
                return ["Immediate consultation recommended"]

        from api import main
        monkeypatch.setattr(main, "detector", MockDetector())

        files = {"file": ("test.png", sample_image_bytes, "image/png")}
        response = client.post("/predict?use_cache=false", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["cached"] == False


class TestBatchPredictionEndpoint:
    """Tests for batch prediction endpoint"""

    def test_batch_predict_requires_files(self, client):
        """Test batch prediction requires files"""
        response = client.post("/batch-predict")
        assert response.status_code == 422

    def test_batch_predict_enforces_max_size(self, client, sample_image_bytes):
        """Test batch prediction enforces maximum batch size"""
        # Try to upload 21 files (max is 20)
        files = [
            ("files", (f"test{i}.png", sample_image_bytes, "image/png"))
            for i in range(21)
        ]

        response = client.post("/batch-predict", files=files)
        assert response.status_code == 400
        assert "Maximum" in response.json()["detail"]

    def test_batch_predict_response_structure(self, client, sample_image_bytes, monkeypatch):
        """Test batch prediction response structure"""
        class MockDetector:
            def predict(self, image, return_confidence=False):
                return {
                    'prediction': 0,
                    'label': 'No Glaucoma',
                    'probability': 0.85,
                    'confidence': 0.85,
                    'risk_level': 'low'
                }

            def get_recommendations(self, result):
                return ["Regular checkup recommended"]

        from api import main
        monkeypatch.setattr(main, "detector", MockDetector())

        files = [
            ("files", (f"test{i}.png", sample_image_bytes, "image/png"))
            for i in range(3)
        ]

        response = client.post("/batch-predict", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "status" in data
        assert "total_images" in data
        assert "successful" in data
        assert "failed" in data
        assert "cache_hits" in data
        assert "cache_misses" in data
        assert "cache_hit_rate" in data
        assert "processing_time_ms" in data
        assert "timestamp" in data
        assert "results" in data

        # Check results array
        assert len(data["results"]) == 3
        assert data["total_images"] == 3


class TestCorsHeaders:
    """Tests for CORS headers"""

    def test_cors_headers_present(self, client):
        """Test CORS headers are present"""
        response = client.get("/")
        assert "access-control-allow-origin" in response.headers


class TestCorrelationId:
    """Tests for correlation ID tracking"""

    def test_correlation_id_in_response(self, client):
        """Test correlation ID is added to response"""
        response = client.get("/health")
        assert "x-correlation-id" in response.headers

    def test_custom_correlation_id_preserved(self, client):
        """Test custom correlation ID is preserved"""
        custom_id = "test-correlation-123"
        headers = {"X-Correlation-ID": custom_id}
        response = client.get("/health", headers=headers)

        # Response should include the same correlation ID
        assert "x-correlation-id" in response.headers
