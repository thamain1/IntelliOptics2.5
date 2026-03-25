"""API endpoints for escalations review."""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from .. import models, schemas
from ..dependencies import get_db, get_current_reviewer, get_current_user


router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("", response_model=List[schemas.EscalationOut])
def list_escalations(db: Session = Depends(get_db), user=Depends(get_current_user)) -> List[models.Escalation]:
    """Return escalations that are unresolved."""
    return db.query(models.Escalation).filter(models.Escalation.resolved == False).all()


@router.post("/generate", response_model=schemas.GenerateEscalationsResponse)
def generate_escalations(
    request: schemas.GenerateEscalationsRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> schemas.GenerateEscalationsResponse:
    """
    Generate escalation records from existing queries based on criteria.

    - labels: Escalate queries where result_label contains any of these (case-insensitive)
    - confidence_threshold: Escalate queries with confidence below this value
    - detector_id: Limit to specific detector
    - dry_run: If true, only return counts without creating records
    """
    # Build base query for queries without escalations
    query = db.query(models.Query).outerjoin(
        models.Escalation, models.Query.id == models.Escalation.query_id
    ).filter(models.Escalation.id == None)  # No existing escalation

    # Filter by detector if specified
    if request.detector_id:
        query = query.filter(models.Query.detector_id == request.detector_id)

    # Build OR conditions for labels and confidence
    conditions = []

    # Label matching (case-insensitive partial match)
    if request.labels:
        label_conditions = []
        for label in request.labels:
            label_conditions.append(
                func.lower(models.Query.result_label).contains(label.lower())
            )
        conditions.append(or_(*label_conditions))

    # Confidence threshold
    if request.confidence_threshold is not None:
        conditions.append(models.Query.confidence < request.confidence_threshold)

    # Apply OR of all conditions (match any criteria)
    if conditions:
        query = query.filter(or_(*conditions))
    else:
        # No criteria specified, return empty
        return schemas.GenerateEscalationsResponse(
            created=0, skipped=0, total_matched=0, escalation_ids=[]
        )

    # Get count first for total_matched
    total_matched = query.count()

    if request.dry_run:
        return schemas.GenerateEscalationsResponse(
            created=0,
            skipped=0,
            total_matched=total_matched,
            escalation_ids=[]
        )

    # Apply limit if specified
    if request.limit:
        query = query.limit(request.limit)

    # Get matching queries
    matching_queries = query.all()

    # Create escalations
    created_ids = []
    for q in matching_queries:
        # Build reason string
        reasons = []
        if request.labels and q.result_label:
            for label in request.labels:
                if label.lower() in q.result_label.lower():
                    reasons.append(f"Label match: {label}")
                    break
        if request.confidence_threshold and q.confidence and q.confidence < request.confidence_threshold:
            reasons.append(f"Low confidence: {q.confidence:.2%}")

        reason = "; ".join(reasons) if reasons else "Manual escalation"

        # Create escalation record
        escalation = models.Escalation(
            id=str(uuid.uuid4()),
            query_id=q.id,
            reason=reason,
            resolved=False
        )
        db.add(escalation)

        # Update query status
        q.escalated = True
        q.status = "ESCALATED"

        created_ids.append(escalation.id)

    db.commit()

    return schemas.GenerateEscalationsResponse(
        created=len(created_ids),
        skipped=0,
        total_matched=total_matched,
        escalation_ids=created_ids
    )


@router.post("/{escalation_id}/resolve", response_model=schemas.EscalationOut)
def resolve_escalation(
    escalation_id: str,
    db: Session = Depends(get_db),
    reviewer=Depends(get_current_reviewer),
) -> models.Escalation:
    esc = db.query(models.Escalation).filter(models.Escalation.id == escalation_id).first()
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    esc.resolved = True
    db.commit()
    db.refresh(esc)
    return esc
