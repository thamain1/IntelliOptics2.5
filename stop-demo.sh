#!/bin/bash
# IntelliOptics 2.0 — Stop Demo
# Stops all running services and frees RAM
# Usage: bash stop-demo.sh

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Stopping cloud services..."
cd "$ROOT/cloud"
docker compose down 2>/dev/null || true

echo "Stopping edge services..."
cd "$ROOT/edge"
docker compose down 2>/dev/null || true

echo ""
echo "All IntelliOptics services stopped. RAM freed."
echo "Run 'bash cleanup.sh' to also reclaim disk space from old images."
