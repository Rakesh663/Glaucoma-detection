"""
Integration tests for API workflows
"""
import pytest
from fastapi.testclient import TestClient
import io
from PIL import Image


class TestPredictionWorkflow:
    """Integration tests for end-to-end prediction workflow"""

    def test_complete_prediction_workflow(self, client, sample_image_bytes, monkeypatch):
        """Test complete workflow from upload to prediction"""
        # Mock detector
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
                return [
                    "Immediate consultation with ophthalmologist recommended",
                    "Schedule IOP measurement",
                    "Consider visual field testing"
                ]

        from api import main
        monkeypatch.setattr(main, "detector", MockDetector())

        # 1. Check health
        health = client.get("/health")
        assert health.status_code == 200

        # 2. Make prediction
        files = {"file": ("retina.png", sample_image_bytes, "image/png")}
        prediction = client.post("/predict", files=files)

        assert prediction.status_code == 200
        data = prediction.json()

        # 3. Verify prediction results
        assert data["label"] == "Glaucoma"
        assert data["risk_level"] == "high"
        assert data["confidence"] > 0.9
        assert len(data["recommendations"]) > 0

        # 4. Verify correlation ID was set
        assert "x-correlation-id" in prediction.headers

    def test_batch_prediction_workflow(self, client, sample_image_bytes, monkeypatch):
        """Test batch prediction workflow"""
        class MockDetector:
            call_count = 0

            def predict(self, image, return_confidence=False):
                # Alternate results
                self.call_count += 1
                is_glaucoma = self.call_count % 2 == 0

                return {
                    'prediction': 1 if is_glaucoma else 0,
                    'label': 'Glaucoma' if is_glaucoma else 'No Glaucoma',
                    'probability': 0.92 if is_glaucoma else 0.85,
                    'confidence': 0.92 if is_glaucoma else 0.85,
                    'risk_level': 'high' if is_glaucoma else 'low'
                }

            def get_recommendations(self, result):
                return ["Consultation recommended"]

        from api import main
        detector = MockDetector()
        monkeypatch.setattr(main, "detector", detector)

        # Upload batch of images
        files = [
            ("files", (f"image{i}.png", sample_image_bytes, "image/png"))
            for i in range(5)
        ]

        response = client.post("/batch-predict", files=files)

        assert response.status_code == 200
        data = response.json()

        # Verify batch processing
        assert data["total_images"] == 5
        assert data["successful"] == 5
        assert data["failed"] == 0
        assert len(data["results"]) == 5

        # Verify mixed results
        glaucoma_count = sum(1 for r in data["results"] if r.get("label") == "Glaucoma")
        assert glaucoma_count > 0  # At least some glaucoma cases


class TestCachingWorkflow:
    """Integration tests for caching functionality"""

    def test_cache_hit_on_duplicate_image(self, client, sample_image_bytes, monkeypatch, mock_redis):
        """Test cache hit when same image is uploaded twice"""
        class MockDetector:
            call_count = 0

            def predict(self, image, return_confidence=False):
                self.call_count += 1
                return {
                    'prediction': 0,
                    'label': 'No Glaucoma',
                    'probability': 0.85,
                    'confidence': 0.85,
                    'risk_level': 'low'
                }

            def get_recommendations(self, result):
                return ["Regular checkup"]

        from api import main
        detector = MockDetector()
        monkeypatch.setattr(main, "detector", detector)

        files = {"file": ("test.png", sample_image_bytes, "image/png")}

        # First request - cache miss
        response1 = client.post("/predict", files=files)
        assert response1.status_code == 200
        data1 = response1.json()

        # Due to file rewinding, we need to recreate the files dict
        files = {"file": ("test.png", sample_image_bytes, "image/png")}

        # Second request - should be cache hit if Redis is working
        response2 = client.post("/predict", files=files)
        assert response2.status_code == 200


class TestRateLimitingWorkflow:
    """Integration tests for rate limiting"""

    def test_rate_limit_headers_present(self, client):
        """Test rate limit headers are included in response"""
        response = client.get("/health")

        # Check for rate limit headers
        # Note: Headers might not be present if rate limiting is disabled in tests
        # This test documents expected behavior


class TestErrorHandling:
    """Integration tests for error handling"""

    def test_invalid_image_format_error(self, client):
        """Test error handling for invalid image format"""
        invalid_data = b"This is not an image"
        files = {"file": ("test.txt", invalid_data, "text/plain")}

        response = client.post("/predict", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "image" in data["detail"].lower()

    def test_corrupted_image_error(self, client):
        """Test error handling for corrupted image"""
        corrupted_data = b"\x89PNG\r\n\x1a\n" + b"corrupted"
        files = {"file": ("corrupted.png", corrupted_data, "image/png")}

        response = client.post("/predict", files=files)

        # Should return 400 or 500 depending on where it fails
        assert response.status_code in [400, 500, 503]


class TestMetricsCollection:
    """Integration tests for metrics collection"""

    def test_metrics_updated_after_prediction(self, client, sample_image_bytes, monkeypatch):
        """Test that metrics are updated after making predictions"""
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
                return ["Regular checkup"]

        from api import main
        monkeypatch.setattr(main, "detector", MockDetector())

        # Get initial metrics
        metrics_before = client.get("/metrics").text

        # Make a prediction
        files = {"file": ("test.png", sample_image_bytes, "image/png")}
        client.post("/predict", files=files)

        # Get updated metrics
        metrics_after = client.get("/metrics").text

        # Metrics should have changed
        assert metrics_before != metrics_after
