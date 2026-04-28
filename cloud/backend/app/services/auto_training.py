"""Phase 6: Auto-training scheduler.

Runs every AUTO_TRAINING_CHECK_INTERVAL_HOURS (default 1 h).
For each detector, counts labeled samples (ground_truth queries + feedback)
created since the last completed training run. When the count reaches
AUTO_TRAINING_MIN_SAMPLES (default 100), automatically exports a dataset
and triggers YOLO fine-tuning via the existing API endpoints.

Sends SendGrid email on trigger and on completion/failure (auto-triggered
runs only, tracked via TrainingRun.notified_at).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from jose import jwt
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from .. import models

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_internal_token() -> str:
    """Generate a short-lived admin JWT for internal self-HTTP calls.

    sub must be a real user email — auth.get_current_user does a DB lookup by sub.
    Use the permanent support admin account that's guaranteed to exist.
    """
    settings = get_settings()
    secret = settings.jwt_secret or settings.api_secret_key
    payload = {
        "sub": "jmorgan@4wardmotions.com",
        "exp": datetime.utcnow() + timedelta(hours=2),
    }
    return jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)


def _send_email(subject: str, html: str) -> None:
    settings = get_settings()
    if not settings.sendgrid_api_key:
        log.info("SendGrid not configured — skipping auto-training email: %s", subject)
        return

    notify_str = settings.auto_training_notify_emails or ""
    recipients = [e.strip() for e in notify_str.split(",") if e.strip()]
    if not recipients and settings.alert.alert_email_to:
        recipients = [e.strip() for e in settings.alert.alert_email_to.split(",") if e.strip()]
    if not recipients:
        log.warning("Auto-training: no recipients configured (set AUTO_TRAINING_NOTIFY_EMAILS or ALERT_EMAIL_TO)")
        return

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        from_email = settings.sendgrid_from_email or "alerts@4wardmotions.com"
        msg = Mail(from_email=from_email, to_emails=recipients, subject=subject, html_content=html)
        SendGridAPIClient(settings.sendgrid_api_key).send(msg)
        log.info("Auto-training email sent to %s — %s", recipients, subject)
    except Exception as exc:
        log.warning("Auto-training email failed: %s", exc)


def _count_new_samples(db: Session, detector_id: str, since: Optional[datetime]) -> int:
    """Count labeled feedback + queries-with-ground-truth since `since`."""
    q = db.query(models.Query).filter(
        models.Query.detector_id == detector_id,
        models.Query.ground_truth.isnot(None),
    )
    if since:
        q = q.filter(models.Query.created_at > since)

    f = (
        db.query(models.Feedback)
        .join(models.Query, models.Feedback.query_id == models.Query.id)
        .filter(models.Query.detector_id == detector_id)
    )
    if since:
        f = f.filter(models.Feedback.created_at > since)

    return q.count() + f.count()


# ── Per-detector check ────────────────────────────────────────────────────────

def _check_detector(
    db: Session,
    detector: models.Detector,
    min_samples: int,
    base_url: str,
    headers: dict,
) -> None:
    # Skip if a run is already active
    active = db.query(models.TrainingRun).filter(
        models.TrainingRun.detector_id == detector.id,
        models.TrainingRun.status.in_(["pending", "running"]),
    ).first()
    if active:
        return

    # Use the most recent run of ANY terminal status (completed OR failed) to
    # set the sample window. This prevents re-triggering on the same samples
    # when training keeps failing — new training only fires once enough NEW
    # samples arrive after the last attempt.
    last_run = (
        db.query(models.TrainingRun)
        .filter(
            models.TrainingRun.detector_id == detector.id,
            models.TrainingRun.status.in_(["completed", "failed"]),
        )
        .order_by(models.TrainingRun.started_at.desc())
        .first()
    )
    since = last_run.started_at if last_run else None

    count = _count_new_samples(db, detector.id, since)
    log.debug("Detector %s (%s): %d new samples since %s", detector.id, detector.name, count, since)

    if count < min_samples:
        return

    log.info("Auto-triggering training for %s (%s) — %d samples >= %d", detector.name, detector.id, count, min_samples)

    # ── Export dataset ────────────────────────────────────────────────────────
    try:
        export_res = requests.get(
            f"{base_url}/detectors/{detector.id}/export-dataset",
            headers=headers,
            timeout=300,
        )
        if export_res.status_code != 200:
            log.warning("Auto-export failed for %s: HTTP %d — %s", detector.id, export_res.status_code, export_res.text[:200])
            return
        dataset_id = export_res.json()["dataset_id"]
    except Exception as exc:
        log.warning("Auto-export error for %s: %s", detector.id, exc)
        return

    # ── Trigger training ──────────────────────────────────────────────────────
    try:
        trigger_res = requests.post(
            f"{base_url}/detectors/{detector.id}/trigger-training",
            headers=headers,
            params={"dataset_id": dataset_id, "epochs": 50, "base_model": "yolov8s.pt"},
            timeout=30,
        )
        if trigger_res.status_code not in (200, 201, 202):
            log.warning("Auto-trigger failed for %s: HTTP %d — %s", detector.id, trigger_res.status_code, trigger_res.text[:200])
            return
        run_id = trigger_res.json()["training_run_id"]
    except Exception as exc:
        log.warning("Auto-trigger error for %s: %s", detector.id, exc)
        return

    # Mark as auto-triggered
    run = db.query(models.TrainingRun).filter(models.TrainingRun.id == run_id).first()
    if run:
        run.auto_triggered = True
        db.commit()

    _send_email(
        subject=f"[IntelliOptics] Auto-training started — {detector.name}",
        html=f"""
        <h2 style="color:#1a73e8">Auto-training triggered</h2>
        <p>Detector <strong>{detector.name}</strong> accumulated
        <strong>{count} new labeled samples</strong> (threshold: {min_samples}),
        triggering automatic YOLO fine-tuning.</p>
        <table cellpadding="6" style="border-collapse:collapse">
          <tr><td style="color:#666">Detector ID</td><td><code>{detector.id}</code></td></tr>
          <tr><td style="color:#666">Run ID</td><td><code>{run_id}</code></td></tr>
          <tr><td style="color:#666">Dataset ID</td><td><code>{dataset_id}</code></td></tr>
          <tr><td style="color:#666">Started at</td><td>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</td></tr>
        </table>
        <p>Review metrics and promote the candidate model once training completes.</p>
        """,
    )


# ── Completion notifications ──────────────────────────────────────────────────

def _notify_completions(db: Session) -> None:
    """Send completion/failure emails for auto-triggered runs not yet notified."""
    runs = (
        db.query(models.TrainingRun)
        .filter(
            models.TrainingRun.status.in_(["completed", "failed"]),
            models.TrainingRun.auto_triggered.is_(True),
            models.TrainingRun.notified_at.is_(None),
        )
        .all()
    )

    for run in runs:
        detector = db.query(models.Detector).filter(models.Detector.id == run.detector_id).first()
        det_name = detector.name if detector else run.detector_id

        if run.status == "completed":
            m = run.metrics or {}

            def pct(v):
                return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else "—"

            _send_email(
                subject=f"[IntelliOptics] Training completed — {det_name}",
                html=f"""
                <h2 style="color:#0f9d58">Training completed</h2>
                <p>Detector <strong>{det_name}</strong> fine-tuning finished successfully.</p>
                <table cellpadding="6" style="border-collapse:collapse">
                  <tr><td style="color:#666">Run ID</td><td><code>{run.id}</code></td></tr>
                  <tr><td style="color:#666">mAP50</td><td><strong>{pct(m.get('mAP50'))}</strong></td></tr>
                  <tr><td style="color:#666">Precision</td><td>{pct(m.get('precision'))}</td></tr>
                  <tr><td style="color:#666">Recall</td><td>{pct(m.get('recall'))}</td></tr>
                  <tr><td style="color:#666">Candidate model</td><td>{run.candidate_model_path or '—'}</td></tr>
                </table>
                <p>Review and promote the candidate model in the IntelliOptics dashboard.</p>
                """,
            )
        else:
            _send_email(
                subject=f"[IntelliOptics] Training failed — {det_name}",
                html=f"""
                <h2 style="color:#d93025">Training failed</h2>
                <p>Detector <strong>{det_name}</strong> — run <code>{run.id}</code> failed.</p>
                <pre style="background:#f8f8f8;padding:12px;border-radius:4px">{run.error_log or 'No error details available'}</pre>
                """,
            )

        run.notified_at = datetime.utcnow()

    if runs:
        db.commit()
        log.info("Sent %d completion notification(s)", len(runs))


# ── Main entry point (called by APScheduler) ──────────────────────────────────

def run_auto_training_cycle() -> None:
    """Sync entry point for APScheduler BackgroundScheduler."""
    settings = get_settings()
    if not settings.auto_training_enabled:
        return

    min_samples = settings.auto_training_min_samples
    base_url = "http://localhost:8000"
    headers = {"Authorization": f"Bearer {_make_internal_token()}"}

    db = SessionLocal()
    try:
        detectors = db.query(models.Detector).all()
        log.info("Auto-training cycle: %d detectors, threshold=%d", len(detectors), min_samples)

        for detector in detectors:
            try:
                _check_detector(db, detector, min_samples, base_url, headers)
            except Exception as exc:
                log.error("Auto-training check failed for detector %s: %s", detector.id, exc)

        _notify_completions(db)
    except Exception as exc:
        log.error("Auto-training cycle error: %s", exc)
    finally:
        db.close()
