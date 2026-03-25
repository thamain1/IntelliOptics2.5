-- Migration: Add deleted_at column to detectors table for soft delete functionality
-- Version: 001
-- Date: 2026-01-20
-- Description: Enables soft delete for detectors while preserving historical data (queries, escalations, etc.)

-- Add the deleted_at column (nullable - NULL means active, timestamp means deleted)
ALTER TABLE detectors
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP NULL;

-- Create index for efficient filtering of active detectors
CREATE INDEX IF NOT EXISTS idx_detectors_deleted_at ON detectors(deleted_at);

-- Optional: Create index for listing active detectors efficiently
CREATE INDEX IF NOT EXISTS idx_detectors_active ON detectors(id) WHERE deleted_at IS NULL;

-- Verification query (run manually to verify)
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'detectors' AND column_name = 'deleted_at';
