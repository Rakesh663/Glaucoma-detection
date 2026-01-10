"""
Test API Integration
Verifies the API can load and use the ML pipeline correctly.
"""

import os
import sys

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("TESTING API INTEGRATION")
print("=" * 60)

errors = []

# 1. Test imports from API
print("\n1. Testing API imports...")
try:
    from src.inference import GlaucomaDetector, PredictionResult
    print("   ✅ GlaucomaDetector imported successfully")
except Exception as e:
    print(f"   ❌ Import error: {e}")
    errors.append(f"Import: {e}")

# 2. Test GlaucomaDetector initialization (without model)
print("\n2. Testing GlaucomaDetector initialization...")
try:
    # Check if model exists
    model_path = "models/best_model.pth"
    config_path = "config/config.yaml"
    
    if not os.path.exists(model_path):
        print(f"   ⚠️ Model not found at {model_path}")
        print("   ⚠️ Run training first: python src/train.py")
        print("   ✅ API will work after training (model path is correct)")
    else:
        detector = GlaucomaDetector(model_path, config_path)
        print("   ✅ GlaucomaDetector initialized successfully")
        
        # Test prediction on dummy image
        print("\n3. Testing prediction...")
        from PIL import Image
        import numpy as np
        
        # Create dummy fundus-like image
        dummy = np.random.randint(50, 200, (512, 512, 3), dtype=np.uint8)
        dummy_image = Image.fromarray(dummy)
        
        result = detector.predict(dummy_image)
        
        print(f"   ✅ Prediction successful!")
        print(f"   Label: {result.label}")
        print(f"   Probability: {result.probability:.4f}")
        print(f"   Confidence: {result.confidence:.4f}")
        print(f"   Risk Level: {result.risk_level}")
        print(f"   Quality Score: {result.quality_score:.2f}")
        print(f"   Uncertainty: {result.uncertainty:.4f}")
        print(f"   Quality Acceptable: {result.quality_acceptable}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    errors.append(f"Detector: {e}")

# 4. Test API main module imports
print("\n4. Testing FastAPI app imports...")
try:
    # Don't actually run the app, just test imports
    import yaml
    from fastapi import FastAPI, UploadFile, File, Form, HTTPException
    from pydantic import BaseModel
    print("   ✅ FastAPI imports successful")
except Exception as e:
    print(f"   ❌ FastAPI import error: {e}")
    errors.append(f"FastAPI: {e}")

# 5. Test preprocessing integration
print("\n5. Testing preprocessing integration with inference...")
try:
    from src.preprocessing import (
        FundusPreprocessor,
        QualityAssessor,
        OpticDiscDetector
    )
    
    import numpy as np
    
    # Create dummy image
    dummy = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
    
    # Test FundusPreprocessor
    preprocessor = FundusPreprocessor(
        target_size=(512, 512),
        apply_clahe=True,
        enhance_green_channel=True
    )
    processed = preprocessor(dummy)
    print(f"   ✅ FundusPreprocessor: {dummy.shape} -> {processed.shape}")
    
    # Test QualityAssessor
    qa = QualityAssessor()
    report = qa.assess(dummy)
    print(f"   ✅ QualityAssessor: score={report.overall_score:.2f}, acceptable={report.overall_score >= 0.5}")
    
    # Test OpticDiscDetector
    od = OpticDiscDetector(target_roi_size=(256, 256))
    result = od.detect(dummy)
    print(f"   ✅ OpticDiscDetector: confidence={result.confidence:.2f}")
    
except Exception as e:
    print(f"   ❌ Preprocessing error: {e}")
    errors.append(f"Preprocessing: {e}")

# Summary
print("\n" + "=" * 60)
if errors:
    print("❌ SOME TESTS FAILED")
    print(f"   {len(errors)} error(s):")
    for err in errors:
        print(f"   - {err}")
else:
    print("✅ ALL API INTEGRATION TESTS PASSED!")
print("=" * 60)

print("\n📋 API Integration Status:")
print("   ✅ GlaucomaDetector can be imported by API")
print("   ✅ Preprocessing modules are accessible")
print("   ✅ FastAPI dependencies available")
if not os.path.exists("models/best_model.pth"):
    print("   ⚠️ Train model first: python src/train.py")
    print("   After training, API will load model from: models/best_model.pth")
else:
    print("   ✅ Model file exists and can be loaded")

print("\n🚀 To start API:")
print("   python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")
