#!/usr/bin/env python3
"""
IntelliOptics: inference worker (AKS/Service Bus)

- Robust Service Bus message parsing (handles generator bodies, JSON, dicts, app props)
- Image fetch via HTTP(S) with Azure Blob fallback
  * If URL has SAS -> use from_blob_url(SAS)
  * If no SAS but AZURE_STORAGE_CONNECTION_STRING is provided -> use from_connection_string(container, blob)
- Optional one-time model prefetch
- Health endpoint on :8081/health
- Optional DB init (won't crash pod if DB is unavailable)
"""

from __future__ import annotations

import io
import json
import logging
import os
import signal
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
try:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage
    from azure.storage.blob import BlobClient
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False
from PIL import Image

# -----------------------------
# Logging
# -----------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("inference-worker")

# -----------------------------
# Env / Config
# -----------------------------
SB_CONN = os.getenv("SB_CONN") or os.getenv("SERVICE_BUS_CONN")
QUEUE_IN = os.getenv("QUEUE_IN", "image-queries")
QUEUE_OUT = os.getenv("QUEUE_OUT", "inference-results")

MODEL_URI = os.getenv("MODEL_URI") or os.getenv("MODEL_URL") or os.getenv("MODEL_URL_FALLBACK")
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/app/models")
MODEL_NAME = os.getenv("MODEL_NAME", "intellioptics-yolov10n.onnx")

# IO defaults (placeholder)
IO_MODE = os.getenv("IO_MODE", "onnx")
IO_IMG_SIZE = int(os.getenv("IO_IMG_SIZE", "640"))
IO_CONF_THRESH = float(os.getenv("IO_CONF_THRESH", "0.5"))
IO_NMS_IOU = float(os.getenv("IO_NMS_IOU", "0.45"))

# Blob
AZ_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")  # full connection string
AZ_ACCOUNT = os.getenv("AZ_BLOB_ACCOUNT")  # optional (just for log hint)

# API token (validated because upstream expects it)
IO_TOKEN = os.getenv("INTELLIOPTICS_API_TOKEN")

# DB init (best-effort)
DB_EAGER_INIT = os.getenv("DB_EAGER_INIT", "false").lower() == "true"

# Health
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8081"))

# -----------------------------
# Shutdown handling
# -----------------------------
_shutdown = threading.Event()


def _handle_sigterm(*_args):
    _shutdown.set()


signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)

# -----------------------------
# Health server
# -----------------------------
def start_health_server(port: int = HEALTH_PORT):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self):  # noqa: N802
            if self.path.rstrip("/") == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(404)
                self.end_headers()

    def _serve():
        httpd = HTTPServer(("0.0.0.0", port), HealthHandler)
        log.info("Health server listening on http://0.0.0.0:%d/health", port)
        while not _shutdown.is_set():
            httpd.handle_request()

    t = threading.Thread(target=_serve, name="healthz", daemon=True)
    t.start()

# -----------------------------
# Blob helpers
# -----------------------------
def _redact_sas(url: str) -> str:
    try:
        if "sig=" in url:
            before, _sig = url.split("sig=", 1)
            return before + "sig=REDACTED"
    except Exception:
        pass
    return url


def _split_container_blob_from_url(blob_url: str) -> Tuple[str, str]:
    """
    Given: https://<acct>.blob.core.windows.net/<container>/<path/to/blob>
    Returns: (container, blob_path)
    """
    u = urlparse(blob_url)
    # path like "/container/blob/segments..."
    parts = [p for p in u.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot parse container/blob from URL: {blob_url}")
    container = parts[0]
    blob_path = "/".join(parts[1:])
    return container, blob_path

# -----------------------------
# Model prefetch (optional)
# -----------------------------
def download_model_if_needed() -> Optional[str]:
    if not MODEL_URI:
        log.info("No MODEL_URI provided; skipping model prefetch.")
        return None

    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
    dest = os.path.join(MODEL_CACHE_DIR, MODEL_NAME)

    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        log.info("Model already present: %s", dest)
        return dest

    # Try straight HTTP first
    try:
        log.info("Fetching model via HTTP: %s", _redact_sas(MODEL_URI))
        r = requests.get(MODEL_URI, stream=True, timeout=60)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
        log.info("Model downloaded: %s (%d bytes)", dest, os.path.getsize(dest))
        return dest
    except Exception as http_err:
        log.warning("HTTP model fetch failed: %s", http_err)

    # Blob SDK fallback:
    try:
        if "?" in MODEL_URI:
            # URL has SAS -> use it as-is
            bc = BlobClient.from_blob_url(MODEL_URI)
        elif AZ_CONN_STR:
            container, blob = _split_container_blob_from_url(MODEL_URI)
            bc = BlobClient.from_connection_string(AZ_CONN_STR, container_name=container, blob_name=blob)
        else:
            raise RuntimeError("No credentials available for BlobClient fallback")

        with open(dest, "wb") as f:
            data = bc.download_blob().readall()
            f.write(data)
        log.info("Model downloaded via BlobClient: %s (%d bytes)", dest, os.path.getsize(dest))
        return dest
    except Exception as blob_err:
        log.error("Model prefetch failed: %s", blob_err)
        return None

# -----------------------------
# SB parsing + image fetch
# -----------------------------
def parse_sb_message(message) -> Dict[str, Any]:
    """
    Accepts:
      - JSON dict in message body (bytes/str)
      - Plain dict bodies
      - application_properties fallback
    """
    # Pull body (can be generator/bytes/str depending on SDK)
    body = getattr(message, "body", None)

    raw_bytes: Optional[bytes] = None
    if body is None:
        pass
    elif isinstance(body, (bytes, bytearray)):
        raw_bytes = bytes(body)
    elif isinstance(body, str):
        raw_bytes = body.encode("utf-8", errors="ignore")
    else:
        # generator case
        try:
            raw_bytes = b"".join(
                part if isinstance(part, (bytes, bytearray)) else bytes(part) for part in body
            )
        except Exception:
            raw_bytes = None

    # Try JSON decode
    if raw_bytes:
        try:
            text = raw_bytes.decode("utf-8", errors="ignore").strip()
            if text.startswith("{") and text.endswith("}"):
                return json.loads(text)
        except Exception:
            pass

    # AMQPValue dict bodies
    if isinstance(body, dict):
        return dict(body)

    # application_properties fallback
    props: Dict[str, Any] = {}
    try:
        ap = getattr(message, "application_properties", None) or {}
        for k, v in ap.items():
            ks = k.decode() if isinstance(k, (bytes, bytearray)) else str(k)
            if isinstance(v, (bytes, bytearray)):
                try:
                    props[ks] = v.decode("utf-8", errors="ignore")
                except Exception:
                    props[ks] = repr(v)
            else:
                props[ks] = v
    except Exception:
        pass

    if props:
        return props

    raise ValueError(f"Unsupported message body type: {type(body)}")


def fetch_image_bytes(blob_url: str) -> bytes:
    """
    Try HTTP first; if 401/403/404 (private blob) and we have creds, use Blob SDK.

    FIX: when there is NO SAS on the URL, we now use
         BlobClient.from_connection_string(conn_str, container, blob),
         which signs correctly with the shared key and avoids the MAC mismatch.
    """
    # Direct HTTP
    try:
        r = requests.get(blob_url, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as http_err:
        log.warning("HTTP fetch failed (%s): %s", _redact_sas(blob_url), http_err)

    # Blob fallback
    try:
        if "?" in blob_url:
            # SAS present
            bc = BlobClient.from_blob_url(blob_url)
        elif AZ_CONN_STR:
            container, blob = _split_container_blob_from_url(blob_url)
            bc = BlobClient.from_connection_string(AZ_CONN_STR, container_name=container, blob_name=blob)
        else:
            raise RuntimeError("No credentials for BlobClient fallback")

        return bc.download_blob().readall()
    except Exception as blob_err:
        raise RuntimeError(f"Blob download failed: {blob_err}") from blob_err

# -----------------------------
# Placeholder inference
# -----------------------------
def dummy_infer(img_bytes: bytes) -> Dict[str, Any]:
    with Image.open(io.BytesIO(img_bytes)) as im:
        w, h = im.size
        mode = im.mode

    return {
        "ok": True,
        "detections": [],
        "image": {"width": w, "height": h, "mode": mode},
        "model": {"name": MODEL_NAME, "mode": IO_MODE, "conf": IO_CONF_THRESH, "iou": IO_NMS_IOU},
    }

def send_result(sb: ServiceBusClient, queue: str, payload: Dict[str, Any]) -> None:
    msg = ServiceBusMessage(json.dumps(payload))
    with sb.get_queue_sender(queue_name=queue) as sender:
        sender.send_messages(msg)

def init_db_best_effort() -> None:
    if not DB_EAGER_INIT:
        return
    try:
        from db import SessionLocal, engine  # noqa: F401
        from sqlalchemy import text
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        log.info("DB eager init: success.")
    except Exception as e:
        log.warning("DB eager init failed (continuing without DB): %s", e)

# -----------------------------
# Main
# -----------------------------
def main():
    # Required configs
    if not IO_TOKEN:
        log.error("INTELLIOPTICS_API_TOKEN is required")
        sys.exit(1)
    if not SB_CONN or SB_CONN == "DISABLED" or not HAS_AZURE:
        log.warning("Service Bus not configured — worker running in idle/health-only mode.")
        start_health_server(HEALTH_PORT)
        while not _shutdown.is_set():
            _shutdown.wait(timeout=30)
        log.info("Shutting down (idle mode).")
        return

    # Prefetch model (optional)
    model_path = download_model_if_needed()
    if model_path:
        log.info("Model ready at %s", model_path)

    # Health server
    start_health_server(HEALTH_PORT)

    # Optional DB init
    init_db_best_effort()

    # Startup banner
    acct_hint = AZ_ACCOUNT
    if not acct_hint and AZ_CONN_STR and "AccountName=" in AZ_CONN_STR:
        try:
            acct_hint = AZ_CONN_STR.split("AccountName=")[1].split(";", 1)[0]
        except Exception:
            acct_hint = "unknown"

    log.info("Service Bus: using connection string")
    log.info(
        "Startup: QUEUE_IN=%s, QUEUE_OUT=%s, PREFETCH=%s, HealthPort=%d, StorageAcct=%s",
        QUEUE_IN, QUEUE_OUT, os.getenv("PREFETCH", "16"), HEALTH_PORT, acct_hint or "unknown"
    )

    # SB loop
    with ServiceBusClient.from_connection_string(SB_CONN, logging_enable=False) as sb:
        with sb.get_queue_receiver(queue_name=QUEUE_IN, max_wait_time=5) as rx:
            log.info("Listening on '%s'...", QUEUE_IN)
            while not _shutdown.is_set():
                try:
                    for msg in rx.receive_messages(max_wait_time=5):
                        try:
                            doc = parse_sb_message(msg)
                            image_query_id = doc.get("image_query_id")
                            blob_url = doc.get("blob_url")
                            if not image_query_id or not blob_url:
                                raise ValueError("Missing required fields: image_query_id and/or blob_url")

                            img_bytes = fetch_image_bytes(blob_url)
                            result = dummy_infer(img_bytes)

                            send_result(sb, QUEUE_OUT, {
                                "image_query_id": image_query_id,
                                "ok": True,
                                "result": result,
                            })
                            rx.complete_message(msg)
                        except Exception as proc_err:
                            log.error("processing_failed: %s", proc_err)
                            try:
                                rx.dead_letter_message(msg)
                            except Exception as dlq_err:
                                log.warning("dead_letter_message failed, abandoning instead: %s", dlq_err)
                                rx.abandon_message(msg)
                except Exception as loop_err:
                    log.warning("Receiver loop warning: %s", loop_err)
                    time.sleep(1)

    log.info("Shutting down.")

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log.exception("Fatal error: %s", e)
        sys.exit(1)
