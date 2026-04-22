"""Application configuration and environment settings.

Simplified configuration for local testing with minimal dependencies.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings."""

    # Database
    postgres_dsn: str = Field(..., alias="POSTGRES_DSN")

    # Supabase
    supabase_url: str = Field("https://uwhbbnouxmpounqeudiw.supabase.co", alias="SUPABASE_URL")
    supabase_anon_key: Optional[str] = Field(None, alias="SUPABASE_ANON_KEY")
    supabase_service_key: str = Field("", alias="SUPABASE_SERVICE_KEY")
    supabase_storage_bucket: str = Field("images", alias="SUPABASE_STORAGE_BUCKET")

    # Legacy Azure fields (kept for backward compat, no longer used)
    azure_tenant_id: Optional[str] = Field(None, alias="AZURE_TENANT_ID")
    azure_client_id: Optional[str] = Field(None, alias="AZURE_CLIENT_ID")
    azure_issuer: Optional[str] = Field(None, alias="AZURE_ISSUER")
    azure_storage_account: Optional[str] = Field(None, alias="AZURE_STORAGE_ACCOUNT")
    azure_storage_key: Optional[str] = Field(None, alias="AZURE_STORAGE_KEY")
    azure_storage_container: str = Field("images", alias="AZURE_STORAGE_CONTAINER")
    azure_storage_connection_string: Optional[str] = Field(None, alias="AZURE_STORAGE_CONNECTION_STRING")
    azure_service_bus_connection: Optional[str] = Field(None, alias="AZURE_SERVICE_BUS_CONNECTION")
    azure_service_bus_queue: str = Field("fallback-jobs", alias="AZURE_SERVICE_BUS_QUEUE")
    service_bus_conn: Optional[str] = Field(None, alias="SERVICE_BUS_CONN")

    # Alerts (optional for local testing)
    sendgrid_api_key: Optional[str] = Field(None, alias="SENDGRID_API_KEY")
    sendgrid_from_email: Optional[str] = Field(None, alias="SENDGRID_FROM_EMAIL")
    twilio_account_sid: Optional[str] = Field(None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(None, alias="TWILIO_AUTH_TOKEN")
    twilio_phone_from: Optional[str] = Field(None, alias="TWILIO_PHONE_FROM")
    alert_email_from: Optional[str] = Field(None, alias="ALERT_EMAIL_FROM")
    alert_phone_from: Optional[str] = Field(None, alias="ALERT_PHONE_FROM")
    alert_email_to: Optional[str] = Field(None, alias="ALERT_EMAIL_TO")
    alert_phone_to: Optional[str] = Field(None, alias="ALERT_PHONE_TO")
    alert_function_url: Optional[str] = Field(None, alias="ALERT_FUNCTION_URL")

    # General
    environment: str = Field("development", alias="ENVIRONMENT")
    jwt_secret: Optional[str] = Field(None, alias="JWT_SECRET")
    api_secret_key: str = Field(..., alias="API_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(120, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    fallback_token_expiry_minutes: int = Field(60 * 24, alias="FALLBACK_TOKEN_EXPIRY_MINUTES")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    worker_url: str = Field("http://worker:8081/infer", alias="WORKER_URL")
    edge_inference_url: str = Field("http://edge-inference:8001/infer", alias="EDGE_INFERENCE_URL")
    yoloworld_worker_url: str = Field("http://edge-inference:8001/yoloworld", alias="YOLOWORLD_WORKER_URL")
    yoloe_worker_url: str = Field("http://edge-inference:8001/yoloe", alias="YOLOE_WORKER_URL")
    cors_allowed_origins: str = Field("http://localhost:3000,http://localhost:30101", alias="CORS_ALLOWED_ORIGINS")
    trainer_url: str = Field("http://cloud-trainer:8082/train", alias="TRAINER_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        case_sensitive=False,
        extra="ignore"
    )

    # Compatibility properties for legacy code
    @property
    def database(self):
        """Legacy database settings compatibility."""
        class DB:
            def __init__(self, dsn):
                self.dsn = dsn
        return DB(self.postgres_dsn)

    @property
    def azure_ad(self):
        """Legacy Azure AD settings compatibility."""
        class AzureAD:
            def __init__(self, tenant_id, client_id, issuer):
                self.tenant_id = tenant_id
                self.client_id = client_id
                self.issuer = issuer

            @property
            def authority(self):
                return f"https://login.microsoftonline.com/{self.tenant_id}"
        return AzureAD(self.azure_tenant_id, self.azure_client_id, self.azure_issuer)

    @property
    def blob(self):
        """Legacy blob storage settings compatibility."""
        class Blob:
            def __init__(self, account_name, account_key, container_name):
                self.account_name = account_name
                self.account_key = account_key
                self.container_name = container_name
        return Blob(self.azure_storage_account, self.azure_storage_key, self.azure_storage_container)

    @property
    def service_bus(self):
        """Legacy service bus settings compatibility."""
        class ServiceBus:
            def __init__(self, connection_string, queue_name):
                self.connection_string = connection_string
                self.queue_name = queue_name
        # Prefer SERVICE_BUS_CONN over AZURE_SERVICE_BUS_CONNECTION
        conn = self.service_bus_conn or self.azure_service_bus_connection
        return ServiceBus(conn, self.azure_service_bus_queue)

    @property
    def alert(self):
        """Legacy alert settings compatibility."""
        class Alert:
            def __init__(self, sendgrid_api_key, sendgrid_from_email,
                        twilio_account_sid, twilio_auth_token, twilio_phone_from,
                        alert_email_from, alert_phone_from, alert_email_to, alert_phone_to,
                        alert_function_url):
                self.sendgrid_api_key = sendgrid_api_key
                self.from_email = alert_email_from or sendgrid_from_email or "alerts@4wardmotions.com"
                self.alert_email_from = self.from_email
                self.twilio_account_sid = twilio_account_sid
                self.twilio_auth_token = twilio_auth_token
                self.alert_phone_from = alert_phone_from or twilio_phone_from
                self.alert_email_to = alert_email_to
                self.alert_phone_to = alert_phone_to
                self.alert_function_url = alert_function_url
        return Alert(self.sendgrid_api_key, self.sendgrid_from_email,
                    self.twilio_account_sid, self.twilio_auth_token, self.twilio_phone_from,
                    self.alert_email_from, self.alert_phone_from, self.alert_email_to,
                    self.alert_phone_to, self.alert_function_url)


@lru_cache()
def get_settings() -> Settings:
    """Cached settings factory.

    FastAPI dependencies can call this function to obtain a shared
    Settings instance.  Using `lru_cache` ensures the environment is
    parsed only once and the resulting object is reused.
    """
    return Settings()
