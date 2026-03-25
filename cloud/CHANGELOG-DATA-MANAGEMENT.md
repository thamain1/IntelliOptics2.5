# Data Management Feature Documentation

## Overview

This document details the data management and query review features added to IntelliOptics 2.0, including:
- Admin Data Management capabilities
- Query skip and delete functionality
- Storage statistics and retention settings
- Training data export

---

## Backend Changes

### 1. New Model: DataRetentionSettings

**File:** `backend/app/models.py`

Added a new model to store data retention configuration:

```python
class DataRetentionSettings(Base):
    __tablename__ = "data_retention_settings"

    id: str                     # UUID primary key
    retention_days: int         # Default: 30 days
    exclude_verified: bool      # Default: True (don't auto-delete verified queries)
    auto_cleanup_enabled: bool  # Default: False
    default_sample_percentage: float  # Default: 10.0%
    stratify_by_label: bool     # Default: True
    created_at: datetime
    updated_at: datetime
    last_cleanup_at: datetime   # When last manual cleanup ran
    last_cleanup_count: int     # How many records were deleted
```

### 2. New Schemas

**File:** `backend/app/schemas.py`

Added the following Pydantic schemas:

- `DataRetentionSettingsOut` - Response model for retention settings
- `DataRetentionSettingsUpdate` - Request model for updating settings
- `StorageStatsOut` - Response model for storage statistics
- `PurgeRequest` - Request model for purge operation
- `PurgeResponse` - Response model for purge results
- `TrainingExportRequest` - Request model for training export
- `TrainingExportResponse` - Response model for export results

### 3. New Router: Data Management

**File:** `backend/app/routers/data_management.py`

New API endpoints under `/admin/data`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/retention-settings` | Get current retention settings |
| PUT | `/retention-settings` | Update retention settings |
| GET | `/storage-stats` | Get storage statistics |
| POST | `/purge` | Purge old queries (supports dry-run) |
| POST | `/export-training` | Create training export |
| GET | `/export-training/{id}/download` | Download training ZIP |

#### Storage Statistics Endpoint

Returns:
- Total queries count
- Queries with images
- Verified vs unverified counts
- Estimated storage size (MB)
- Queries grouped by age (< 7 days, 7-30 days, > 30 days)
- Queries grouped by label (top 20)
- Oldest and newest query dates

#### Purge Endpoint

Parameters:
- `older_than_days` (required): Delete queries older than N days
- `exclude_verified` (optional): Don't delete verified queries (default: true)
- `label_filter` (optional): Only delete queries with this label
- `dry_run` (optional): Preview what would be deleted without deleting

Actions:
- Deletes blob images from Azure Storage
- Deletes related escalations, feedback, and annotations
- Deletes query records
- Updates last_cleanup_at and last_cleanup_count

#### Training Export Endpoint

Parameters:
- `sample_percentage`: Percentage of matching queries to export (1-100%)
- `stratify_by_label`: Sample proportionally from each label
- `verified_only`: Only export queries with ground truth
- `label_filter`: List of labels to include
- `min_confidence` / `max_confidence`: Filter by confidence range

Returns a ZIP file containing:
- `images/` directory with images organized by label
- `metadata.json` with query details, detections, and ground truth

### 4. Azure Blob Utilities

**File:** `backend/app/utils/azure.py`

Added two new functions:

```python
def delete_blob(container: str, blob_name: str) -> bool:
    """Delete a blob from Azure Blob Storage.
    Returns True if deleted, False if blob didn't exist."""

def download_blob(container: str, blob_name: str) -> bytes:
    """Download a blob and return its content as bytes."""
```

### 5. Query Delete Endpoint

**File:** `backend/app/routers/queries.py`

Added DELETE endpoint:

```python
@router.delete("/{query_id}", status_code=204)
def delete_query(query_id: str, db, current_user):
    """Delete a query and its associated blob image.
    Also deletes related escalations, feedback, and annotations."""
```

---

## Frontend Changes

### 1. AdminPage Updates

**File:** `frontend/src/pages/AdminPage.tsx`

Complete rewrite with two tabs:

#### User Management Tab
- Create new users
- List existing users
- Delete users
- Assign roles (admin/reviewer/operator)

#### Data Management Tab

**Storage Statistics Section:**
- Total queries count
- Queries with images
- Verified/Unverified counts
- Estimated storage size
- Breakdown by age (< 7 days, 7-30 days, > 30 days)
- Top labels distribution

**Retention Settings Section:**
- Retention days input
- Exclude verified checkbox
- Default sample percentage slider

**Purge Data Section:**
- Days threshold input
- Exclude verified checkbox
- Label filter (optional)
- Dry run preview mode
- Execute purge button
- Results display showing deleted count

**Training Export Section:**
- Sample percentage slider
- Stratify by label checkbox
- Verified only checkbox
- Label filter (comma-separated)
- Confidence range inputs
- Generate export button
- Download link when ready

### 2. QueryHistoryPage Updates

**File:** `frontend/src/pages/QueryHistoryPage.tsx`

Added new action buttons for pending queries:

#### Skip Button
- Marks query with `ground_truth: 'skipped'`
- Removes from pending review list
- Displays with gray styling when viewed in "Show All" mode

#### Delete Button
- Prompts for confirmation
- Permanently deletes query and blob image
- Removes from UI immediately

Button layout:
```
[  Correct  ] [  Wrong   ]  <- Verification buttons
[   Skip    ] [  Delete  ]  <- New buttons
```

---

## Database Schema

### New Table: data_retention_settings

```sql
CREATE TABLE data_retention_settings (
    id VARCHAR(36) PRIMARY KEY,
    retention_days INTEGER DEFAULT 30,
    exclude_verified BOOLEAN DEFAULT TRUE,
    auto_cleanup_enabled BOOLEAN DEFAULT FALSE,
    default_sample_percentage FLOAT DEFAULT 10.0,
    stratify_by_label BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_cleanup_at TIMESTAMP,
    last_cleanup_count INTEGER
);
```

---

## API Reference

### GET /admin/data/storage-stats

Response:
```json
{
  "total_queries": 16848,
  "total_with_images": 16848,
  "verified_queries": 150,
  "unverified_queries": 16698,
  "estimated_size_mb": 1645.3,
  "queries_by_age": {
    "< 7 days": 5000,
    "7-30 days": 8000,
    "> 30 days": 3848
  },
  "queries_by_label": {
    "person": 14000,
    "cat": 500,
    "laptop": 300
  },
  "oldest_query_date": "2026-01-10T...",
  "newest_query_date": "2026-01-19T..."
}
```

### POST /admin/data/purge

Request:
```json
{
  "older_than_days": 30,
  "exclude_verified": true,
  "label_filter": null,
  "dry_run": true
}
```

Response:
```json
{
  "deleted_count": 3848,
  "deleted_blob_count": 3848,
  "dry_run": true,
  "message": "Dry run: Would delete 3848 queries and their images."
}
```

### POST /admin/data/export-training

Request:
```json
{
  "sample_percentage": 10.0,
  "stratify_by_label": true,
  "verified_only": false,
  "label_filter": ["person", "cat"],
  "min_confidence": null,
  "max_confidence": 0.8
}
```

Response:
```json
{
  "total_samples": 500,
  "samples_by_label": {
    "person": 400,
    "cat": 100
  },
  "download_url": "/admin/data/export-training/abc123/download?ids=...",
  "export_id": "abc123",
  "message": "Export ready with 500 samples..."
}
```

### DELETE /queries/{query_id}

Response: `204 No Content`

---

## Usage Guide

### Reviewing Queries

1. Navigate to **Image Queries** page
2. Use filters:
   - **Label filter**: Type to filter by detection label
   - **Max Confidence**: Slide to focus on low-confidence detections
   - **Show All**: Toggle to see verified queries
3. For each query:
   - Click **Correct** if the detection label is accurate
   - Click **Wrong** to enter the correct label
   - Click **Skip** to mark as skipped (uncertain/unclear)
   - Click **Delete** to permanently remove (with confirmation)

### Managing Storage

1. Navigate to **Admin** page
2. Click **Data Management** tab
3. View **Storage Statistics** for current state
4. Configure **Retention Settings** as needed
5. Use **Purge Data** to clean old records:
   - Set days threshold
   - Enable "Exclude Verified" to preserve reviewed data
   - Use "Dry Run" first to preview
   - Click "Purge" to execute

### Exporting Training Data

1. Navigate to **Admin** > **Data Management**
2. Scroll to **Training Export** section
3. Configure:
   - Sample percentage (e.g., 10% of matching queries)
   - Enable stratification to balance labels
   - Filter by labels if needed
   - Set confidence range for edge cases
4. Click **Generate Export**
5. Click **Download** when ready

The ZIP contains:
- Images organized as `images/{label}_{index}.jpg`
- `metadata.json` with all query details

---

## Files Modified

| File | Changes |
|------|---------|
| `backend/app/models.py` | Added DataRetentionSettings model |
| `backend/app/schemas.py` | Added 6 new schema classes |
| `backend/app/routers/data_management.py` | New file - data management endpoints |
| `backend/app/routers/queries.py` | Added DELETE endpoint, import delete_blob |
| `backend/app/utils/azure.py` | Added delete_blob, download_blob functions |
| `backend/app/main.py` | Registered data_management router |
| `frontend/src/pages/AdminPage.tsx` | Complete rewrite with Data Management tab |
| `frontend/src/pages/QueryHistoryPage.tsx` | Added Skip and Delete buttons |

---

## Security Considerations

- All data management endpoints require authentication (`get_current_user`)
- Delete operations prompt for confirmation in the UI
- Dry-run mode available to preview purge operations
- Blob deletion failures are logged but don't block record deletion
- Training exports require authentication to download

---

## Future Enhancements

Potential improvements:
- Scheduled auto-cleanup based on retention settings
- Bulk selection for delete/skip operations
- Export format options (COCO, YOLO, Pascal VOC)
- Storage quota warnings
- Audit logging for data deletion
