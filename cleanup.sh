#!/bin/bash
# IntelliOptics 2.0 — Cleanup
# Removes old Docker images, stopped containers, and build cache to reclaim disk
# Usage: bash cleanup.sh [--deep]
#
# --deep: Also removes VLM model cache volume (will re-download ~1.7GB on next start)

set -e

echo "=== Docker Disk Usage Before ==="
docker system df
echo ""

echo "Removing stopped containers..."
docker container prune -f

echo "Removing dangling images..."
docker image prune -f

echo "Removing unused build cache..."
docker builder prune -f

echo "Removing unused images (not referenced by any container)..."
docker image prune -a -f

if [ "$1" = "--deep" ]; then
  echo ""
  echo "Deep clean: removing VLM model cache volume..."
  docker volume rm edge_vlm_models 2>/dev/null || true
  docker volume rm intellioptics-20_vlm_models 2>/dev/null || true
  echo "VLM models will re-download on next start (~1.7GB)."
fi

echo ""
echo "=== Docker Disk Usage After ==="
docker system df
echo ""
echo "Cleanup complete."
