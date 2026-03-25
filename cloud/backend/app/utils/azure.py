"""Azure helper functions.

This module centralises integration with Azure services such as Blob
Storage and Service Bus.  By isolating these interactions, the rest
of the application can remain agnostic of the underlying SDKs and
handles errors consistently.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from azure.storage.blob import (BlobServiceClient, ContentSettings,
                                generate_blob_sas, BlobSasPermissions)
from azure.servicebus import ServiceBusClient, ServiceBusMessage
import json

from ..config import get_settings


settings = get_settings()

# Instantiate clients once at module import time.  These will reuse
# underlying HTTP connections and share credentials.
# Use connection string if available (for SAS token auth), otherwise use account key
if settings.azure_storage_connection_string:
    blob_service_client = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
else:
    blob_service_client = BlobServiceClient(
        account_url=f"https://{settings.blob.account_name}.blob.core.windows.net/",
        credential=settings.blob.account_key,
    )
service_bus_client = ServiceBusClient.from_connection_string(settings.service_bus.connection_string)


def upload_blob(container: str, blob_name: str, data: bytes, content_type: str) -> str:
    """Upload bytes to Azure Blob Storage and return the blob path.

    The function creates the container if it doesn't already exist.  It
    sets the content type for the uploaded blob.  On success, it
    returns the full path (container/blob_name) which can be stored in
    the database.  Exceptions are allowed to bubble up to the caller.
    """
    container_client = blob_service_client.get_container_client(container)
    if not container_client.exists():
        container_client.create_container()
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(data, overwrite=True, content_settings=ContentSettings(content_type=content_type))
    return f"{container}/{blob_name}"


def generate_signed_url(container: str, blob_name: str, expiry_minutes: int = 60) -> str:
    """Generate a shared access signature URL for a blob.

    The returned URL is valid for `expiry_minutes` minutes and grants
    read-only access.  It can be used by the frontend to display
    images without exposing the storage account key.
    """
    # If using connection string with SAS, extract account name and generate URL
    if settings.azure_storage_connection_string and not settings.blob.account_key:
        # Extract account name from connection string
        import re
        match = re.search(r'https://([^.]+)\.blob\.core\.windows\.net', settings.azure_storage_connection_string)
        account_name = match.group(1) if match else settings.blob.account_name

        # Use the existing SAS token from connection string (it's already valid until 2027)
        blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)
        return blob_client.url
    else:
        # Generate new SAS token with account key
        sas_token = generate_blob_sas(
            account_name=settings.blob.account_name,
            container_name=container,
            blob_name=blob_name,
            account_key=settings.blob.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(minutes=expiry_minutes),
        )
        return f"https://{settings.blob.account_name}.blob.core.windows.net/{container}/{blob_name}?{sas_token}"


def send_service_bus_message(queue_name: str, payload: dict) -> None:
    """Send a JSON serializable payload to a Service Bus queue."""
    sender = service_bus_client.get_queue_sender(queue_name)
    with sender:
        message = ServiceBusMessage(json.dumps(payload))  # type: ignore[name-defined]
        sender.send_messages(message)


def delete_blob(container: str, blob_name: str) -> bool:
    """Delete a blob from Azure Blob Storage.

    Returns True if deleted successfully, False if blob didn't exist.
    Raises exception for other errors.
    """
    try:
        blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)
        blob_client.delete_blob()
        return True
    except Exception as e:
        if "BlobNotFound" in str(e):
            return False
        raise


def download_blob(container: str, blob_name: str) -> bytes:
    """Download a blob from Azure Blob Storage and return its content as bytes."""
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)
    download_stream = blob_client.download_blob()
    return download_stream.readall()
