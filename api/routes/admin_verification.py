"""
Admin Routes for Doctor Image Verification
==========================================
Endpoints for doctors to review and label incoming prediction images.

This module implements a Human-in-the-Loop (HITL) workflow where:
1. AI predictions are saved to data/incoming/ with metadata
2. Doctors review and verify/correct the labels
3. Verified images can be merged into training data for retraining

Authentication: Requires Admin or Doctor role (admin:verify permission)
"""

import os
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from enum import Enum

# Import authentication and database
from api.auth.jwt import get_current_active_user
from api.auth.rbac import RequirePermission
from api.database.models import User
from api.utils.logging_config import logger

# Create router
router = APIRouter(prefix="/admin", tags=["Admin - Doctor Verification"])

# Paths - use absolute paths from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
INCOMING_DIR = PROJECT_ROOT / "data" / "incoming"
VERIFIED_DIR = PROJECT_ROOT / "data" / "verified"
TRAIN_DIR = PROJECT_ROOT / "data" / "train"


class LabelChoice(str, Enum):
    GLAUCOMA = "glaucoma"
    NORMAL = "normal"
    UNCERTAIN = "uncertain"


class PendingImage(BaseModel):
    filename: str
    prediction: str
    probability: float
    confidence: float
    timestamp: str
    patient_id: Optional[str] = None


class LabelRequest(BaseModel):
    filename: str
    doctor_label: LabelChoice
    doctor_notes: Optional[str] = None


class LabelResponse(BaseModel):
    status: str
    message: str
    moved_to: str


class VerificationStats(BaseModel):
    pending_count: int
    verified_glaucoma: int
    verified_normal: int
    uncertain_count: int


# Ensure directories exist
def ensure_dirs():
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    (VERIFIED_DIR / "glaucoma").mkdir(parents=True, exist_ok=True)
    (VERIFIED_DIR / "normal").mkdir(parents=True, exist_ok=True)
    (VERIFIED_DIR / "uncertain").mkdir(parents=True, exist_ok=True)


@router.get("/pending-images", response_model=List[PendingImage])
async def get_pending_images(
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("timestamp", enum=["timestamp", "confidence", "prediction"]),
    current_user: User = Depends(RequirePermission("admin:verify"))
):
    """
    Get list of images pending doctor verification.
    
    Requires: Admin or Doctor role (admin:verify permission)
    Returns images from data/incoming/ that need to be labeled.
    """
    ensure_dirs()
    logger.info(f"Doctor {current_user.username} fetching pending images")
    
    pending = []
    
    # Find all JSON metadata files
    for json_file in INCOMING_DIR.glob("*.json"):
        try:
            with open(json_file, 'r') as f:
                metadata = json.load(f)
            
            # Check if corresponding image exists
            img_file = INCOMING_DIR / metadata.get('filename', '')
            if img_file.exists():
                pending.append(PendingImage(
                    filename=metadata.get('filename', json_file.stem),
                    prediction=metadata.get('prediction', 'unknown'),
                    probability=metadata.get('probability', 0.0),
                    confidence=metadata.get('confidence', 0.0),
                    timestamp=metadata.get('timestamp', ''),
                    patient_id=metadata.get('patient_id', None)
                ))
        except Exception as e:
            continue
    
    # Sort
    if sort_by == "confidence":
        pending.sort(key=lambda x: x.confidence, reverse=True)
    elif sort_by == "prediction":
        pending.sort(key=lambda x: x.prediction)
    else:
        pending.sort(key=lambda x: x.timestamp, reverse=True)
    
    return pending[:limit]


@router.post("/label-image", response_model=LabelResponse)
async def label_image(
    request: LabelRequest,
    current_user: User = Depends(RequirePermission("admin:verify"))
):
    """
    Doctor labels an image with verified diagnosis.
    
    Requires: Admin or Doctor role (admin:verify permission)
    This moves the image from incoming/ to verified/{label}/ 
    for future training.
    """
    ensure_dirs()
    
    logger.info(
        f"Doctor {current_user.username} labeling image {request.filename} as {request.doctor_label.value}",
        extra={
            "doctor_id": current_user.id,
            "filename": request.filename,
            "label": request.doctor_label.value
        }
    )
    
    # Find the image
    img_path = INCOMING_DIR / request.filename
    json_path = INCOMING_DIR / request.filename.replace('.jpg', '.json').replace('.png', '.json')
    
    if not img_path.exists():
        raise HTTPException(status_code=404, detail=f"Image not found: {request.filename}")
    
    # Determine destination
    if request.doctor_label == LabelChoice.GLAUCOMA:
        dest_dir = VERIFIED_DIR / "glaucoma"
    elif request.doctor_label == LabelChoice.NORMAL:
        dest_dir = VERIFIED_DIR / "normal"
    else:
        dest_dir = VERIFIED_DIR / "uncertain"
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Move image
    dest_img = dest_dir / request.filename
    shutil.move(str(img_path), str(dest_img))
    
    # Update and move metadata
    if json_path.exists():
        with open(json_path, 'r') as f:
            metadata = json.load(f)
        
        metadata['doctor_label'] = request.doctor_label.value
        metadata['doctor_notes'] = request.doctor_notes
        metadata['verified_at'] = datetime.now().isoformat()
        metadata['verified'] = True
        metadata['verified_by'] = current_user.username
        metadata['verified_by_id'] = current_user.id
        
        dest_json = dest_dir / json_path.name
        with open(dest_json, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        os.remove(json_path)
    
    return LabelResponse(
        status="success",
        message=f"Image labeled as {request.doctor_label.value}",
        moved_to=str(dest_dir)
    )


@router.get("/verification-stats", response_model=VerificationStats)
async def get_verification_stats(
    current_user: User = Depends(RequirePermission("admin:verify"))
):
    """
    Get statistics on pending and verified images.
    
    Requires: Admin or Doctor role (admin:verify permission)
    """
    ensure_dirs()
    
    def count_images(dir_path: Path) -> int:
        if not dir_path.exists():
            return 0
        return len(list(dir_path.glob("*.jpg"))) + len(list(dir_path.glob("*.png")))
    
    return VerificationStats(
        pending_count=count_images(INCOMING_DIR),
        verified_glaucoma=count_images(VERIFIED_DIR / "glaucoma"),
        verified_normal=count_images(VERIFIED_DIR / "normal"),
        uncertain_count=count_images(VERIFIED_DIR / "uncertain")
    )


@router.post("/merge-to-training")
async def merge_verified_to_training(
    min_images: int = Query(10, description="Minimum verified images required to merge"),
    clear_after_merge: bool = Query(False, description="Remove images from verified/ after copying to train/"),
    current_user: User = Depends(RequirePermission("admin:verify"))
):
    """
    Merge verified images into training dataset.
    
    Requires: Admin or Doctor role (admin:verify permission)
    Call this when you have enough verified images and want to retrain.
    
    Args:
        min_images: Minimum number of verified images before allowing merge
        clear_after_merge: If True, removes verified images after copying to avoid duplicates
    """
    ensure_dirs()
    
    logger.info(
        f"Admin {current_user.username} initiating merge to training",
        extra={"clear_after_merge": clear_after_merge}
    )
    
    stats = {
        "glaucoma_added": 0,
        "normal_added": 0,
        "errors": [],
        "cleared": clear_after_merge
    }
    
    # Merge glaucoma
    glaucoma_src = VERIFIED_DIR / "glaucoma"
    glaucoma_dst = TRAIN_DIR / "glaucoma"
    glaucoma_dst.mkdir(parents=True, exist_ok=True)
    
    for img in list(glaucoma_src.glob("*.jpg")) + list(glaucoma_src.glob("*.png")):
        try:
            dst = glaucoma_dst / f"verified_{img.name}"
            shutil.copy2(str(img), str(dst))
            stats["glaucoma_added"] += 1
            
            # Clear source if requested
            if clear_after_merge:
                os.remove(img)
                # Also remove metadata JSON if exists
                json_file = glaucoma_src / img.name.replace('.jpg', '.json').replace('.png', '.json')
                if json_file.exists():
                    os.remove(json_file)
        except Exception as e:
            stats["errors"].append(f"glaucoma/{img.name}: {str(e)}")
    
    # Merge normal
    normal_src = VERIFIED_DIR / "normal"
    normal_dst = TRAIN_DIR / "normal"
    normal_dst.mkdir(parents=True, exist_ok=True)
    
    for img in list(normal_src.glob("*.jpg")) + list(normal_src.glob("*.png")):
        try:
            dst = normal_dst / f"verified_{img.name}"
            shutil.copy2(str(img), str(dst))
            stats["normal_added"] += 1
            
            # Clear source if requested
            if clear_after_merge:
                os.remove(img)
                # Also remove metadata JSON if exists
                json_file = normal_src / img.name.replace('.jpg', '.json').replace('.png', '.json')
                if json_file.exists():
                    os.remove(json_file)
        except Exception as e:
            stats["errors"].append(f"normal/{img.name}: {str(e)}")
    
    total = stats["glaucoma_added"] + stats["normal_added"]
    
    logger.info(
        f"Merge completed: {total} images added to training",
        extra={"details": stats, "merged_by": current_user.username}
    )
    
    return {
        "status": "success",
        "message": f"Added {total} verified images to training data",
        "details": stats,
        "merged_by": current_user.username,
        "next_step": "Run: python src/train.py --config config/config.yaml"
    }


@router.get("/image/{filename}")
async def get_image_for_review(
    filename: str,
    current_user: User = Depends(RequirePermission("admin:verify"))
):
    """
    Get image details for doctor review.
    
    Requires: Admin or Doctor role (admin:verify permission)
    """
    ensure_dirs()
    
    img_path = INCOMING_DIR / filename
    json_path = INCOMING_DIR / filename.replace('.jpg', '.json').replace('.png', '.json')
    
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    metadata = {}
    if json_path.exists():
        with open(json_path, 'r') as f:
            metadata = json.load(f)
    
    return {
        "filename": filename,
        "image_url": f"/admin/incoming-image/{filename}",
        "metadata": metadata
    }


@router.get("/incoming-image/{filename}")
async def get_incoming_image_file(
    filename: str,
    current_user: User = Depends(RequirePermission("admin:verify"))
):
    """
    Stream the actual image file for doctor review.
    
    Requires: Admin or Doctor role (admin:verify permission)
    Returns the image file with proper content-type for display.
    """
    ensure_dirs()
    
    img_path = INCOMING_DIR / filename
    
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Determine content type
    suffix = img_path.suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp"
    }
    content_type = content_types.get(suffix, "application/octet-stream")
    
    return FileResponse(
        path=str(img_path),
        media_type=content_type,
        filename=filename
    )
