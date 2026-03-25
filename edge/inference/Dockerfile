FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies (libgl1 provides OpenGL for OpenCV, git for CLIP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy inference service code
COPY inference_service.py /app/inference_service.py
COPY yoloe_inference.py /app/yoloe_inference.py
COPY vlm_inference.py /app/vlm_inference.py
COPY vehicle_id.py /app/vehicle_id.py
COPY forensic_search.py /app/forensic_search.py

# YOLOWorld model (yolov8s-worldv2.pt) is auto-downloaded by Ultralytics on first use.
# If you have a local copy, uncomment below to bake it into the image:
# COPY yolov8s-worldv2.pt /app/yolov8s-worldv2.pt

# Create model directory
RUN mkdir -p /models

# Health check
HEALTHCHECK --interval=10s --timeout=3s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose ports
EXPOSE 8001 8081

# Run inference service
CMD ["python", "inference_service.py"]
