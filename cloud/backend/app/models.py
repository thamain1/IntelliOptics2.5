"""SQLAlchemy ORM models for IntelliOptics.

These classes define the database schema used by the backend.  They
roughly mirror the data structures described in the project
specification: users, detectors, queries, escalations, and hubs.  You
may extend these models with additional fields as needed.  UUID
primary keys are used for uniqueness and ease of integration with
external systems.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, Float, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: str = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password: str = Column(String, nullable=True)
    roles: str = Column(String(255), nullable=False, default="reviewer")
    created_at: datetime = Column(DateTime, default=datetime.utcnow)


class Detector(Base):
    __tablename__ = "detectors"

    id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = Column(Text, nullable=False)
    description: str = Column(Text, nullable=True)
    mode: str = Column(Text, nullable=False, default="BINARY")
    query_text: str = Column(Text, nullable=False)
    threshold: float = Column(Float, nullable=False, default=0.75)
    status: str = Column(Text, nullable=False, default="active")
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    deleted_at: datetime = Column(DateTime, nullable=True)  # Soft delete: NULL = active, timestamp = deleted
    
    confidence_threshold: float = Column(Float, default=0.75)
    escalation_type: str = Column(Text, nullable=True)
    group_name: str = Column(Text, nullable=True)
    detector_metadata_serialized: dict = Column("metadata", JSONB, nullable=True, default=lambda: {})
    mode_configuration: dict = Column(JSONB, nullable=True, default=lambda: {})
    patience_time: float = Column(Float, default=0.0)
    
    # Optional fields found in DB
    query: str = Column(Text, nullable=True)
    type: str = Column(Text, nullable=True)
    public_id: str = Column(Text, nullable=False, default=lambda: str(uuid.uuid4())) # Actually handled by trigger but needed for model
    query_type: str = Column(String(32), nullable=True)
    labels: list = Column(JSONB, nullable=True, default=lambda: ["YES", "NO"])
    org_id: str = Column(Text, nullable=True)
    created_by: str = Column(Text, nullable=True)
    site_code: str = Column(Text, nullable=True)

    primary_model_blob_path: str = Column(String(255), nullable=True)
    oodd_model_blob_path: str = Column(String(255), nullable=True)
    model_blob_path: str = Column(String(255), nullable=True) 

    queries = relationship("Query", back_populates="detector")
    config = relationship("DetectorConfig", back_populates="detector", uselist=False, cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="detector")


class DetectorConfig(Base):
    __tablename__ = "detector_configs"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    detector_id: str = Column(String(36), ForeignKey("detectors.id"), unique=True, nullable=False)
    mode: str = Column(String(50), default="BINARY")
    class_names: list = Column(JSONB, nullable=True)
    confidence_threshold: float = Column(Float, default=0.85)
    
    # New configuration fields
    per_class_thresholds: dict = Column(JSONB, nullable=True)
    model_input_config: dict = Column(JSONB, nullable=True)
    model_output_config: dict = Column(JSONB, nullable=True)
    detection_params: dict = Column(JSONB, nullable=True)

    edge_inference_config: dict = Column(JSONB, nullable=True)
    patience_time: float = Column(Float, default=30.0)

    primary_model_blob_path: str = Column(String(255), nullable=True)
    oodd_model_blob_path: str = Column(String(255), nullable=True)

    # ── Item 6: OODD Per-Detector Threshold ─────────────────────────────────
    oodd_calibrated_threshold: float = Column(Float, default=0.444, nullable=True)

    # ── Phase 2: Active Learning — Candidate Model ───────────────────────────
    candidate_model_path: str = Column(String(512), nullable=True)
    candidate_model_version: int = Column(Integer, nullable=True)

    # Open-vocabulary detection
    open_vocab_prompts: list = Column(JSONB, nullable=True)  # Default prompts for OPEN_VOCAB mode

    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    detector = relationship("Detector", back_populates="config")


class DetectorAlertConfig(Base):
    """Configuration for detector-based alerts (e.g., person detected → alert security)."""
    __tablename__ = "detector_alert_configs"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    detector_id: str = Column(String(36), ForeignKey("detectors.id", ondelete="CASCADE"), unique=True, nullable=False)

    enabled: bool = Column(Boolean, default=False)
    alert_name: str = Column(String(200), nullable=True)  # Human-readable alert name

    # Alert condition (when to trigger) - Boolean logic builder
    condition_type: str = Column(String(50), default="LABEL_MATCH")  # LABEL_MATCH, CONFIDENCE_ABOVE, CONFIDENCE_BELOW, ALWAYS
    condition_value: str = Column(String(200), nullable=True)  # e.g., "YES", "Person", "0.9"
    consecutive_count: int = Column(Integer, default=1)  # Require X consecutive matches
    time_window_minutes: int = Column(Integer, nullable=True)  # Alternative: X matches within Y minutes
    confirm_with_cloud: bool = Column(Boolean, default=False)  # Confirm with cloud labelers first

    # Recipients - Email
    alert_emails: list = Column(JSONB, default=list)  # List of email addresses

    # Recipients - SMS
    alert_phones: list = Column(JSONB, default=list)  # List of phone numbers (E.164 format)
    include_image_sms: bool = Column(Boolean, default=True)  # Include image in SMS (MMS)

    # Recipients - Webhook
    alert_webhooks: list = Column(JSONB, default=list)  # List of webhook URLs
    webhook_template: str = Column(Text, nullable=True)  # Jinja template for webhook body
    webhook_headers: dict = Column(JSONB, nullable=True)  # Custom headers for webhook

    # Alert settings
    severity: str = Column(String(20), default="warning")  # critical, warning, info
    cooldown_minutes: int = Column(Integer, default=5)  # Don't spam - min time between same alert
    include_image: bool = Column(Boolean, default=True)  # Include image in email alerts
    custom_message: str = Column(Text, nullable=True)  # Custom alert message template

    # Metadata
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    detector = relationship("Detector", backref="alert_config")


class DetectorAlert(Base):
    """History of alerts triggered by detectors."""
    __tablename__ = "detector_alerts"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    detector_id: str = Column(String(36), ForeignKey("detectors.id", ondelete="CASCADE"), nullable=False)
    query_id: str = Column(String(36), ForeignKey("queries.id", ondelete="SET NULL"), nullable=True)

    # Alert details
    alert_type: str = Column(String(50), default="DETECTION")  # DETECTION, THRESHOLD_EXCEEDED, etc.
    severity: str = Column(String(20), nullable=False)  # critical, warning, info
    message: str = Column(Text, nullable=False)

    # Detection context
    detection_label: str = Column(String(128), nullable=True)
    detection_confidence: float = Column(Float, nullable=True)
    camera_name: str = Column(String(255), nullable=True)
    image_blob_path: str = Column(String(255), nullable=True)

    # Alert status
    sent_to: list = Column(JSONB, default=list)  # List of recipients who received the alert
    email_sent: bool = Column(Boolean, default=False)
    email_sent_at: datetime = Column(DateTime, nullable=True)
    acknowledged: bool = Column(Boolean, default=False)
    acknowledged_at: datetime = Column(DateTime, nullable=True)
    acknowledged_by: str = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    detector = relationship("Detector", backref="detection_alerts")
    query = relationship("Query", backref="detector_alerts")


class Camera(Base):
    __tablename__ = "cameras"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id: str = Column(String(36), ForeignKey("hubs.id", ondelete="CASCADE"), nullable=False)
    name: str = Column(String(255), nullable=False)
    url: str = Column(String(512), nullable=False)
    status: str = Column(String(50), default="active")
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    # Camera inspection fields
    baseline_image_path: str = Column(Text, nullable=True)
    baseline_image_updated_at: datetime = Column(DateTime, nullable=True)
    view_change_detected: bool = Column(Boolean, default=False)
    view_change_detected_at: datetime = Column(DateTime, nullable=True)
    last_health_check: datetime = Column(DateTime, nullable=True)
    current_status: str = Column(String(32), default="unknown")  # connected, degraded, offline, unknown
    health_score: float = Column(Float, nullable=True)  # 0-100 aggregate health metric

    hub = relationship("Hub", back_populates="cameras_list")
    health_records = relationship("CameraHealth", back_populates="camera", cascade="all, delete-orphan")
    alerts = relationship("CameraAlert", back_populates="camera", cascade="all, delete-orphan")
    

class Query(Base):
    __tablename__ = "queries"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    detector_id: str = Column(String(36), ForeignKey("detectors.id"))
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    image_blob_path: str = Column(String(255), nullable=True)
    result_label: str = Column(String(128), nullable=True)
    confidence: float = Column(Float, nullable=True)
    status: str = Column(String(32), default="PENDING")  # PENDING, DONE, ESCALATED
    local_inference: bool = Column(Boolean, default=False)
    escalated: bool = Column(Boolean, default=False)

    # All detections with bounding boxes: [{label, confidence, bbox: [x, y, w, h]}]
    detections_json: list = Column(JSONB, nullable=True)

    # ── Item 6: OODD Drift Tracking ──────────────────────────────────────────
    # in_domain_score from OODD model at inference time (0–1; NULL if no OODD model).
    # Stored so the drift endpoint can compute week-over-week rolling averages.
    oodd_score: float = Column(Float, nullable=True)

    # Ground truth fields for metrics
    ground_truth: str = Column(String(50), nullable=True)  # Human-verified label
    is_correct: bool = Column(Boolean, nullable=True)       # result == ground_truth
    reviewed_by: str = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at: datetime = Column(DateTime, nullable=True)

    detector = relationship("Detector", back_populates="queries")
    escalation = relationship("Escalation", back_populates="query", uselist=False)


class Escalation(Base):
    __tablename__ = "escalations"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_id: str = Column(String(36), ForeignKey("queries.id"))
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    reason: str = Column(Text, nullable=True)
    resolved: bool = Column(Boolean, default=False)

    query = relationship("Query", back_populates="escalation")


class Deployment(Base):
    __tablename__ = "deployments"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    detector_id: str = Column(String(36), ForeignKey("detectors.id"), nullable=False)
    hub_id: str = Column(String(36), ForeignKey("hubs.id"), nullable=False)
    config: dict = Column(JSONB, nullable=False)
    status: str = Column(String(50), default="PENDING") # PENDING, SUCCESS, FAILED
    cameras: dict = Column(JSONB, nullable=True) # Array of {name, url, sampling_interval}
    deployed_at: datetime = Column(DateTime, default=datetime.utcnow)
    
    detector = relationship("Detector", back_populates="deployments")
    hub = relationship("Hub", back_populates="deployments")


class AlertSettings(Base):
    __tablename__ = "alert_settings"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # SendGrid
    sendgrid_api_key: str = Column(String, nullable=True)
    from_email: str = Column(String, nullable=True)
    # Twilio
    twilio_account_sid: str = Column(String, nullable=True)
    twilio_auth_token: str = Column(String, nullable=True)
    twilio_phone_from: str = Column(String, nullable=True)
    # HTTP Endpoint
    alert_function_url: str = Column(String, nullable=True)
    # General
    recipients: dict = Column(JSONB, default=lambda: {"emails": [], "phones": []})
    triggers: dict = Column(JSONB, default=lambda: {"low_confidence": False, "oodd": False, "camera_health": False})
    batching: dict = Column(JSONB, default=lambda: {"strategy": "immediate", "size": 1, "interval_minutes": 5})
    rate_limiting: dict = Column(JSONB, default=lambda: {"max_per_hour": 100})
    created_at: datetime = Column(DateTime, default=datetime.utcnow)


class Hub(Base):
    __tablename__ = "hubs"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = Column(String(128), nullable=False)
    status: str = Column(String(32), default="unknown")  # online/offline/unknown
    last_ping: datetime = Column(DateTime, nullable=True)
    location: str = Column(String(255), nullable=True)
    cameras: list = Column(JSONB, nullable=True) # Legacy List of discovered cameras
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    cameras_list = relationship("Camera", back_populates="hub", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="hub")


class Feedback(Base):
    __tablename__ = "feedback"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_id: str = Column(String(36), ForeignKey("queries.id"), nullable=False)
    reviewer_id: str = Column(String(36), nullable=True)
    label: str = Column(String(16), nullable=False)
    confidence: float = Column(Float, nullable=True)
    notes: str = Column(Text, nullable=True)
    count: int = Column(Integer, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    query = relationship("Query")


class InspectionConfig(Base):
    """Configuration for camera inspection system."""
    __tablename__ = "inspection_config"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: str = Column(String(36), nullable=True)

    # Inspection interval in minutes
    inspection_interval_minutes: int = Column(Integer, nullable=False, default=60)

    # Alert thresholds
    offline_threshold_minutes: int = Column(Integer, default=5)
    fps_drop_threshold_pct: float = Column(Float, default=0.5)  # Alert if FPS drops below 50%
    latency_threshold_ms: int = Column(Integer, default=1000)
    view_change_threshold: float = Column(Float, default=0.7)  # SSIM threshold

    # Alert recipients (array of email addresses)
    alert_emails: list = Column(JSONB, default=list)

    # Retention policies
    dashboard_retention_days: int = Column(Integer, default=30)
    database_retention_days: int = Column(Integer, default=90)

    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InspectionRun(Base):
    """Track each inspection cycle."""
    __tablename__ = "inspection_runs"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    started_at: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: datetime = Column(DateTime, nullable=True)
    total_cameras: int = Column(Integer, nullable=True)
    cameras_inspected: int = Column(Integer, nullable=True)
    cameras_healthy: int = Column(Integer, nullable=True)
    cameras_warning: int = Column(Integer, nullable=True)
    cameras_failed: int = Column(Integer, nullable=True)
    status: str = Column(String(32), default="running")  # running, completed, failed

    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    health_records = relationship("CameraHealth", back_populates="inspection_run")
    alerts = relationship("CameraAlert", back_populates="inspection_run")


class CameraHealth(Base):
    """Camera health metrics from each inspection."""
    __tablename__ = "camera_health"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id: str = Column(String(36), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    inspection_run_id: str = Column(String(36), ForeignKey("inspection_runs.id", ondelete="CASCADE"), nullable=True)
    timestamp: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Connection
    status: str = Column(String(32), nullable=False)  # connected, degraded, offline
    connection_error: str = Column(Text, nullable=True)

    # Stream quality
    fps: float = Column(Float, nullable=True)
    expected_fps: float = Column(Float, default=30.0)
    resolution: str = Column(String(32), nullable=True)  # "1920x1080"
    bitrate_kbps: int = Column(Integer, nullable=True)

    # Image quality
    avg_brightness: float = Column(Float, nullable=True)  # 0.0 to 1.0
    sharpness_score: float = Column(Float, nullable=True)  # 0.0 to 1.0
    motion_detected: bool = Column(Boolean, nullable=True)

    # Operational
    last_frame_at: datetime = Column(DateTime, nullable=True)
    uptime_24h: float = Column(Float, nullable=True)  # Percentage
    error_count_1h: int = Column(Integer, nullable=True)

    # Network
    latency_ms: int = Column(Integer, nullable=True)
    packet_loss_pct: float = Column(Float, nullable=True)

    # View change detection
    view_similarity_score: float = Column(Float, nullable=True)  # SSIM score 0-1
    view_change_detected: bool = Column(Boolean, default=False)
    feature_match_count: int = Column(Integer, nullable=True)

    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    camera = relationship("Camera", back_populates="health_records")
    inspection_run = relationship("InspectionRun", back_populates="health_records")


class CameraAlert(Base):
    """Camera alerts and notifications."""
    __tablename__ = "camera_alerts"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id: str = Column(String(36), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    inspection_run_id: str = Column(String(36), ForeignKey("inspection_runs.id", ondelete="CASCADE"), nullable=True)

    # Alert details
    alert_type: str = Column(String(64), nullable=False)  # offline, fps_drop, view_change, quality_degradation, network_issue
    severity: str = Column(String(32), nullable=False)  # critical, warning, info
    message: str = Column(Text, nullable=True)
    details: dict = Column(JSONB, nullable=True)  # Specific metrics that triggered alert

    # Alert management
    acknowledged: bool = Column(Boolean, default=False)
    acknowledged_by: str = Column(String(36), ForeignKey("users.id"), nullable=True)
    acknowledged_at: datetime = Column(DateTime, nullable=True)

    muted_until: datetime = Column(DateTime, nullable=True)
    muted_by: str = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Email tracking
    email_sent: bool = Column(Boolean, default=False)
    email_sent_at: datetime = Column(DateTime, nullable=True)

    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    camera = relationship("Camera", back_populates="alerts")
    inspection_run = relationship("InspectionRun", back_populates="alerts")
    acknowledged_user = relationship("User", foreign_keys=[acknowledged_by])
    muted_user = relationship("User", foreign_keys=[muted_by])


class DemoStreamConfig(Base):
    """Saved preset configurations for YouTube stream demos."""
    __tablename__ = "demo_stream_configs"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = Column(String(128), nullable=False)
    description: str = Column(Text, nullable=True)

    # Stream source
    youtube_url: str = Column(String(512), nullable=False)
    youtube_video_id: str = Column(String(32), nullable=True)

    # Capture configuration
    capture_mode: str = Column(String(32), default="polling")  # polling, motion, manual
    polling_interval_ms: int = Column(Integer, default=2000)
    motion_threshold: float = Column(Float, default=0.15)

    # Detector assignments (array of detector IDs)
    detector_ids: list = Column(JSONB, default=list)

    # Metadata
    created_by: str = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = relationship("DemoSession", back_populates="config", cascade="all, delete-orphan")


class DemoSession(Base):
    """Active and historical demo sessions."""
    __tablename__ = "demo_sessions"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_id: str = Column(String(36), ForeignKey("demo_stream_configs.id"), nullable=True)

    # Session info
    name: str = Column(String(128), nullable=False)
    youtube_url: str = Column(String(512), nullable=False)
    youtube_video_id: str = Column(String(32), nullable=True)

    # Capture settings (snapshot at session start)
    capture_mode: str = Column(String(32), nullable=False)
    polling_interval_ms: int = Column(Integer, nullable=True)
    motion_threshold: float = Column(Float, nullable=True)

    # Detector assignments
    detector_ids: list = Column(JSONB, default=list)

    # YOLOWorld settings
    yoloworld_prompts: str = Column(Text, nullable=True)  # Comma-separated prompts for open-vocabulary detection

    # Session state
    status: str = Column(String(32), default="active")  # active, stopped, completed
    started_at: datetime = Column(DateTime, default=datetime.utcnow)
    stopped_at: datetime = Column(DateTime, nullable=True)

    # Statistics
    total_frames_captured: int = Column(Integer, default=0)
    total_detections: int = Column(Integer, default=0)
    
    # Error tracking
    error_message: str = Column(Text, nullable=True)
    last_frame_at: datetime = Column(DateTime, nullable=True)

    # User
    created_by: str = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Relationships
    config = relationship("DemoStreamConfig", back_populates="sessions")
    results = relationship("DemoDetectionResult", back_populates="session", cascade="all, delete-orphan")


class ImageAnnotation(Base):
    """Bounding box annotations for images, supporting both model and human annotations."""
    __tablename__ = "image_annotations"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_id: str = Column(String(36), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False)
    image_blob_path: str = Column(String(255), nullable=False)  # Links to image storage

    # Normalized bounding box coordinates (0.0 to 1.0, resolution-independent)
    x: float = Column(Float, nullable=False)  # Left edge (normalized)
    y: float = Column(Float, nullable=False)  # Top edge (normalized)
    width: float = Column(Float, nullable=False)  # Box width (normalized)
    height: float = Column(Float, nullable=False)  # Box height (normalized)

    # Classification
    label: str = Column(String(128), nullable=False)
    confidence: float = Column(Float, nullable=True)  # Null for human annotations

    # Source tracking
    source: str = Column(String(32), nullable=False, default="human")  # "model" or "human"
    model_name: str = Column(String(128), nullable=True)  # Model that generated this (if source=model)

    # Review status
    review_status: str = Column(String(32), default="pending")  # pending, approved, rejected, corrected
    reviewed_by: str = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at: datetime = Column(DateTime, nullable=True)

    # Timestamps
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    query = relationship("Query", backref="annotations")
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class DemoDetectionResult(Base):
    """Detection results from demo sessions."""
    __tablename__ = "demo_detection_results"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: str = Column(String(36), ForeignKey("demo_sessions.id", ondelete="CASCADE"), nullable=False)
    query_id: str = Column(String(36), ForeignKey("queries.id", ondelete="SET NULL"), nullable=True)
    detector_id: str = Column(String(36), ForeignKey("detectors.id"), nullable=True)

    # Result data
    result_label: str = Column(String(128), nullable=True)
    confidence: float = Column(Float, nullable=True)
    status: str = Column(String(32), default="PENDING")  # PENDING, DONE, ERROR

    # Frame info
    frame_number: int = Column(Integer, nullable=True)
    capture_method: str = Column(String(32), nullable=True)  # polling, motion, manual

    # Timing
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    completed_at: datetime = Column(DateTime, nullable=True)

    # Relationships
    session = relationship("DemoSession", back_populates="results")
    detector = relationship("Detector")
    query = relationship("Query")


# ====================
# Vehicle Identification
# ====================

class VehicleRecord(Base):
    """Vehicle identification records from the YOLOE + VLM pipeline."""
    __tablename__ = "vehicle_records"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    detector_id: str = Column(String(36), ForeignKey("detectors.id"), nullable=True)
    plate_text: str = Column(String(20), nullable=True)
    vehicle_color: str = Column(String(50), nullable=True)
    vehicle_type: str = Column(String(50), nullable=True)  # car, truck, van, SUV
    vehicle_make_model: str = Column(String(128), nullable=True)
    confidence: float = Column(Float, default=0.0)
    bbox: dict = Column(JSONB, nullable=True)  # [x1, y1, x2, y2] normalized
    plate_bbox: dict = Column(JSONB, nullable=True)
    image_url: str = Column(String(512), nullable=True)
    camera_id: str = Column(String(36), nullable=True)
    captured_at: datetime = Column(DateTime, default=datetime.utcnow)

    detector = relationship("Detector", backref="vehicle_records")


# ====================
# Forensic Search (BOLO)
# ====================

class ForensicSearchJob(Base):
    """Video forensic search job."""
    __tablename__ = "forensic_search_jobs"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_text: str = Column(String(500), nullable=False)
    source_type: str = Column(String(50), default="video_file")  # dvr, rtsp_recording, video_file
    source_url: str = Column(String(512), nullable=False)
    camera_ids: list = Column(JSONB, nullable=True)
    time_range_start: datetime = Column(DateTime, nullable=True)
    time_range_end: datetime = Column(DateTime, nullable=True)
    status: str = Column(String(32), default="PENDING")  # PENDING, RUNNING, COMPLETED, CANCELLED, ERROR
    progress_pct: float = Column(Float, default=0.0)
    total_frames: int = Column(Integer, default=0)
    frames_scanned: int = Column(Integer, default=0)
    matches_found: int = Column(Integer, default=0)
    created_by: str = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    results = relationship("ForensicSearchResult", back_populates="job", cascade="all, delete-orphan")


class ForensicSearchResult(Base):
    """A single match from a forensic search."""
    __tablename__ = "forensic_search_results"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: str = Column(String(36), ForeignKey("forensic_search_jobs.id", ondelete="CASCADE"), nullable=False)
    timestamp_sec: float = Column(Float, nullable=True)
    camera_id: str = Column(String(36), nullable=True)
    confidence: float = Column(Float, default=0.0)
    bbox: dict = Column(JSONB, nullable=True)  # [x1, y1, x2, y2] normalized
    label: str = Column(String(128), nullable=True)
    description: str = Column(Text, nullable=True)  # VLM description of what was found
    frame_url: str = Column(String(512), nullable=True)  # Stored in Supabase Storage
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    job = relationship("ForensicSearchJob", back_populates="results")


# ====================
# Maven Parking
# ====================

class ParkingZone(Base):
    """Parking zone configuration."""
    __tablename__ = "parking_zones"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = Column(String(128), nullable=False)
    camera_id: str = Column(String(36), nullable=True)
    max_capacity: int = Column(Integer, default=0)
    current_occupancy: int = Column(Integer, default=0)
    zone_type: str = Column(String(50), default="general")  # permit, metered, handicap, fire, general
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("ParkingEvent", back_populates="zone", cascade="all, delete-orphan")


class ParkingEvent(Base):
    """Parking entry/exit/violation events."""
    __tablename__ = "parking_events"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    zone_id: str = Column(String(36), ForeignKey("parking_zones.id", ondelete="CASCADE"), nullable=False)
    vehicle_record_id: str = Column(String(36), ForeignKey("vehicle_records.id"), nullable=True)
    event_type: str = Column(String(32), nullable=False)  # ENTRY, EXIT, VIOLATION
    timestamp: datetime = Column(DateTime, default=datetime.utcnow)

    zone = relationship("ParkingZone", back_populates="events")
    vehicle = relationship("VehicleRecord")


class ParkingViolation(Base):
    """Parking violations with evidence."""
    __tablename__ = "parking_violations"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: str = Column(String(36), ForeignKey("parking_events.id", ondelete="CASCADE"), nullable=False)
    violation_type: str = Column(String(64), nullable=False)  # expired, no_permit, fire_lane, double_park
    evidence_url: str = Column(String(512), nullable=True)
    resolved: bool = Column(Boolean, default=False)
    resolved_at: datetime = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    event = relationship("ParkingEvent", backref="violations")


# ── Phase 1: Active Learning — Training Dataset Record ───────────────────────

class TrainingDataset(Base):
    """Created each time a labeled dataset is exported for retraining."""
    __tablename__ = "training_datasets"

    id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    detector_id: str = Column(String, ForeignKey("detectors.id"), nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    sample_count: int = Column(Integer, nullable=True)
    val_count: int = Column(Integer, nullable=True)
    storage_path: str = Column(String(512), nullable=True)
    label_distribution: dict = Column(JSONB, nullable=True)
    triggered_by: str = Column(String(255), nullable=True)

    detector = relationship("Detector", backref="training_datasets")


# ── Phase 2: Active Learning — Training Run Record ────────────────────────────

class TrainingRun(Base):
    """One fine-tuning cycle.  Created by trigger-training, updated by trainer."""
    __tablename__ = "training_runs"

    id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    detector_id: str = Column(String, ForeignKey("detectors.id"), nullable=False)
    dataset_id: str = Column(String, ForeignKey("training_datasets.id"), nullable=True)
    started_at: datetime = Column(DateTime, default=datetime.utcnow)
    completed_at: datetime = Column(DateTime, nullable=True)
    status: str = Column(String(32), default="pending")  # pending, running, completed, failed
    base_model_version: int = Column(Integer, nullable=True)
    candidate_model_path: str = Column(String(512), nullable=True)
    metrics: dict = Column(JSONB, nullable=True)
    triggered_by: str = Column(String(255), nullable=True)
    error_log: str = Column(Text, nullable=True)

    detector = relationship("Detector", backref="training_runs")
    dataset = relationship("TrainingDataset", backref="training_runs")


class DataRetentionSettings(Base):
    """Settings for automatic data retention and cleanup."""
    __tablename__ = "data_retention_settings"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Retention settings
    retention_days: int = Column(Integer, default=30)  # Delete queries older than this
    exclude_verified: bool = Column(Boolean, default=True)  # Don't delete queries with ground_truth
    auto_cleanup_enabled: bool = Column(Boolean, default=False)  # Enable automatic cleanup

    # Training export settings
    default_sample_percentage: float = Column(Float, default=10.0)  # Default % for training export
    stratify_by_label: bool = Column(Boolean, default=True)  # Balance samples across labels

    # Timestamps
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_cleanup_at: datetime = Column(DateTime, nullable=True)
    last_cleanup_count: int = Column(Integer, nullable=True)  # Number of records deleted in last cleanup
