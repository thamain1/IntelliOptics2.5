"""Lightweight Supabase Storage + PostgREST client for the trainer service."""
from __future__ import annotations

import os
import httpx

_URL = os.environ.get("SUPABASE_URL", "")
_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

_HEADERS = {
    "apikey": _KEY,
    "Authorization": f"Bearer {_KEY}",
}

# Long timeout — uploads/downloads of model files can be large
_client = httpx.Client(timeout=600.0)


def download_blob(bucket: str, blob_name: str) -> bytes:
    url = f"{_URL}/storage/v1/object/{bucket}/{blob_name}"
    resp = _client.get(url, headers=_HEADERS)
    resp.raise_for_status()
    return resp.content


def upload_blob(bucket: str, blob_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes and return 'bucket/blob_name' path."""
    url = f"{_URL}/storage/v1/object/{bucket}/{blob_name}"
    resp = _client.post(
        url,
        content=data,
        headers={**_HEADERS, "Content-Type": content_type, "x-upsert": "true"},
    )
    resp.raise_for_status()
    return f"{bucket}/{blob_name}"


def db_patch(table: str, filters: dict, data: dict) -> None:
    """PATCH one or more rows in a Supabase table via PostgREST."""
    params = "&".join(f"{k}=eq.{v}" for k, v in filters.items())
    url = f"{_URL}/rest/v1/{table}?{params}"
    resp = _client.patch(
        url,
        json=data,
        headers={**_HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
    )
    resp.raise_for_status()
