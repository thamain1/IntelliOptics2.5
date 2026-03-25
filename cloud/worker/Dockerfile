# ---------- Base ----------
FROM python:3.11-slim

# Allow overriding the SDK ref (branch, tag, or commit)
ARG SDK_REF=main

# Basic Python/pip behavior
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OS deps: git for potential VCS installs, curl for healthcheck, CA certs
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# ---------- App layout ----------
WORKDIR /app/worker

# 1) Install runtime dependencies (NO private GitHub dependencies)
RUN python -m pip install --upgrade pip \
 && pip install \
      onnxruntime \
      opencv-python-headless \
      requests \
      numpy>=2.0 \
      pydantic>=2.7 \
      httpx>=0.27 \
      python-dotenv>=1.0 \
      pillow>=10.4

# 2) Copy the worker sources
#    onnx_worker.py is the main entrypoint used by this image.
COPY onnx_worker.py /app/worker/onnx_worker.py
COPY detector_inference.py /app/worker/detector_inference.py

# (Optional extras: kept for future refactors; not used by the ONNX entrypoint)
COPY worker.py /app/worker/worker.py
COPY models.py /app/worker/models.py
COPY db.py /app/worker/db.py
COPY .env.example /app/worker/.env.example

# ---------- Runtime ----------
# Run as non-root
RUN adduser --disabled-password --gecos "" app \
 && chown -R app:app /app
USER app

# Health endpoint used by probes (onnx_worker serves /health on 8081)
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:8081/health || exit 1

# Start the ONNX worker
ENTRYPOINT ["python", "-u", "/app/worker/onnx_worker.py"]
