"""
Production FastAPI service for glaucoma detection
"""
import os
import sys
import time
import io
import yaml
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional
from functools import partial
from PIL import Image

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Depends, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from inference import GlaucomaDetector
from api.database.models import User, Patient, Prediction
from api.database.session import get_db
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Import middleware and utilities
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.metrics import PrometheusMetricsMiddleware
from api.middleware.logging import LoggingMiddleware
from api.middleware.tenant import TenantMiddleware
from api.utils.redis_client import redis_client
from api.utils.cache import CacheService, ImageHasher, CacheWarmer
from api.utils.metrics import MetricsCollector, model_loaded as model_loaded_gauge
from api.utils.logging_config import logger, setup_logging
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

# Import authentication and RBAC
from api.auth.jwt import get_current_active_user
from api.auth.rbac import RequirePermission
from api.routes import auth as auth_router
from api.routes import patients as patients_router


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
    cached: bool = False


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

# Add middleware (order matters - innermost first)
app.add_middleware(PrometheusMetricsMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(TenantMiddleware, enable_tenant_isolation=True)
app.add_middleware(RateLimitMiddleware, enable_per_ip=True)

# Include routers
app.include_router(auth_router.router)
app.include_router(patients_router.router)

detector = None
app_start_time = None
executor = None  # ThreadPoolExecutor for CPU-intensive tasks


@app.on_event("startup")
async def startup_event():
    global detector, app_start_time, executor
    import time as time_module
    app_start_time = time_module.time()

    # Initialize thread pool executor for CPU-intensive inference
    # Use number of CPU cores, but cap at 4 for memory efficiency
    import multiprocessing
    max_workers = min(multiprocessing.cpu_count(), 4)
    executor = ThreadPoolExecutor(max_workers=max_workers)
    logger.info(f"Initialized ThreadPoolExecutor with {max_workers} workers")

    # Setup logging
    setup_logging(log_level="INFO", json_logs=True)
    logger.info("Starting Glaucoma Detection API", version="1.0.0")

    # Initialize database (create tables and seed data)
    try:
        from api.database.init_db import init_database
        logger.info("Initializing database...")
        init_database()
    except Exception as e:
        logger.warning(f"Database initialization skipped or failed: {e}")

    # Initialize Redis
    await redis_client.init()

    # Get the project root directory (parent of api folder)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)

    model_path = os.path.join(project_root, 'models', 'best_model.pth')
    scripted_path = os.path.join(project_root, 'models', 'model_scripted.pt')
    config_path = os.path.join(project_root, 'models', 'config.yaml')

    if os.path.exists(scripted_path):
        logger.info("Loading TorchScript model", model_path=scripted_path)
        detector = GlaucomaDetector(scripted_path, config_path)
    elif os.path.exists(model_path):
        logger.info("Loading PyTorch model", model_path=model_path)
        detector = GlaucomaDetector(model_path, config_path)
    else:
        logger.warning("No trained model found",
                      expected_paths=[model_path, scripted_path])
        detector = None

    # Update model metrics
    if detector is not None:
        MetricsCollector.set_model_loaded(True, {
            "version": "1.0.0",
            "type": "pytorch"
        })
        logger.info("Model loaded successfully")

        # Warm cache with model metadata
        await CacheWarmer.warm_model_metadata(detector)
    else:
        MetricsCollector.set_model_loaded(False)

    # Set application info
    MetricsCollector.set_application_info(
        version="1.0.0",
        build_date=datetime.now().isoformat()
    )

    logger.info("API startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global executor
    logger.info("Shutting down API")

    # Shutdown executor
    if executor:
        logger.info("Shutting down ThreadPoolExecutor")
        executor.shutdown(wait=True)

    # Close Redis connection
    await redis_client.close()
    logger.info("Shutdown complete")


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
    import time as time_module

    # Update uptime metric
    if app_start_time:
        uptime = time_module.time() - app_start_time
        MetricsCollector.update_uptime(uptime)

    return HealthResponse(
        status="healthy",
        model_loaded=detector is not None,
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    from fastapi.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


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


async def run_inference_async(image: Image.Image, return_confidence: bool = True) -> dict:
    """
    Run CPU-intensive inference in thread pool to avoid blocking event loop

    Args:
        image: PIL Image to analyze
        return_confidence: Whether to return confidence scores

    Returns:
        Prediction result dictionary
    """
    global executor, detector

    if detector is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded"
        )

    # Run blocking inference in executor
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor,
        partial(detector.predict, image, return_confidence=return_confidence)
    )

    return result


async def get_recommendations_async(result: dict) -> list:
    """
    Get recommendations in thread pool (if computationally intensive)

    Args:
        result: Prediction result

    Returns:
        List of recommendations
    """
    global executor, detector

    # Run in executor (even though it's typically lightweight,
    # this ensures consistency and allows for future expansion)
    loop = asyncio.get_event_loop()
    recommendations = await loop.run_in_executor(
        executor,
        partial(detector.get_recommendations, result)
    )

    return recommendations


@app.post("/predict", response_model=PredictionResponse)
async def predict(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    use_cache: bool = Form(True),
    current_user: User = Depends(RequirePermission("prediction:create")),
    db: Session = Depends(get_db)
):
    """Predict glaucoma from retinal image and save to patient record"""

    if detector is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Train first: cd src && python train.py"
        )

    # Verify patient exists and belongs to current user's tenant
    patient = db.query(Patient).filter(
        and_(
            Patient.patient_id == patient_id,
            Patient.tenant_id == current_user.tenant_id
        )
    ).first()

    if not patient:
        raise HTTPException(
            status_code=404,
            detail=f"Patient with ID '{patient_id}' not found in your organization"
        )

    validate_image(file)
    start_time = time.time()

    try:
        # Generate image hash for caching
        image_hash, image_bytes = await ImageHasher.hash_upload_file(file)

        # Check cache first
        if use_cache and redis_client.is_connected():
            cached_result = await CacheService.get_cached_prediction(
                image_hash,
                model_version="v1"
            )
            if cached_result:
                processing_time = (time.time() - start_time) * 1000
                logger.log_prediction(
                    image_hash=image_hash,
                    result=cached_result['label'],
                    confidence=cached_result['confidence'],
                    duration_ms=processing_time,
                    cached=True
                )
                return PredictionResponse(
                    **cached_result,
                    processing_time_ms=round(processing_time, 2),
                    timestamp=datetime.now().isoformat(),
                    cached=True
                )

        # Cache miss or cache disabled - perform prediction
        image = await load_image_from_upload(file)

        # Run inference asynchronously in thread pool
        result = await run_inference_async(image, return_confidence=True)
        recommendations = await get_recommendations_async(result)

        processing_time = (time.time() - start_time) * 1000

        # Record metrics
        MetricsCollector.record_prediction(
            model_version="v1",
            result=result['label'],
            confidence=result['confidence'],
            risk_level=result['risk_level'],
            duration=processing_time / 1000
        )

        # Log prediction
        logger.log_prediction(
            image_hash=image_hash,
            result=result['label'],
            confidence=result['confidence'],
            duration_ms=processing_time,
            cached=False
        )

        prediction_data = {
            "status": "success",
            "prediction": result['prediction'],
            "label": result['label'],
            "probability": result['probability'],
            "confidence": result['confidence'],
            "risk_level": result['risk_level'],
            "recommendations": recommendations,
        }

        # Save prediction to database
        db_prediction = Prediction(
            tenant_id=current_user.tenant_id,
            patient_id=patient.id,  # Use internal patient.id (integer)
            user_id=current_user.id,
            prediction=result['prediction'],
            label=result['label'],
            probability=result['probability'],
            confidence=result['confidence'],
            risk_level=result['risk_level'],
            image_filename=file.filename,
            image_size=len(image_bytes) if image_bytes else None,
            image_hash=image_hash,
            model_version="v1",
            processing_time_ms=processing_time,
            recommendations=recommendations,
        )

        db.add(db_prediction)
        db.commit()
        db.refresh(db_prediction)

        logger.info(
            f"Prediction saved to database: {db_prediction.prediction_id} for patient {patient.patient_id}",
            extra={
                "prediction_id": db_prediction.prediction_id,
                "patient_id": patient.patient_id,
                "label": result['label'],
                "confidence": result['confidence']
            }
        )

        # Cache the result
        if use_cache and redis_client.is_connected():
            await CacheService.set_cached_prediction(
                image_hash,
                prediction_data,
                model_version="v1"
            )

        return PredictionResponse(
            **prediction_data,
            processing_time_ms=round(processing_time, 2),
            timestamp=datetime.now().isoformat(),
            cached=False
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )


@app.post("/batch-predict")
async def batch_predict(
    files: list[UploadFile] = File(...),
    patient_id: str = Form(...),
    use_cache: bool = Form(True),
    current_user: User = Depends(RequirePermission("prediction:create")),
    db: Session = Depends(get_db)
):
    """Predict glaucoma for multiple images and save to patient record"""

    if detector is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Train first: cd src && python train.py"
        )

    # Verify patient exists and belongs to current user's tenant
    patient = db.query(Patient).filter(
        and_(
            Patient.patient_id == patient_id,
            Patient.tenant_id == current_user.tenant_id
        )
    ).first()

    if not patient:
        raise HTTPException(
            status_code=404,
            detail=f"Patient with ID '{patient_id}' not found in your organization"
        )

    max_batch_size = 20
    if len(files) > max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_batch_size} images allowed"
        )

    start_time = time.time()
    results = []
    cache_hits = 0
    cache_misses = 0

    # Record batch size metric
    MetricsCollector.record_batch_prediction(len(files))

    for idx, file in enumerate(files):
        try:
            validate_image(file)

            # Generate image hash for caching
            image_hash, image_bytes = await ImageHasher.hash_upload_file(file)

            # Check cache first
            cached_result = None
            if use_cache and redis_client.is_connected():
                cached_result = await CacheService.get_cached_prediction(
                    image_hash,
                    model_version="v1"
                )

            if cached_result:
                # Cache hit
                cache_hits += 1
                results.append({
                    "index": idx,
                    "filename": file.filename,
                    **cached_result,
                    "cached": True
                })
            else:
                # Cache miss - perform prediction
                cache_misses += 1
                image = await load_image_from_upload(file)

                # Run inference asynchronously in thread pool
                result = await run_inference_async(image, return_confidence=True)
                recommendations = await get_recommendations_async(result)

                prediction_data = {
                    "status": "success",
                    "prediction": result['prediction'],
                    "label": result['label'],
                    "probability": result['probability'],
                    "confidence": result['confidence'],
                    "risk_level": result['risk_level'],
                    "recommendations": recommendations
                }

                # Save prediction to database
                processing_time_ms = (time.time() - start_time) * 1000
                db_prediction = Prediction(
                    tenant_id=current_user.tenant_id,
                    patient_id=patient.id,
                    user_id=current_user.id,
                    prediction=result['prediction'],
                    label=result['label'],
                    probability=result['probability'],
                    confidence=result['confidence'],
                    risk_level=result['risk_level'],
                    image_filename=file.filename,
                    image_size=len(image_bytes) if image_bytes else None,
                    image_hash=image_hash,
                    model_version="v1",
                    processing_time_ms=processing_time_ms,
                    recommendations=recommendations,
                )

                db.add(db_prediction)
                db.commit()
                db.refresh(db_prediction)

                # Cache the result
                if use_cache and redis_client.is_connected():
                    await CacheService.set_cached_prediction(
                        image_hash,
                        prediction_data,
                        model_version="v1"
                    )

                results.append({
                    "index": idx,
                    "filename": file.filename,
                    "prediction_id": db_prediction.prediction_id,
                    **prediction_data,
                    "cached": False
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
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_hit_rate": f"{(cache_hits / len(files) * 100):.1f}%" if len(files) > 0 else "0%",
        "processing_time_ms": round(processing_time, 2),
        "timestamp": datetime.now().isoformat(),
        "results": results
    })


# Note: Request logging is now handled by LoggingMiddleware


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