"""
Production FastAPI service for glaucoma detection
"""
import os
import sys
import time
import io
import yaml
from datetime import datetime
from typing import Optional
from PIL import Image

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from inference import GlaucomaDetector


class PredictionResponse(BaseModel):
    status: str
    prediction: int
    label: str
    probability: float
    confidence: float
    risk_level: str
    recommendations: list
    processing_time_ms: float
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    timestamp: str
    version: str


app = FastAPI(
    title="Glaucoma Detection API",
    description="Production API for automated glaucoma detection",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

detector = None


@app.on_event("startup")
async def startup_event():
    global detector

    # Get the project root directory (parent of api folder)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)

    model_path = os.path.join(project_root, 'models', 'best_model.pth')
    scripted_path = os.path.join(project_root, 'models', 'model_scripted.pt')
    config_path = os.path.join(project_root, 'models', 'config.yaml')
    
    if os.path.exists(scripted_path):
        print(f"Loading TorchScript model: {scripted_path}")
        detector = GlaucomaDetector(scripted_path, config_path)
    elif os.path.exists(model_path):
        print(f"Loading PyTorch model: {model_path}")
        detector = GlaucomaDetector(model_path, config_path)
    else:
        print("WARNING: No trained model found!")
        print(f"Expected: {model_path} or {scripted_path}")
        print("Train first: cd src && python train.py")
        detector = None


@app.get("/", response_model=dict)
async def root():
    return {
        "service": "Glaucoma Detection API",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "GET /": "API information",
            "GET /health": "Health check",
            "POST /predict": "Single image prediction",
            "POST /batch-predict": "Batch prediction",
            "GET /docs": "API documentation"
        },
        "model_status": "loaded" if detector is not None else "not loaded"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        model_loaded=detector is not None,
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


def validate_image(file: UploadFile, max_size_mb: int = 10):
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail=f"File must be an image. Received: {file.content_type}"
        )


async def load_image_from_upload(file: UploadFile) -> Image.Image:
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert('RGB')
        return image
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load image: {str(e)}"
        )


@app.post("/predict", response_model=PredictionResponse)
async def predict(file: UploadFile = File(...)):
    """Predict glaucoma from retinal image"""
    
    if detector is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Train first: cd src && python train.py"
        )
    
    validate_image(file)
    start_time = time.time()
    
    try:
        image = await load_image_from_upload(file)
        result = detector.predict(image, return_confidence=True)
        recommendations = detector.get_recommendations(result)
        processing_time = (time.time() - start_time) * 1000
        
        return PredictionResponse(
            status="success",
            prediction=result['prediction'],
            label=result['label'],
            probability=result['probability'],
            confidence=result['confidence'],
            risk_level=result['risk_level'],
            recommendations=recommendations,
            processing_time_ms=round(processing_time, 2),
            timestamp=datetime.now().isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )


@app.post("/batch-predict")
async def batch_predict(files: list[UploadFile] = File(...)):
    """Predict glaucoma for multiple images"""
    
    if detector is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Train first: cd src && python train.py"
        )
    
    max_batch_size = 20
    if len(files) > max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_batch_size} images allowed"
        )
    
    start_time = time.time()
    results = []
    
    for idx, file in enumerate(files):
        try:
            validate_image(file)
            image = await load_image_from_upload(file)
            result = detector.predict(image, return_confidence=True)
            recommendations = detector.get_recommendations(result)
            
            results.append({
                "index": idx,
                "filename": file.filename,
                "status": "success",
                "prediction": result['prediction'],
                "label": result['label'],
                "probability": result['probability'],
                "confidence": result['confidence'],
                "risk_level": result['risk_level'],
                "recommendations": recommendations
            })
        
        except HTTPException as he:
            results.append({
                "index": idx,
                "filename": file.filename,
                "status": "error",
                "error": he.detail
            })
        except Exception as e:
            results.append({
                "index": idx,
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })
    
    processing_time = (time.time() - start_time) * 1000
    
    return JSONResponse(content={
        "status": "success",
        "total_images": len(files),
        "successful": sum(1 for r in results if r['status'] == 'success'),
        "failed": sum(1 for r in results if r['status'] == 'error'),
        "processing_time_ms": round(processing_time, 2),
        "timestamp": datetime.now().isoformat(),
        "results": results
    })


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    print(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.2f}ms")
    return response


if __name__ == "__main__":
    # Get the project root directory (parent of api folder if running from api, otherwise current)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    config_path = os.path.join(project_root, 'config', 'config.yaml')

    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        host = config['api']['host']
        port = config['api']['port']
        workers = config['api']['workers']
    else:
        host = "0.0.0.0"
        port = 8000
        workers = 1
    
    print("=" * 60)
    print("Glaucoma Detection API")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Docs: http://localhost:{port}/docs")
    print("=" * 60)
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=False
    )