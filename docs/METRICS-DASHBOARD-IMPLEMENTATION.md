# Detector Metrics Dashboard Implementation Guide

**Date**: 2026-01-13
**Purpose**: Add metrics visualization showing balanced system accuracy, accuracy for yes (sensitivity), and accuracy for no (specificity)

---

## Overview

Implement a metrics dashboard that displays detection performance for each detector:
- **Balanced Accuracy** = (Sensitivity + Specificity) / 2
- **Accuracy for Yes (Sensitivity)** = TP / (TP + FN) = True Positive Rate
- **Accuracy for No (Specificity)** = TN / (TN + FP) = True Negative Rate

These metrics require ground truth labels to compare against detector predictions.

---

## Architecture

```
Frontend (React + Recharts)
    ↓ GET /detectors/{id}/metrics
Backend (FastAPI)
    ↓ SQL Query
Database (PostgreSQL - queries table with ground_truth labels)
```

---

## Prerequisites

**Database Schema Requirements**:

The `queries` table must have ground truth labels to calculate accuracy. Two approaches:

### Option A: Add ground_truth column to queries table (Recommended)
```sql
ALTER TABLE queries
ADD COLUMN ground_truth VARCHAR(50),  -- Human-verified label
ADD COLUMN is_correct BOOLEAN;         -- detector_result == ground_truth
```

### Option B: Use escalations table
Escalations already contain human reviews, use those as ground truth source.

---

## Implementation Plan

### Phase 1: Backend - Metrics Calculation Endpoint

**File**: `C:\Dev\IntelliOptics 2.0\cloud\backend\app\routers\detectors.py`

#### Step 1.1: Add Metrics Endpoint

Add this endpoint after the test endpoint (around line 318):

```python
@router.get("/{detector_id}/metrics", response_model=schemas.DetectorMetricsOut)
def get_detector_metrics(
    detector_id: uuid.UUID,
    time_range: str = "7d",  # Options: 1d, 7d, 30d, all
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Calculate detector performance metrics based on ground truth labels.

    Returns:
    - balanced_accuracy: (Sensitivity + Specificity) / 2
    - sensitivity: TP / (TP + FN) - Accuracy for "yes" predictions
    - specificity: TN / (TN + FP) - Accuracy for "no" predictions
    - true_positives, true_negatives, false_positives, false_negatives
    - total_queries: Total queries with ground truth labels
    """
    detector = db.query(models.Detector).get(detector_id)
    if not detector:
        raise HTTPException(status_code=404, detail="Detector not found")

    # Calculate time cutoff
    from datetime import datetime, timedelta
    if time_range == "1d":
        cutoff = datetime.utcnow() - timedelta(days=1)
    elif time_range == "7d":
        cutoff = datetime.utcnow() - timedelta(days=7)
    elif time_range == "30d":
        cutoff = datetime.utcnow() - timedelta(days=30)
    else:
        cutoff = None  # All time

    # Query all queries with ground truth labels
    query = db.query(models.Query).filter(
        models.Query.detector_id == detector_id,
        models.Query.ground_truth.isnot(None)  # Only queries with ground truth
    )

    if cutoff:
        query = query.filter(models.Query.created_at >= cutoff)

    queries = query.all()

    if not queries:
        # No ground truth data available
        return {
            "detector_id": detector_id,
            "balanced_accuracy": None,
            "sensitivity": None,
            "specificity": None,
            "true_positives": 0,
            "true_negatives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "total_queries": 0,
            "message": "No ground truth labels available for this detector"
        }

    # Calculate confusion matrix
    # Assuming binary detection: "yes" (defect/detected) vs "no" (normal/not detected)
    tp = 0  # Predicted YES, Actual YES
    tn = 0  # Predicted NO, Actual NO
    fp = 0  # Predicted YES, Actual NO
    fn = 0  # Predicted NO, Actual YES

    for q in queries:
        predicted = q.result  # Detector prediction (e.g., "yes", "no", "defect", "normal")
        actual = q.ground_truth  # Human-verified label

        # Normalize labels to binary (adjust based on your label scheme)
        predicted_positive = predicted.lower() in ["yes", "defect", "detected", "true"]
        actual_positive = actual.lower() in ["yes", "defect", "detected", "true"]

        if predicted_positive and actual_positive:
            tp += 1
        elif not predicted_positive and not actual_positive:
            tn += 1
        elif predicted_positive and not actual_positive:
            fp += 1
        else:  # not predicted_positive and actual_positive
            fn += 1

    # Calculate metrics
    total = tp + tn + fp + fn

    # Sensitivity (Recall, True Positive Rate, Accuracy for YES)
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    # Specificity (True Negative Rate, Accuracy for NO)
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    # Balanced Accuracy
    balanced_accuracy = (sensitivity + specificity) / 2.0

    return {
        "detector_id": detector_id,
        "balanced_accuracy": balanced_accuracy,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "total_queries": total,
        "time_range": time_range
    }
```

#### Step 1.2: Add Pydantic Schema

**File**: `C:\Dev\IntelliOptics 2.0\cloud\backend\app\schemas.py`

Add this schema:

```python
class DetectorMetricsOut(BaseModel):
    detector_id: uuid.UUID
    balanced_accuracy: Optional[float]
    sensitivity: Optional[float]  # Accuracy for YES
    specificity: Optional[float]  # Accuracy for NO
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    total_queries: int
    time_range: str = "7d"
    message: Optional[str] = None

    class Config:
        from_attributes = True
```

#### Step 1.3: Update Database Model (if using Option A)

**File**: `C:\Dev\IntelliOptics 2.0\cloud\backend\app\models.py`

Add columns to Query model:

```python
class Query(Base):
    __tablename__ = "queries"

    # ... existing columns ...

    # NEW: Ground truth fields
    ground_truth = Column(String(50), nullable=True)  # Human-verified label
    is_correct = Column(Boolean, nullable=True)       # result == ground_truth
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
```

#### Step 1.4: Create Database Migration

```bash
cd C:\Dev\IntelliOptics 2.0\cloud\backend

# If using Alembic
alembic revision -m "Add ground truth fields to queries table"

# Edit the migration file and add:
# def upgrade():
#     op.add_column('queries', sa.Column('ground_truth', sa.String(50), nullable=True))
#     op.add_column('queries', sa.Column('is_correct', sa.Boolean, nullable=True))
#     op.add_column('queries', sa.Column('reviewed_by', sa.UUID, nullable=True))
#     op.add_column('queries', sa.Column('reviewed_at', sa.DateTime, nullable=True))

alembic upgrade head
```

**OR** manually run SQL:

```sql
ALTER TABLE queries
ADD COLUMN ground_truth VARCHAR(50),
ADD COLUMN is_correct BOOLEAN,
ADD COLUMN reviewed_by UUID REFERENCES users(id),
ADD COLUMN reviewed_at TIMESTAMP;
```

---

### Phase 2: Frontend - Metrics Visualization

**File**: `C:\Dev\IntelliOptics 2.0\cloud\frontend\src\pages\DetectorDetails.tsx`

#### Step 2.1: Install Chart Library

```bash
cd C:\Dev\IntelliOptics 2.0\cloud\frontend
npm install recharts
```

#### Step 2.2: Create Metrics Component

**File**: `C:\Dev\IntelliOptics 2.0\cloud\frontend\src\components\DetectorMetrics.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import axios from 'axios';

interface MetricsData {
  detector_id: string;
  balanced_accuracy: number | null;
  sensitivity: number | null;
  specificity: number | null;
  true_positives: number;
  true_negatives: number;
  false_positives: number;
  false_negatives: number;
  total_queries: number;
  time_range: string;
  message?: string;
}

interface Props {
  detectorId: string;
  timeRange?: string;
}

const DetectorMetrics: React.FC<Props> = ({ detectorId, timeRange = '7d' }) => {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMetrics();
  }, [detectorId, timeRange]);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`/api/detectors/${detectorId}/metrics`, {
        params: { time_range: timeRange }
      });
      setMetrics(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load metrics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="text-center p-4">Loading metrics...</div>;
  if (error) return <div className="text-red-600 p-4">Error: {error}</div>;
  if (!metrics || metrics.total_queries === 0) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
        <p className="text-yellow-800">
          {metrics?.message || 'No ground truth data available. Start reviewing queries to see accuracy metrics.'}
        </p>
      </div>
    );
  }

  // Prepare data for bar chart
  const chartData = [
    {
      name: 'Balanced Accuracy',
      value: (metrics.balanced_accuracy || 0) * 100,
      color: '#8884d8'
    },
    {
      name: 'Accuracy for Yes',
      value: (metrics.sensitivity || 0) * 100,
      color: '#82ca9d'
    },
    {
      name: 'Accuracy for No',
      value: (metrics.specificity || 0) * 100,
      color: '#ffc658'
    }
  ];

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4">System Accuracy Metrics</h3>

      {/* Metrics Chart */}
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis domain={[0, 100]} label={{ value: 'Accuracy (%)', angle: -90, position: 'insideLeft' }} />
          <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
          <Bar dataKey="value" label={{ position: 'top', formatter: (val: number) => `${val.toFixed(1)}%` }}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Confusion Matrix Stats */}
      <div className="mt-6 grid grid-cols-2 gap-4">
        <div className="bg-green-50 p-4 rounded">
          <div className="text-2xl font-bold text-green-700">{metrics.true_positives}</div>
          <div className="text-sm text-green-600">True Positives</div>
        </div>
        <div className="bg-green-50 p-4 rounded">
          <div className="text-2xl font-bold text-green-700">{metrics.true_negatives}</div>
          <div className="text-sm text-green-600">True Negatives</div>
        </div>
        <div className="bg-red-50 p-4 rounded">
          <div className="text-2xl font-bold text-red-700">{metrics.false_positives}</div>
          <div className="text-sm text-red-600">False Positives</div>
        </div>
        <div className="bg-red-50 p-4 rounded">
          <div className="text-2xl font-bold text-red-700">{metrics.false_negatives}</div>
          <div className="text-sm text-red-600">False Negatives</div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="mt-4 text-sm text-gray-600">
        <p>Total queries with ground truth: {metrics.total_queries}</p>
        <p>Time range: {timeRange}</p>
      </div>
    </div>
  );
};

export default DetectorMetrics;
```

#### Step 2.3: Add Metrics to Detector Details Page

**File**: `C:\Dev\IntelliOptics 2.0\cloud\frontend\src\pages\DetectorDetails.tsx`

Add the metrics component to the detector details page:

```typescript
import DetectorMetrics from '../components/DetectorMetrics';

// Inside the DetectorDetails component, add:
<div className="mt-8">
  <DetectorMetrics detectorId={detectorId} timeRange="7d" />
</div>
```

Or add a dropdown to select time range:

```typescript
const [timeRange, setTimeRange] = useState('7d');

<div className="mb-4">
  <label className="mr-2">Time Range:</label>
  <select
    value={timeRange}
    onChange={(e) => setTimeRange(e.target.value)}
    className="border rounded px-3 py-1"
  >
    <option value="1d">Last 24 hours</option>
    <option value="7d">Last 7 days</option>
    <option value="30d">Last 30 days</option>
    <option value="all">All time</option>
  </select>
</div>

<DetectorMetrics detectorId={detectorId} timeRange={timeRange} />
```

---

### Phase 3: Ground Truth Labeling UI (Optional but Recommended)

To populate ground truth labels, create a review interface:

**File**: `C:\Dev\IntelliOptics 2.0\cloud\frontend\src\pages\ReviewQueue.tsx`

```typescript
// Add a review button next to each query result
<button onClick={() => handleReview(query.id, 'yes')}>
  Mark as Correct
</button>
<button onClick={() => handleReview(query.id, 'no')}>
  Mark as Incorrect
</button>

const handleReview = async (queryId: string, groundTruth: string) => {
  await axios.patch(`/api/queries/${queryId}`, {
    ground_truth: groundTruth,
    reviewed_at: new Date().toISOString()
  });
  // Refresh data
};
```

Add corresponding backend endpoint:

```python
@router.patch("/{query_id}", response_model=schemas.QueryOut)
def update_query_ground_truth(
    query_id: uuid.UUID,
    payload: schemas.QueryGroundTruthUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update ground truth label for a query."""
    query = db.query(models.Query).get(query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    query.ground_truth = payload.ground_truth
    query.reviewed_by = current_user.id
    query.reviewed_at = datetime.utcnow()
    query.is_correct = (query.result == payload.ground_truth)

    db.commit()
    db.refresh(query)
    return query
```

Schema:

```python
class QueryGroundTruthUpdate(BaseModel):
    ground_truth: str  # e.g., "yes", "no", "defect", "normal"
```

---

## Testing

### Step 1: Populate Test Data

Manually add ground truth labels to existing queries:

```sql
-- Add ground truth labels to some queries for testing
UPDATE queries
SET ground_truth = 'yes', is_correct = (result = 'yes')
WHERE detector_id = 'e1709250-49e2-48e1-85ca-55f16c8fafc6'
  AND id IN (SELECT id FROM queries WHERE detector_id = 'e1709250-49e2-48e1-85ca-55f16c8fafc6' LIMIT 10);

UPDATE queries
SET ground_truth = 'no', is_correct = (result = 'no')
WHERE detector_id = 'e1709250-49e2-48e1-85ca-55f16c8fafc6'
  AND id IN (SELECT id FROM queries WHERE detector_id = 'e1709250-49e2-48e1-85ca-55f16c8fafc6' LIMIT 10 OFFSET 10);
```

### Step 2: Test Backend API

```bash
# Test metrics endpoint
curl http://localhost:8000/detectors/e1709250-49e2-48e1-85ca-55f16c8fafc6/metrics?time_range=7d

# Expected response:
{
  "detector_id": "e1709250-49e2-48e1-85ca-55f16c8fafc6",
  "balanced_accuracy": 0.85,
  "sensitivity": 0.80,
  "specificity": 0.90,
  "true_positives": 8,
  "true_negatives": 9,
  "false_positives": 1,
  "false_negatives": 2,
  "total_queries": 20,
  "time_range": "7d"
}
```

### Step 3: Test Frontend

1. Navigate to detector details page
2. Verify metrics chart displays correctly
3. Verify confusion matrix stats show correct counts
4. Test time range selector

---

## Deployment

### Backend Deployment

```bash
cd C:\Dev\IntelliOptics 2.0\cloud

# Rebuild backend container
docker-compose up -d --build backend

# Run database migration
docker-compose exec backend alembic upgrade head

# Verify
docker logs intellioptics-cloud-backend --tail 50
```

### Frontend Deployment

```bash
cd C:\Dev\IntelliOptics 2.0\cloud\frontend

# Install dependencies
npm install

# Rebuild frontend
docker-compose up -d --build frontend

# Verify
curl http://localhost:3000
```

---

## Summary

**What this adds**:
1. Backend API endpoint for calculating detector accuracy metrics
2. Frontend chart component using Recharts
3. Confusion matrix visualization (TP, TN, FP, FN)
4. Time range filtering (1d, 7d, 30d, all)
5. Ground truth labeling system

**Metrics displayed**:
- **Balanced Accuracy**: Overall system performance across both classes
- **Sensitivity (Accuracy for Yes)**: How well the detector catches positive cases
- **Specificity (Accuracy for No)**: How well the detector avoids false alarms

**Key files modified**:
- `cloud/backend/app/routers/detectors.py` - Add metrics endpoint
- `cloud/backend/app/schemas.py` - Add metrics schema
- `cloud/backend/app/models.py` - Add ground truth columns
- `cloud/frontend/src/components/DetectorMetrics.tsx` - New metrics component
- `cloud/frontend/src/pages/DetectorDetails.tsx` - Integrate metrics component

**Next steps after implementation**:
1. Add ground truth labels through review UI
2. Monitor metrics to improve detector performance
3. Use metrics to identify detectors needing retraining
