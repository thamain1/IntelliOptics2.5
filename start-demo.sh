#!/bin/bash
# IntelliOptics 2.0 — Start Demo
# Starts cloud (frontend + backend) and edge (inference) services
# Usage: bash start-demo.sh [--edge-only | --cloud-only]

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

start_cloud() {
  echo "Starting cloud services (frontend + backend + worker)..."
  cd "$ROOT/cloud"
  docker compose up -d
  echo "  Frontend:  http://localhost:3000"
  echo "  Backend:   http://localhost:8000"
}

start_edge() {
  echo "Starting edge services (inference + edge-api)..."
  cd "$ROOT/edge"
  docker compose up -d
  echo "  Inference: http://localhost:8001"
  echo "  Edge API:  http://localhost:30101"
}

case "${1:-all}" in
  --cloud-only) start_cloud ;;
  --edge-only)  start_edge ;;
  *)            start_cloud; echo ""; start_edge ;;
esac

echo ""
echo "IntelliOptics 2.0 is running. Stop with: bash stop-demo.sh"
