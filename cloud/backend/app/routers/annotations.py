"""API endpoints for image annotations."""
from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_db, get_current_user


router = APIRouter(prefix="/annotations", tags=["annotations"])


@router.get("", response_model=List[schemas.ImageAnnotationOut])
def list_annotations(
    query_id: str = None,
    source: str = None,
    review_status: str = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> List[models.ImageAnnotation]:
    """List annotations with optional filters."""
    query = db.query(models.ImageAnnotation)

    if query_id:
        query = query.filter(models.ImageAnnotation.query_id == query_id)
    if source:
        query = query.filter(models.ImageAnnotation.source == source)
    if review_status:
        query = query.filter(models.ImageAnnotation.review_status == review_status)

    return query.order_by(models.ImageAnnotation.created_at.desc()).limit(limit).all()


@router.get("/by-query/{query_id}", response_model=List[schemas.ImageAnnotationOut])
def get_annotations_by_query(
    query_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> List[models.ImageAnnotation]:
    """Get all annotations for a specific query."""
    # Verify query exists
    q = db.query(models.Query).filter(models.Query.id == query_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")

    return db.query(models.ImageAnnotation).filter(
        models.ImageAnnotation.query_id == query_id
    ).all()


@router.get("/{annotation_id}", response_model=schemas.ImageAnnotationOut)
def get_annotation(
    annotation_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.ImageAnnotation:
    """Get a specific annotation by ID."""
    annotation = db.query(models.ImageAnnotation).filter(
        models.ImageAnnotation.id == annotation_id
    ).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    return annotation


@router.post("", response_model=schemas.ImageAnnotationOut, status_code=201)
def create_annotation(
    payload: schemas.ImageAnnotationCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.ImageAnnotation:
    """Create a new annotation."""
    # Verify query exists
    q = db.query(models.Query).filter(models.Query.id == payload.query_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")

    annotation = models.ImageAnnotation(
        query_id=payload.query_id,
        image_blob_path=payload.image_blob_path,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        label=payload.label,
        confidence=payload.confidence,
        source=payload.source,
        model_name=payload.model_name,
        review_status="pending"
    )

    db.add(annotation)
    db.commit()
    db.refresh(annotation)

    return annotation


@router.post("/bulk", response_model=List[schemas.ImageAnnotationOut], status_code=201)
def create_annotations_bulk(
    payload: schemas.ImageAnnotationBulkCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> List[models.ImageAnnotation]:
    """Create multiple annotations at once (e.g., from model predictions)."""
    # Verify query exists
    q = db.query(models.Query).filter(models.Query.id == payload.query_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")

    annotations = []
    for ann in payload.annotations:
        annotation = models.ImageAnnotation(
            query_id=payload.query_id,
            image_blob_path=payload.image_blob_path,
            x=ann.x,
            y=ann.y,
            width=ann.width,
            height=ann.height,
            label=ann.label,
            confidence=ann.confidence,
            source=payload.source,
            model_name=payload.model_name,
            review_status="pending"
        )
        db.add(annotation)
        annotations.append(annotation)

    db.commit()
    for ann in annotations:
        db.refresh(ann)

    return annotations


@router.put("/{annotation_id}", response_model=schemas.ImageAnnotationOut)
def update_annotation(
    annotation_id: str,
    payload: schemas.ImageAnnotationUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.ImageAnnotation:
    """Update an existing annotation."""
    annotation = db.query(models.ImageAnnotation).filter(
        models.ImageAnnotation.id == annotation_id
    ).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    # Update only provided fields
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(annotation, field, value)

    annotation.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(annotation)

    return annotation


@router.post("/{annotation_id}/review", response_model=schemas.ImageAnnotationOut)
def review_annotation(
    annotation_id: str,
    payload: schemas.ImageAnnotationReview,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.ImageAnnotation:
    """Review an annotation (approve, reject, or correct)."""
    annotation = db.query(models.ImageAnnotation).filter(
        models.ImageAnnotation.id == annotation_id
    ).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    annotation.review_status = payload.review_status
    annotation.reviewed_by = user.id if hasattr(user, 'id') else None
    annotation.reviewed_at = datetime.utcnow()

    # Apply corrections if provided
    if payload.review_status == "corrected":
        if payload.corrected_x is not None:
            annotation.x = payload.corrected_x
        if payload.corrected_y is not None:
            annotation.y = payload.corrected_y
        if payload.corrected_width is not None:
            annotation.width = payload.corrected_width
        if payload.corrected_height is not None:
            annotation.height = payload.corrected_height
        if payload.corrected_label is not None:
            annotation.label = payload.corrected_label
        # Mark as human-corrected
        annotation.source = "human"

    db.commit()
    db.refresh(annotation)

    return annotation


@router.delete("/{annotation_id}", status_code=204)
def delete_annotation(
    annotation_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Delete an annotation."""
    annotation = db.query(models.ImageAnnotation).filter(
        models.ImageAnnotation.id == annotation_id
    ).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    db.delete(annotation)
    db.commit()

    return None


@router.delete("/by-query/{query_id}", status_code=204)
def delete_annotations_by_query(
    query_id: str,
    source: str = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Delete all annotations for a query, optionally filtered by source."""
    query = db.query(models.ImageAnnotation).filter(
        models.ImageAnnotation.query_id == query_id
    )

    if source:
        query = query.filter(models.ImageAnnotation.source == source)

    query.delete()
    db.commit()

    return None
