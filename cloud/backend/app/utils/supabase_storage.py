"""Supabase Storage helper functions.

Drop-in replacement for the Azure blob/service-bus helpers.  Every
public function here mirrors the old ``azure.py`` signatures so callers
only need to change their import path.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ---------------------------------------------------------------------------
# Supabase configuration pulled from Settings
# ---------------------------------------------------------------------------

_SUPABASE_URL: str = settings.supabase_url           # e.g. https://xxx.supabase.co
_SUPABASE_KEY: str = settings.supabase_service_key    # service_role key (full access)
_DEFAULT_BUCKET: str = settings.supabase_storage_bucket  # "images"

_HEADERS = {
    "apikey": _SUPABASE_KEY,
    "Authorization": f"Bearer {_SUPABASE_KEY}",
}

# Re-usable HTTP client (connection pooling)
_client = httpx.Client(timeout=30.0)


# ---------------------------------------------------------------------------
# Public helpers — same signatures as the old azure.py module
# ---------------------------------------------------------------------------

def upload_blob(container: str, blob_name: str, data: bytes, content_type: str) -> str:
    """Upload bytes to Supabase Storage and return the storage path.

    ``container`` maps to a Supabase bucket name.
    ``blob_name`` is the object path inside the bucket.
    Returns ``container/blob_name`` to match the old convention.
    """
    url = f"{_SUPABASE_URL}/storage/v1/object/{container}/{blob_name}"
    headers = {
        **_HEADERS,
        "Content-Type": content_type,
        "x-upsert": "true",  # overwrite if exists
    }
    resp = _client.post(url, content=data, headers=headers)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Supabase upload failed ({resp.status_code}): {resp.text}"
        )
    logger.info("Uploaded %s/%s (%d bytes)", container, blob_name, len(data))
    return f"{container}/{blob_name}"


def generate_signed_url(
    container: str, blob_name: str, expiry_minutes: int = 60
) -> str:
    """Return a time-limited signed URL for the object.

    For public buckets this just returns the public URL.  For private
    buckets it creates a signed URL via the Supabase API.
    """
    # Public buckets — direct URL (no signing needed)
    if container in ("images",):
        return f"{_SUPABASE_URL}/storage/v1/object/public/{container}/{blob_name}"

    # Private buckets — request a signed URL
    url = f"{_SUPABASE_URL}/storage/v1/object/sign/{container}/{blob_name}"
    resp = _client.post(
        url,
        json={"expiresIn": expiry_minutes * 60},
        headers=_HEADERS,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Supabase signed-url failed ({resp.status_code}): {resp.text}"
        )
    signed_path = resp.json().get("signedURL", "")
    return f"{_SUPABASE_URL}/storage/v1{signed_path}"


def download_blob(container: str, blob_name: str) -> bytes:
    """Download an object from Supabase Storage and return bytes."""
    url = f"{_SUPABASE_URL}/storage/v1/object/{container}/{blob_name}"
    resp = _client.get(url, headers=_HEADERS)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Supabase download failed ({resp.status_code}): {resp.text}"
        )
    return resp.content


def delete_blob(container: str, blob_name: str) -> bool:
    """Delete an object from Supabase Storage.

    Returns True on success, False if the object didn't exist.
    """
    url = f"{_SUPABASE_URL}/storage/v1/object/{container}"
    resp = _client.request(
        "DELETE",
        url,
        json={"prefixes": [blob_name]},
        headers=_HEADERS,
    )
    if resp.status_code == 200:
        return True
    if resp.status_code == 404 or "not found" in resp.text.lower():
        return False
    raise RuntimeError(
        f"Supabase delete failed ({resp.status_code}): {resp.text}"
    )


def send_service_bus_message(queue_name: str, payload: dict) -> None:
    """Stub — Service Bus has been removed.

    For local / demo usage inference is called inline.  If async job
    processing is needed later, this can write to a ``job_queue`` table
    and a polling worker can pick it up.
    """
    logger.warning(
        "send_service_bus_message called (queue=%s) — ignored (no Service Bus configured)",
        queue_name,
    )
