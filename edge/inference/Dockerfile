# ============================================================
# IntelliOptics 2.5 - Inference Service (Multi-Stage Build)
#
# Stage 1 (exporter):       Ultralytics + CLIP → ONNX export
# Stage 2 (vlm-downloader): Download Moondream ONNX model
# Stage 3 (runtime):        Lean image — onnxruntime + moondream + fastapi
#
# Result: ~1.0GB image, 100% Apache 2.0 licensed runtime
# ============================================================

# ── Stage 1: YOLOE ONNX Exporter (build-time only) ──────────
FROM python:3.11-slim AS exporter

WORKDIR /export

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    ultralytics>=8.3.0 \
    "clip @ git+https://github.com/openai/CLIP.git"

COPY tools/export_onnx.py /export/export_onnx.py
RUN python export_onnx.py --output /export/models/

# ── Stage 2: Moondream VLM Downloader ────────────────────────
FROM python:3.11-slim AS vlm-downloader

RUN pip install --no-cache-dir huggingface_hub

RUN python -c "\
from huggingface_hub import hf_hub_download; \
hf_hub_download('vikhyatk/moondream2', 'moondream-2b-int8.mf.gz', \
    local_dir='/vlm-models', revision='onnx')"

# ── Stage 3: Runtime (GPU-enabled) ────────────────────────────
# CUDA 12.6 base with cuDNN 9 — supports compute capability 3.5+ (GTX 900+)
FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu22.04

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install Python 3.11 + runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
    curl libgomp1 libgl1 libglib2.0-0 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy ONNX model + vocabulary from exporter stage
COPY --from=exporter /export/models/ /models/yoloworld/

# Copy Moondream VLM model from downloader stage
COPY --from=vlm-downloader /vlm-models/ /vlm-models/

# Copy application code
COPY inference_service.py /app/inference_service.py
COPY yoloe_inference.py /app/yoloe_inference.py
COPY vlm_inference.py /app/vlm_inference.py
COPY vehicle_id.py /app/vehicle_id.py
COPY forensic_search.py /app/forensic_search.py

# Create model directory for custom detector models
RUN mkdir -p /models

# Health check
HEALTHCHECK --interval=10s --timeout=3s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose ports
EXPOSE 8001 8081

# Run inference service
CMD ["python", "inference_service.py"]
