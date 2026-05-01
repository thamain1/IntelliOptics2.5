"""Pydantic models for request and response bodies.

These classes define the data shapes exchanged between the client and
server.  They serve as a contract for the API and provide
serialization, validation and documentation support.  Nested models
can be used to represent complex entities.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    email: str
    roles: str
    created_at: datetime


# --- Alert Settings Schemas ---

class AlertTriggerConfig(BaseModel):
    low_confidence: bool = False
    confidence_threshold: float = Field(0.80, ge=0.0, le=1.0)
    oodd: bool = False
    oodd_threshold: float = Field(0.50, ge=0.0, le=1.0)
    camera_health_critical: bool = False
    edge_device_offline: bool = False


class AlertBatchingConfig(BaseModel):
    strategy: str = Field("immediate", max_length=50) # immediate, count, interval
    count_threshold: Optional[int] = Field(10, ge=1)
    interval_minutes: Optional[int] = Field(15, ge=1)


class AlertRateLimitingConfig(BaseModel):
    max_per_hour: int = Field(100, ge=0)


class AlertSettingsBase(BaseModel):
    # SendGrid
    sendgrid_api_key: Optional[str] = None
    from_email: Optional[str] = None
    # Twilio
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_from: Optional[str] = None
    # HTTP Endpoint
    alert_function_url: Optional[str] = None
    # General
    recipients: Dict[str, List[str]] = Field(default_factory=lambda: {"emails": [], "phones": []})
    triggers: AlertTriggerConfig = Field(default_factory=AlertTriggerConfig)
    batching: AlertBatchingConfig = Field(default_factory=AlertBatchingConfig)
    rate_limiting: AlertRateLimitingConfig = Field(default_factory=AlertRateLimitingConfig)


class AlertSettingsUpdate(AlertSettingsBase):
    pass


class AlertSettingsOut(AlertSettingsBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: datetime

# --- End Alert Settings Schemas ---


# --- Detector Configuration Schemas ---

class EdgeInferenceConfig(BaseModel):
    always_return_edge_prediction: bool = False
    disable_cloud_escalation: bool = False
    min_time_between_escalations: float = 2.0


class DetectorConfigBase(BaseModel):
    mode: str = Field("OPEN_VOCAB", max_length=50)
    class_names: Optional[List[str]] = None
    per_class_thresholds: Optional[Dict[str, float]] = None
    confidence_threshold: float = Field(0.85, ge=0.0, le=1.0)
    patience_time: float = Field(30.0, ge=0.0)
    model_input_config: Optional[Dict[str, Any]] = None
    model_output_config: Optional[Dict[str, Any]] = None
    detection_params: Optional[Dict[str, Any]] = None
    edge_inference_config: Optional[EdgeInferenceConfig] = None
    open_vocab_prompts: Optional[List[str]] = None  # Default prompts for OPEN_VOCAB mode


class DetectorConfigUpdate(DetectorConfigBase):
    pass


class DetectorConfigOut(DetectorConfigBase):
    model_config = ConfigDict(from_attributes=True)
    
    detector_id: str

# --- End Detector Configuration Schemas ---


class DetectorCreate(BaseModel):
    # Basic Info
    name: str = Field(..., min_length=3, max_length=128)
    description: Optional[str] = Field(None, max_length=500)
    query_text: Optional[str] = Field(None, max_length=200)
    group_name: Optional[str] = Field(None, max_length=128)
    detector_metadata_serialized: Optional[dict] = Field(None, alias="metadata", description="Custom key-value pairs for deployment tracking")

    # Detection Configuration (REQUIRED)
    mode: str = Field("OPEN_VOCAB", pattern="^(BINARY|MULTICLASS|COUNTING|BOUNDING_BOX|OPEN_VOCAB)$")
    class_names: Optional[List[str]] = Field(None, min_length=1, max_length=50)
    open_vocab_prompts: Optional[List[str]] = Field(None, description="Default text prompts for OPEN_VOCAB mode")
    confidence_threshold: float = Field(0.85, ge=0.0, le=1.0)

    # Edge Inference Profile
    edge_inference_profile: Optional[str] = Field("default", pattern="^(default|offline|aggressive)$")

    # Advanced (optional)
    patience_time: Optional[float] = Field(30.0, ge=0.0)
    min_time_between_escalations: Optional[float] = Field(2.0, ge=0.0)
    mode_configuration: Optional[dict] = Field(None, description="Mode-specific configuration (e.g., max_count for COUNTING)")
    pipeline_config: Optional[str] = Field(None, description="Advanced AI pipeline configuration (expert only)")

    model_config = ConfigDict(populate_by_name=True)


class DetectorUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None
    query_text: Optional[str] = None
    group_name: Optional[str] = Field(None, max_length=128)


class DetectorOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, 
        protected_namespaces=(), 
        populate_by_name=True
    )

    id: str
    name: str
    description: Optional[str] = None
    query_text: Optional[str] = None
    group_name: Optional[str] = None
    detector_metadata_serialized: Optional[dict] = None
    model_blob_path: Optional[str]
    primary_model_blob_path: Optional[str]
    oodd_model_blob_path: Optional[str]
    created_at: datetime
    deleted_at: Optional[datetime] = None
    config: Optional[DetectorConfigOut] = None


class DetectorMetricsOut(BaseModel):
    detector_id: str
    balanced_accuracy: Optional[float] = None
    sensitivity: Optional[float] = None  # Accuracy for YES
    specificity: Optional[float] = None  # Accuracy for NO
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    total_queries: int
    time_range: str = "7d"
    message: Optional[str] = None

    class Config:
        from_attributes = True


# --- Deployment Schemas ---

class CameraStreamConfig(BaseModel):
    name: str
    url: str
    sampling_interval: float = 2.0

class DeploymentCreate(BaseModel):
    hub_id: str
    detector_id: str
    cameras: List[CameraStreamConfig] = Field(default_factory=list)


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    detector_id: str
    hub_id: str
    config: Dict[str, Any]
    deployed_at: datetime
    status: str
    cameras: Optional[List[Dict[str, Any]]] = None

# --- End Deployment Schemas ---


class QueryCreate(BaseModel):
    detector_id: str
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    want_async: Optional[bool] = False


class QueryGroundTruthUpdate(BaseModel):
    ground_truth: str  # e.g., "yes", "no", "defect", "normal"


class Detection(BaseModel):
    """Single detection with bounding box."""
    label: str
    confidence: float
    bbox: Optional[List[float]] = None  # [x, y, width, height] normalized 0-1


class QueryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    detector_id: Optional[str] = None  # Can be None for YOLOWorld queries
    created_at: datetime
    image_blob_path: Optional[str] = None
    image_url: Optional[str] = None  # Signed URL for image access
    result_label: Optional[str] = None
    confidence: Optional[float] = None
    status: str
    local_inference: bool
    escalated: bool
    ground_truth: Optional[str] = None
    is_correct: Optional[bool] = None
    detections_json: Optional[List[Dict[str, Any]]] = None  # All detections with bboxes


class QueryListResponse(BaseModel):
    """Paginated list of queries."""
    queries: List[QueryOut]
    total: int
    skip: int
    limit: int


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    query_id: str
    created_at: datetime
    reason: Optional[str]
    resolved: bool


class GenerateEscalationsRequest(BaseModel):
    """Request to generate escalations from existing queries."""
    labels: List[str] = Field(default_factory=list, description="Labels to escalate (case-insensitive partial match)")
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Escalate queries below this confidence")
    detector_id: Optional[str] = Field(None, description="Limit to specific detector")
    limit: Optional[int] = Field(None, ge=1, le=10000, description="Maximum number of escalations to create")
    dry_run: bool = Field(default=True, description="If true, only return count without creating escalations")


class GenerateEscalationsResponse(BaseModel):
    """Response from escalation generation."""
    created: int
    skipped: int
    total_matched: int
    escalation_ids: List[str] = Field(default_factory=list)


class CameraCreate(BaseModel):
    name: str
    url: str


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    url: str
    status: str
    hub_id: str
    created_at: datetime


class HubOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    status: str
    last_ping: Optional[datetime]
    location: Optional[str]
    cameras: Optional[List[CameraOut]] = None
    created_at: datetime


class FeedbackCreate(BaseModel):
    label: str
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    notes: Optional[str] = None
    count: Optional[int] = None


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    query_id: str
    reviewer_id: Optional[str]
    label: str
    confidence: Optional[float]
    notes: Optional[str]
    count: Optional[int]
    created_at: datetime


class UserCreate(BaseModel):
    email: str
    password: str
    roles: str = Field("reviewer")


class UserUpdate(BaseModel):
    roles: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# ============================================================
# Camera Inspection Schemas
# ============================================================

class InspectionConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: Optional[str]
    inspection_interval_minutes: int
    offline_threshold_minutes: int
    fps_drop_threshold_pct: float
    latency_threshold_ms: int
    view_change_threshold: float
    alert_emails: list
    dashboard_retention_days: int
    database_retention_days: int
    created_at: datetime
    updated_at: datetime


class InspectionConfigUpdate(BaseModel):
    inspection_interval_minutes: Optional[int] = None
    offline_threshold_minutes: Optional[int] = None
    fps_drop_threshold_pct: Optional[float] = None
    latency_threshold_ms: Optional[int] = None
    view_change_threshold: Optional[float] = None
    alert_emails: Optional[list] = None
    dashboard_retention_days: Optional[int] = None
    database_retention_days: Optional[int] = None


class CameraHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    camera_id: str
    timestamp: datetime
    status: str
    connection_error: Optional[str]
    fps: Optional[float]
    expected_fps: float
    resolution: Optional[str]
    bitrate_kbps: Optional[int]
    avg_brightness: Optional[float]
    sharpness_score: Optional[float]
    motion_detected: Optional[bool]
    last_frame_at: Optional[datetime]
    uptime_24h: Optional[float]
    error_count_1h: Optional[int]
    latency_ms: Optional[int]
    packet_loss_pct: Optional[float]
    view_similarity_score: Optional[float]
    view_change_detected: bool
    feature_match_count: Optional[int]


class CameraAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    camera_id: str
    alert_type: str
    severity: str
    message: Optional[str]
    details: Optional[dict]
    acknowledged: bool
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    muted_until: Optional[datetime]
    muted_by: Optional[str]
    email_sent: bool
    email_sent_at: Optional[datetime]
    created_at: datetime


class CameraWithHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url: str
    hub_id: str
    current_status: str
    health_score: Optional[float]
    baseline_image_path: Optional[str]
    baseline_image_updated_at: Optional[datetime]
    view_change_detected: bool
    view_change_detected_at: Optional[datetime]
    last_health_check: Optional[datetime]
    created_at: datetime


class InspectionDashboardCamera(BaseModel):
    camera: CameraWithHealthOut
    hub_name: str
    health: Optional[CameraHealthOut]
    alerts: list[CameraAlertOut]


class InspectionDashboardSummary(BaseModel):
    total: int
    healthy: int
    warning: int
    failed: int


class InspectionDashboard(BaseModel):
    summary: InspectionDashboardSummary
    cameras: list[InspectionDashboardCamera]
    last_updated: datetime


class InspectionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    started_at: datetime
    completed_at: Optional[datetime]
    total_cameras: Optional[int]
    cameras_inspected: Optional[int]
    cameras_healthy: Optional[int]
    cameras_warning: Optional[int]
    cameras_failed: Optional[int]
    status: str
    created_at: datetime


class MuteAlertsRequest(BaseModel):
    mute_days: int = Field(ge=1, le=30, description="Number of days to mute alerts (1-30)")


# --- Detector Alert Schemas ---

class DetectorAlertConfigOut(BaseModel):
    """Schema for detector alert configuration output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    detector_id: str
    enabled: bool
    alert_name: Optional[str] = None
    condition_type: str  # LABEL_MATCH, CONFIDENCE_ABOVE, CONFIDENCE_BELOW, ALWAYS
    condition_value: Optional[str]
    consecutive_count: int = 1
    time_window_minutes: Optional[int] = None
    confirm_with_cloud: bool = False
    alert_emails: list[str] = []
    alert_phones: list[str] = []
    include_image_sms: bool = True
    alert_webhooks: list[str] = []
    webhook_template: Optional[str] = None
    webhook_headers: Optional[dict] = None
    severity: str  # critical, warning, info
    cooldown_minutes: int
    include_image: bool = True
    custom_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class DetectorAlertConfigUpdate(BaseModel):
    """Schema for updating detector alert configuration."""
    enabled: Optional[bool] = None
    alert_name: Optional[str] = None
    condition_type: Optional[str] = None
    condition_value: Optional[str] = None
    consecutive_count: Optional[int] = Field(None, ge=1, le=100)
    time_window_minutes: Optional[int] = Field(None, ge=1, le=1440)
    confirm_with_cloud: Optional[bool] = None
    alert_emails: Optional[list[str]] = None
    alert_phones: Optional[list[str]] = None
    include_image_sms: Optional[bool] = None
    alert_webhooks: Optional[list[str]] = None
    webhook_template: Optional[str] = None
    webhook_headers: Optional[dict] = None
    severity: Optional[str] = None
    cooldown_minutes: Optional[int] = Field(None, ge=1, le=1440)  # 1 min to 24 hours
    include_image: Optional[bool] = None
    custom_message: Optional[str] = None


class DetectorAlertOut(BaseModel):
    """Schema for detector alert history output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    detector_id: str
    query_id: Optional[str]
    alert_type: str
    severity: str
    message: str
    detection_label: Optional[str]
    detection_confidence: Optional[float]
    camera_name: Optional[str]
    image_blob_path: Optional[str]
    sent_to: list[str]
    email_sent: bool
    email_sent_at: Optional[datetime]
    acknowledged: bool
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    created_at: datetime


class AcknowledgeAlertRequest(BaseModel):
    """Schema for acknowledging an alert."""
    acknowledged_by: Optional[str] = None  # User ID (optional if auth not required)


# ==================== Demo Stream Schemas ====================

class DemoStreamConfigBase(BaseModel):
    """Base schema for demo stream configuration."""
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    youtube_url: str = Field(..., max_length=512)
    capture_mode: str = Field(default="polling", pattern="^(polling|motion|manual)$")
    polling_interval_ms: Optional[int] = Field(default=2000, ge=500, le=60000)
    motion_threshold: Optional[float] = Field(default=0.15, ge=0.0, le=1.0)
    detector_ids: list[str] = Field(default_factory=list)


class DemoStreamConfigCreate(DemoStreamConfigBase):
    """Schema for creating a new demo stream configuration."""
    pass


class DemoStreamConfigUpdate(BaseModel):
    """Schema for updating a demo stream configuration."""
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None
    youtube_url: Optional[str] = Field(None, max_length=512)
    capture_mode: Optional[str] = Field(None, pattern="^(polling|motion|manual)$")
    polling_interval_ms: Optional[int] = Field(None, ge=500, le=60000)
    motion_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    detector_ids: Optional[list[str]] = None


class DemoStreamConfigOut(DemoStreamConfigBase):
    """Schema for demo stream configuration output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    youtube_video_id: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


class DemoSessionCreate(BaseModel):
    """Schema for creating a new demo session."""
    config_id: Optional[str] = None
    name: Optional[str] = Field(None, max_length=128)
    youtube_url: str = Field(..., max_length=512)
    capture_mode: str = Field(..., pattern="^(polling|motion|manual)$")
    polling_interval_ms: Optional[int] = Field(default=2000, ge=500, le=60000)
    motion_threshold: Optional[float] = Field(default=0.15, ge=0.0, le=1.0)
    detector_ids: list[str] = Field(default_factory=list)
    yoloworld_prompts: Optional[str] = Field(None, max_length=1024)  # Comma-separated prompts for YOLOWorld


class DemoSessionOut(BaseModel):
    """Schema for demo session output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    config_id: Optional[str]
    name: str
    youtube_url: str
    youtube_video_id: Optional[str]
    capture_mode: str
    polling_interval_ms: Optional[int]
    motion_threshold: Optional[float]
    detector_ids: list[str]
    status: str
    started_at: datetime
    stopped_at: Optional[datetime]
    total_frames_captured: int
    total_detections: int
    error_message: Optional[str] = None
    last_frame_at: Optional[datetime] = None
    created_by: Optional[str]
    yoloworld_prompts: Optional[str] = None  # Comma-separated prompts for YOLOWorld


class FrameSubmit(BaseModel):
    """Schema for submitting a frame for detection."""
    detector_id: str
    image_data: str  # Base64 encoded image
    capture_method: str = Field(..., pattern="^(polling|motion|manual|webcam)$")


class YoloWorldFrameSubmit(BaseModel):
    """Schema for submitting a frame for YOLOWorld detection."""
    image_data: str  # Base64 encoded image
    prompts: str  # Comma-separated list of things to detect
    capture_method: str = Field(default="yoloworld")


class YoloeFrameSubmit(BaseModel):
    """Schema for submitting a frame for YOLOE open-vocab detection."""
    image_data: str  # Base64 encoded image
    prompts: str  # Comma-separated list of things to detect
    confidence_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    capture_method: str = Field(default="yoloe")


class DemoDetectionResultOut(BaseModel):
    """Schema for demo detection result output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    query_id: Optional[str]
    detector_id: Optional[str]  # Optional for YOLOWorld mode
    result_label: Optional[str]
    confidence: Optional[float]
    status: str
    frame_number: Optional[int]
    capture_method: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


# ==================== Image Annotation Schemas ====================

class ImageAnnotationBase(BaseModel):
    """Base schema for image annotation with normalized bounding box coordinates."""
    # Normalized bounding box (0.0 to 1.0 for resolution-independence)
    x: float = Field(..., ge=0.0, le=1.0, description="Left edge (normalized 0-1)")
    y: float = Field(..., ge=0.0, le=1.0, description="Top edge (normalized 0-1)")
    width: float = Field(..., ge=0.0, le=1.0, description="Box width (normalized 0-1)")
    height: float = Field(..., ge=0.0, le=1.0, description="Box height (normalized 0-1)")

    # Classification
    label: str = Field(..., max_length=128)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score (null for human annotations)")


class ImageAnnotationCreate(ImageAnnotationBase):
    """Schema for creating a new annotation."""
    query_id: str
    image_blob_path: str
    source: str = Field(default="human", pattern="^(model|human)$")
    model_name: Optional[str] = Field(None, max_length=128)


class ImageAnnotationUpdate(BaseModel):
    """Schema for updating an annotation."""
    x: Optional[float] = Field(None, ge=0.0, le=1.0)
    y: Optional[float] = Field(None, ge=0.0, le=1.0)
    width: Optional[float] = Field(None, ge=0.0, le=1.0)
    height: Optional[float] = Field(None, ge=0.0, le=1.0)
    label: Optional[str] = Field(None, max_length=128)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    review_status: Optional[str] = Field(None, pattern="^(pending|approved|rejected|corrected)$")


class ImageAnnotationOut(ImageAnnotationBase):
    """Schema for annotation output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    query_id: str
    image_blob_path: str
    source: str  # "model" or "human"
    model_name: Optional[str]
    review_status: str  # pending, approved, rejected, corrected
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ImageAnnotationBulkCreate(BaseModel):
    """Schema for bulk creating annotations (e.g., from model predictions)."""
    query_id: str
    image_blob_path: str
    source: str = Field(default="model", pattern="^(model|human)$")
    model_name: Optional[str] = None
    annotations: List[ImageAnnotationBase] = Field(..., min_length=1)


class ImageAnnotationReview(BaseModel):
    """Schema for reviewing an annotation."""
    review_status: str = Field(..., pattern="^(approved|rejected|corrected)$")
    # Optional correction fields (when status is "corrected")
    corrected_x: Optional[float] = Field(None, ge=0.0, le=1.0)
    corrected_y: Optional[float] = Field(None, ge=0.0, le=1.0)
    corrected_width: Optional[float] = Field(None, ge=0.0, le=1.0)
    corrected_height: Optional[float] = Field(None, ge=0.0, le=1.0)
    corrected_label: Optional[str] = Field(None, max_length=128)


# ==================== Data Retention & Management Schemas ====================

class DataRetentionSettingsOut(BaseModel):
    """Schema for data retention settings output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    retention_days: int
    exclude_verified: bool
    auto_cleanup_enabled: bool
    default_sample_percentage: float
    stratify_by_label: bool
    last_cleanup_at: Optional[datetime]
    last_cleanup_count: Optional[int]
    created_at: datetime
    updated_at: datetime


class DataRetentionSettingsUpdate(BaseModel):
    """Schema for updating data retention settings."""
    retention_days: Optional[int] = Field(None, ge=1, le=365)
    exclude_verified: Optional[bool] = None
    auto_cleanup_enabled: Optional[bool] = None
    default_sample_percentage: Optional[float] = Field(None, ge=1.0, le=100.0)
    stratify_by_label: Optional[bool] = None


class StorageStatsOut(BaseModel):
    """Schema for storage statistics."""
    total_queries: int
    total_with_images: int
    verified_queries: int
    unverified_queries: int
    estimated_size_mb: float
    queries_by_age: Dict[str, int]  # e.g., {"< 7 days": 100, "7-30 days": 500, "> 30 days": 1000}
    queries_by_label: Dict[str, int]  # e.g., {"person": 500, "car": 100}
    oldest_query_date: Optional[datetime]
    newest_query_date: Optional[datetime]


class PurgeRequest(BaseModel):
    """Schema for manual purge request."""
    older_than_days: int = Field(..., ge=0, le=365)  # 0 = same day and beyond
    exclude_verified: bool = True
    label_filter: Optional[str] = None  # Only purge specific label
    dry_run: bool = False  # If true, just return count without deleting


class PurgeResponse(BaseModel):
    """Schema for purge operation response."""
    deleted_count: int
    deleted_blob_count: int
    dry_run: bool
    message: str


class TrainingExportRequest(BaseModel):
    """Schema for training data export request."""
    sample_percentage: float = Field(10.0, ge=1.0, le=100.0)
    stratify_by_label: bool = True
    verified_only: bool = False  # Only export queries with ground_truth
    label_filter: Optional[List[str]] = None  # Only include specific labels
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    include_bboxes: bool = True  # Include bounding box annotations
    export_format: str = Field("zip", pattern="^(zip|yolo|coco)$")


class TrainingExportResponse(BaseModel):
    """Schema for training export response."""
    total_samples: int
    samples_by_label: Dict[str, int]
    download_url: Optional[str] = None
    export_id: str
    message: str


# ==================== Open-Vocab Detection Schemas ====================

class OpenVocabQueryCreate(BaseModel):
    """Schema for submitting an open-vocabulary detection query."""
    prompts: str = Field(..., description="Comma-separated object prompts")
    confidence_threshold: float = Field(0.25, ge=0.0, le=1.0)
    image_data: Optional[str] = None  # Base64 encoded image
    segment: bool = False  # Request SAM pixel-precise mask polygons


class OpenVocabDetectionOut(BaseModel):
    """Schema for a single open-vocab detection."""
    label: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]
    mask_polygon: Optional[List[List[float]]] = None  # [[x,y],...] normalized 0-1


class OpenVocabResultOut(BaseModel):
    """Schema for open-vocab detection results."""
    detections: List[OpenVocabDetectionOut]
    prompts_used: List[str]
    latency_ms: int = 0
    sam_enriched: bool = False


class VLMQueryCreate(BaseModel):
    """Schema for VLM natural language query."""
    question: str = Field(..., max_length=500)
    image_data: Optional[str] = None  # Base64 encoded image


class VLMQueryResultOut(BaseModel):
    """Schema for VLM query result."""
    answer: str
    confidence: float
    bboxes: Optional[List[OpenVocabDetectionOut]] = None
    latency_ms: int = 0


# ==================== Vehicle Identification Schemas ====================

class VehicleRecordOut(BaseModel):
    """Schema for vehicle identification result."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    detector_id: Optional[str] = None
    plate_text: Optional[str] = None
    vehicle_color: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_make_model: Optional[str] = None
    confidence: float
    bbox: Optional[List[float]] = None
    plate_bbox: Optional[List[float]] = None
    image_url: Optional[str] = None
    camera_id: Optional[str] = None
    captured_at: datetime


class VehicleSearchParams(BaseModel):
    """Schema for vehicle search parameters."""
    plate_text: Optional[str] = None  # Partial match
    vehicle_color: Optional[str] = None
    vehicle_type: Optional[str] = None
    camera_id: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class VehicleIdentifyRequest(BaseModel):
    """Schema for vehicle identification request."""
    image_data: str  # Base64 encoded image
    camera_id: Optional[str] = None
    detector_id: Optional[str] = None


# ==================== Forensic Search (BOLO) Schemas ====================

class ForensicSearchJobCreate(BaseModel):
    """Schema for creating a forensic search job."""
    query_text: str = Field(..., max_length=500)
    source_type: str = Field("video_file", pattern="^(dvr|rtsp_recording|video_file)$")
    source_url: str = Field(..., max_length=512)
    camera_ids: Optional[List[str]] = None
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None


class ForensicSearchJobOut(BaseModel):
    """Schema for forensic search job output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    query_text: str
    source_type: str
    source_url: str
    camera_ids: Optional[List[str]] = None
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None
    status: str
    progress_pct: float
    total_frames: int
    frames_scanned: int
    matches_found: int
    created_by: Optional[str] = None
    created_at: datetime


class ForensicSearchResultOut(BaseModel):
    """Schema for a single forensic search match."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    timestamp_sec: Optional[float] = None
    camera_id: Optional[str] = None
    confidence: float
    bbox: Optional[List[float]] = None
    label: Optional[str] = None
    description: Optional[str] = None
    frame_url: Optional[str] = None
    created_at: datetime


# ==================== Maven Parking Schemas ====================

class ParkingZoneCreate(BaseModel):
    """Schema for creating a parking zone."""
    name: str = Field(..., max_length=128)
    camera_id: Optional[str] = None
    max_capacity: int = Field(0, ge=0)
    zone_type: str = Field("general", pattern="^(permit|metered|handicap|fire|general)$")


class ParkingZoneOut(BaseModel):
    """Schema for parking zone output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    camera_id: Optional[str] = None
    max_capacity: int
    current_occupancy: int
    zone_type: str
    created_at: datetime
    updated_at: datetime


class ParkingEventOut(BaseModel):
    """Schema for parking event output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    zone_id: str
    vehicle_record_id: Optional[str] = None
    event_type: str  # ENTRY, EXIT, VIOLATION
    timestamp: datetime


class ParkingViolationOut(BaseModel):
    """Schema for parking violation output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    violation_type: str
    evidence_url: Optional[str] = None
    resolved: bool
    resolved_at: Optional[datetime] = None
    created_at: datetime


class ParkingDashboardOut(BaseModel):
    """Schema for parking dashboard summary."""
    total_zones: int
    total_capacity: int
    total_occupied: int
    occupancy_pct: float
    zones: List[ParkingZoneOut]
    recent_events: List[ParkingEventOut]
    active_violations: int
