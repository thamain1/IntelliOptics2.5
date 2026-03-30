# ============================================================
# IntelliOptics 2.5 - Inference Service (Multi-Stage Build)
#
# Stage 1 (exporter):       Ultralytics + CLIP → ONNX export
# Stage 2 (vlm-downloader): Pre-download Moondream2 from HuggingFace
# Stage 3 (runtime):        ONNX Runtime (YOLOE) + PyTorch/transformers (VLM)
#
# YOLOE:  Pure ONNX — no Ultralytics at runtime (Apache 2.0)
# VLM:    HuggingFace transformers + PyTorch (BSD/Apache 2.0)
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

# ── Stage 2: Moondream VLM Pre-Download ────────────────────
FROM python:3.11-slim AS vlm-downloader

RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir huggingface_hub "transformers>=4.51.1,<5.0.0" einops accelerate "pillow>=11.0.0"

# Pre-download model weights so runtime doesn't need internet
RUN python -c "\
from transformers import AutoModelForCausalLM; \
AutoModelForCausalLM.from_pretrained( \
    'vikhyatk/moondream2', revision='2025-06-21', \
    trust_remote_code=True, cache_dir='/vlm-models')"

# ── Stage 3: Runtime ──────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libgomp1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (torch from cu128 wheel index for CUDA 12.x driver support)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu128

# Copy ONNX model + vocabulary from exporter stage
COPY --from=exporter /export/models/ /models/yoloworld/

# Copy pre-downloaded Moondream VLM from downloader stage
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
