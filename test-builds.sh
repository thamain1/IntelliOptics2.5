#!/bin/bash
# IntelliOptics 2.0 - Test Container Builds
# Verifies all Docker images build successfully before deployment

set -e

echo "=========================================="
echo "Testing IntelliOptics 2.0 Container Builds"
echo "=========================================="

# Test Edge Builds
echo ""
echo "[1/6] Building Edge nginx..."
cd "/c/Dev/IntelliOptics 2.0/edge/nginx"
docker build -t intellioptics-edge-nginx:test . || exit 1

echo ""
echo "[2/6] Building Edge API..."
cd "/c/Dev/IntelliOptics 2.0/edge/edge-api"
docker build -t intellioptics-edge-api:test . || exit 1

echo ""
echo "[3/6] Building Edge Inference Service..."
cd "/c/Dev/IntelliOptics 2.0/edge/inference"
docker build -t intellioptics-inference:test . || exit 1

# Test Cloud Builds
echo ""
echo "[4/6] Building Cloud nginx..."
cd "/c/Dev/IntelliOptics 2.0/cloud/nginx"
docker build -t intellioptics-cloud-nginx:test . || exit 1

echo ""
echo "[5/6] Building Cloud Backend..."
cd "/c/Dev/IntelliOptics 2.0/cloud/backend"
docker build -t intellioptics-backend:test . || exit 1

echo ""
echo "[6/6] Building Cloud Frontend..."
cd "/c/Dev/IntelliOptics 2.0/cloud/frontend"
docker build -t intellioptics-frontend:test . || exit 1

echo ""
echo "=========================================="
echo "✅ All builds completed successfully!"
echo "=========================================="
echo ""
echo "Built images:"
docker images | grep intellioptics | grep test
echo ""
echo "Next steps:"
echo "1. Configure .env files with your credentials"
echo "2. Deploy cloud: cd cloud && docker-compose up -d"
echo "3. Deploy edge: cd edge && docker-compose up -d"
