"""
Patient management routes
Handles CRUD operations for patient records with RBAC and multi-tenancy
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from ..database.session import get_db
from ..database.models import Patient, User, Prediction
from ..auth.jwt import get_current_active_user
from ..auth.rbac import RequirePermission
from ..utils.logging_config import logger

# ============================================================================
# Router Setup
# ============================================================================

router = APIRouter(prefix="/api/v1/patients", tags=["patients"])

# ============================================================================
# Request/Response Models
# ============================================================================

class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    mrn: str
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    medical_history: Optional[dict] = {}
    risk_factors: Optional[dict] = {}

class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    medical_history: Optional[dict] = None
    risk_factors: Optional[dict] = None
    is_active: Optional[bool] = None

class PatientResponse(BaseModel):
    id: int
    patient_id: str
    tenant_id: int
    first_name: str
    last_name: str
    mrn: str
    date_of_birth: Optional[datetime]
    gender: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    medical_history: dict
    risk_factors: dict
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class PatientListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    patients: List[PatientResponse]

class PatientWithPredictions(PatientResponse):
    predictions: List[dict]
    total_predictions: int
    latest_prediction: Optional[dict]

# ============================================================================
# Helper Functions
# ============================================================================

def get_patient_or_404(
    patient_id: str,
    tenant_id: int,
    db: Session
) -> Patient:
    """Get patient by ID or raise 404"""
    patient = db.query(Patient).filter(
        and_(
            Patient.patient_id == patient_id,
            Patient.tenant_id == tenant_id
        )
    ).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID '{patient_id}' not found"
        )

    return patient

# ============================================================================
# Patient CRUD Endpoints
# ============================================================================

@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_data: PatientCreate,
    current_user: User = Depends(RequirePermission("patient:create")),
    db: Session = Depends(get_db)
):
    """
    Create a new patient record

    Requires: patient:create permission
    Available to: admin, doctor, technician
    """
    # Check if MRN already exists for this tenant
    existing = db.query(Patient).filter(
        and_(
            Patient.tenant_id == current_user.tenant_id,
            Patient.mrn == patient_data.mrn
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Patient with MRN '{patient_data.mrn}' already exists in your organization"
        )

    # Create new patient
    new_patient = Patient(
        tenant_id=current_user.tenant_id,
        first_name=patient_data.first_name,
        last_name=patient_data.last_name,
        mrn=patient_data.mrn,
        date_of_birth=patient_data.date_of_birth,
        gender=patient_data.gender,
        email=patient_data.email,
        phone=patient_data.phone,
        address=patient_data.address,
        medical_history=patient_data.medical_history or {},
        risk_factors=patient_data.risk_factors or {},
        is_active=True
    )

    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)

    logger.info(
        f"Patient created: {new_patient.patient_id} by user {current_user.email}",
        extra={
            "patient_id": new_patient.patient_id,
            "user_id": current_user.id,
            "tenant_id": current_user.tenant_id
        }
    )

    return new_patient


@router.get("", response_model=PatientListResponse)
async def list_patients(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or MRN"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(RequirePermission("patient:read")),
    db: Session = Depends(get_db)
):
    """
    List all patients with pagination and search

    Requires: patient:read permission
    Available to: all roles
    Multi-tenant: Only shows patients from user's organization
    """
    # Base query - filter by tenant
    query = db.query(Patient).filter(Patient.tenant_id == current_user.tenant_id)

    # Apply search filter
    if search:
        search_filter = or_(
            Patient.first_name.ilike(f"%{search}%"),
            Patient.last_name.ilike(f"%{search}%"),
            Patient.mrn.ilike(f"%{search}%"),
            Patient.email.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    # Apply active filter
    if is_active is not None:
        query = query.filter(Patient.is_active == is_active)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    patients = query.order_by(Patient.created_at.desc()).offset(offset).limit(page_size).all()

    logger.info(
        f"Patient list accessed by user {current_user.email}",
        extra={
            "user_id": current_user.id,
            "tenant_id": current_user.tenant_id,
            "total_patients": total,
            "page": page
        }
    )

    return PatientListResponse(
        total=total,
        page=page,
        page_size=page_size,
        patients=patients
    )


@router.get("/{patient_id}", response_model=PatientWithPredictions)
async def get_patient(
    patient_id: str,
    current_user: User = Depends(RequirePermission("patient:read")),
    db: Session = Depends(get_db)
):
    """
    Get patient details with prediction history

    Requires: patient:read permission
    Available to: all roles
    Multi-tenant: Only shows patients from user's organization
    """
    patient = get_patient_or_404(patient_id, current_user.tenant_id, db)

    # Get patient's predictions
    predictions = db.query(Prediction).filter(
        Prediction.patient_id == patient.id
    ).order_by(Prediction.created_at.desc()).all()

    # Format predictions
    predictions_data = [
        {
            "id": p.id,
            "prediction_id": p.prediction_id,
            "label": p.label,
            "confidence": p.confidence,
            "risk_level": p.risk_level,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "is_reviewed": p.is_reviewed
        }
        for p in predictions
    ]

    latest_prediction = predictions_data[0] if predictions_data else None

    logger.info(
        f"Patient details accessed: {patient_id} by user {current_user.email}",
        extra={
            "patient_id": patient_id,
            "user_id": current_user.id,
            "tenant_id": current_user.tenant_id
        }
    )

    # Create response with predictions
    return PatientWithPredictions(
        id=patient.id,
        patient_id=patient.patient_id,
        tenant_id=patient.tenant_id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        mrn=patient.mrn,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        email=patient.email,
        phone=patient.phone,
        address=patient.address,
        medical_history=patient.medical_history or {},
        risk_factors=patient.risk_factors or {},
        is_active=patient.is_active,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
        predictions=predictions_data,
        total_predictions=len(predictions_data),
        latest_prediction=latest_prediction
    )


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: str,
    patient_data: PatientUpdate,
    current_user: User = Depends(RequirePermission("patient:update")),
    db: Session = Depends(get_db)
):
    """
    Update patient information

    Requires: patient:update permission
    Available to: admin, technician
    Multi-tenant: Only updates patients from user's organization
    """
    patient = get_patient_or_404(patient_id, current_user.tenant_id, db)

    # Update fields if provided
    update_data = patient_data.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(patient, field, value)

    db.commit()
    db.refresh(patient)

    logger.info(
        f"Patient updated: {patient_id} by user {current_user.email}",
        extra={
            "patient_id": patient_id,
            "user_id": current_user.id,
            "tenant_id": current_user.tenant_id,
            "updated_fields": list(update_data.keys())
        }
    )

    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: str,
    current_user: User = Depends(RequirePermission("patient:delete")),
    db: Session = Depends(get_db)
):
    """
    Delete a patient (soft delete - marks as inactive)

    Requires: patient:delete permission
    Available to: admin only
    Multi-tenant: Only deletes patients from user's organization
    """
    patient = get_patient_or_404(patient_id, current_user.tenant_id, db)

    # Soft delete - mark as inactive instead of hard delete
    patient.is_active = False
    db.commit()

    logger.warning(
        f"Patient deleted: {patient_id} by user {current_user.email}",
        extra={
            "patient_id": patient_id,
            "user_id": current_user.id,
            "tenant_id": current_user.tenant_id
        }
    )

    return None


@router.get("/{patient_id}/predictions")
async def get_patient_predictions(
    patient_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequirePermission("prediction:read")),
    db: Session = Depends(get_db)
):
    """
    Get all predictions for a specific patient

    Requires: prediction:read permission
    Available to: all roles
    Multi-tenant: Only shows predictions from user's organization
    """
    patient = get_patient_or_404(patient_id, current_user.tenant_id, db)

    # Get predictions
    query = db.query(Prediction).filter(Prediction.patient_id == patient.id)

    total = query.count()
    offset = (page - 1) * page_size

    predictions = query.order_by(Prediction.created_at.desc()).offset(offset).limit(page_size).all()

    predictions_data = [
        {
            "id": p.id,
            "prediction_id": p.prediction_id,
            "label": p.label,
            "confidence": p.confidence,
            "probability": p.probability,
            "risk_level": p.risk_level,
            "recommendations": p.recommendations or [],
            "is_reviewed": p.is_reviewed,
            "reviewed_by_user_id": p.reviewed_by_user_id,
            "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None
        }
        for p in predictions
    ]

    logger.info(
        f"Patient predictions accessed: {patient_id} by user {current_user.email}",
        extra={
            "patient_id": patient_id,
            "user_id": current_user.id,
            "tenant_id": current_user.tenant_id,
            "total_predictions": total
        }
    )

    return {
        "patient_id": patient.patient_id,
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "total": total,
        "page": page,
        "page_size": page_size,
        "predictions": predictions_data
    }


@router.get("/{patient_id}/stats")
async def get_patient_stats(
    patient_id: str,
    current_user: User = Depends(RequirePermission("patient:read")),
    db: Session = Depends(get_db)
):
    """
    Get patient statistics and summary

    Requires: patient:read permission
    Available to: all roles
    Multi-tenant: Only shows stats from user's organization
    """
    patient = get_patient_or_404(patient_id, current_user.tenant_id, db)

    # Get all predictions
    predictions = db.query(Prediction).filter(Prediction.patient_id == patient.id).all()

    # Calculate stats
    total_predictions = len(predictions)
    glaucoma_detections = sum(1 for p in predictions if p.label == "glaucoma")
    normal_results = sum(1 for p in predictions if p.label == "normal")

    high_risk = sum(1 for p in predictions if p.risk_level == "High Risk")
    moderate_risk = sum(1 for p in predictions if p.risk_level == "Moderate Risk")
    low_risk = sum(1 for p in predictions if p.risk_level == "Low Risk")

    avg_confidence = sum(p.confidence for p in predictions) / total_predictions if total_predictions > 0 else 0

    latest_prediction = max(predictions, key=lambda p: p.created_at) if predictions else None

    return {
        "patient_id": patient.patient_id,
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "mrn": patient.mrn,
        "total_predictions": total_predictions,
        "glaucoma_detections": glaucoma_detections,
        "normal_results": normal_results,
        "risk_distribution": {
            "high": high_risk,
            "moderate": moderate_risk,
            "low": low_risk
        },
        "average_confidence": round(avg_confidence, 2),
        "latest_prediction": {
            "label": latest_prediction.label,
            "risk_level": latest_prediction.risk_level,
            "confidence": latest_prediction.confidence,
            "date": latest_prediction.created_at.isoformat()
        } if latest_prediction else None,
        "medical_history": patient.medical_history or {},
        "risk_factors": patient.risk_factors or {}
    }
