# IntelliOptics 2.5 - Installation Guide

## Prerequisites

- **Windows Server 2019+** or **Windows 10/11 Pro** (Hyper-V capable)
- **Docker Desktop** 4.x+ with Docker Compose V2
- **Git** (to clone the repo)
- **20 GB free disk space** (Docker images + model downloads)
- **8 GB RAM minimum** (16 GB recommended)
- **NVIDIA GPU** (optional) with compute capability >= 7.0 for GPU inference

## Quick Start

```powershell
# 1. Clone the repository
git clone https://github.com/thamain1/IntelliOptics2.5.git
cd IntelliOptics2.5\install

# 2. Run the installer
.\Install-IntelliOptics.ps1

# 3. Open the app
# Frontend: http://localhost/
# Edge API: http://localhost:30101/
```

The installer will:
1. Detect and stop any old IntelliOptics 2.0 containers (if running)
2. Check prerequisites (Docker, disk space, ports)
3. Generate `.env` with pre-configured Supabase/SendGrid credentials and auto-generated API secret key
4. Build all 5 Docker images
5. Start 7 services
6. Run health checks
7. Create admin user (`admin@intellioptics.com` / `admin123`)

## Configuration

### Environment Variables

All configuration is in `install/.env` (created from `.env.template` during install).

Supabase and SendGrid credentials are **pre-configured** in the template. Only change these if connecting to a different Supabase project.

| Variable | Pre-filled | Description |
|----------|------------|-------------|
| `POSTGRES_DSN` | Yes | Supabase PostgreSQL connection string |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anonymous key |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `API_SECRET_KEY` | Auto | JWT signing key (auto-generated per install) |
| `SENDGRID_API_KEY` | Yes | Email alerts via SendGrid |
| `TWILIO_ACCOUNT_SID` | No | SMS alerts via Twilio (optional) |
| `CLOUD_HTTP_PORT` | No | Cloud port (default: 80) |
| `EDGE_PORT` | No | Edge port (default: 30101) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

### Edge Configuration

Edge behavior is configured in `install/config/edge-config.yaml`:
- Detector definitions
- Open-vocabulary detection settings
- VLM model and dual-track config
- Vehicle ID and forensic search settings
- Alert thresholds

### Nginx Configuration

- `install/config/nginx-cloud.conf` — Cloud reverse proxy (frontend + API)
- `install/config/nginx-edge.conf` — Edge API gateway

## GPU Setup

By default, inference runs on CPU. To enable GPU acceleration:

1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
2. Edit `install/docker-compose.prod.yml`
3. Uncomment the GPU block under `edge-inference`:

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

4. Restart: `docker compose -f docker-compose.prod.yml up -d edge-inference`

**Note:** GPUs with compute capability < 7.0 (e.g., GTX 1050 Ti) will automatically fall back to CPU even with GPU enabled.

## Services

| Service | Container | Internal Port | Description |
|---------|-----------|---------------|-------------|
| Cloud Nginx | io-cloud-nginx | 80/443 | Reverse proxy |
| Cloud Backend | io-cloud-backend | 8000 | FastAPI API |
| Cloud Frontend | io-cloud-frontend | 3000 | React UI |
| Cloud Worker | io-cloud-worker | 8081 | ONNX worker |
| Edge Nginx | io-edge-nginx | 30101 | Edge gateway |
| Edge API | io-edge-api | 8718 | Edge endpoint |
| Edge Inference | io-edge-inference | 8001 | AI inference |

## Common Commands

```powershell
cd IntelliOptics2.5\install

# Status
docker compose -f docker-compose.prod.yml ps

# Logs (all services)
docker compose -f docker-compose.prod.yml logs -f

# Logs (specific service)
docker compose -f docker-compose.prod.yml logs -f cloud-backend
docker compose -f docker-compose.prod.yml logs -f edge-inference

# Restart a service
docker compose -f docker-compose.prod.yml restart cloud-backend

# Stop everything
.\scripts\Stop-Services.ps1

# Start again
.\scripts\Start-Services.ps1

# Rebuild after code changes
.\scripts\Build-Images.ps1
.\scripts\Start-Services.ps1

# Full rebuild (no cache)
.\scripts\Build-Images.ps1 -NoCache
```

## Uninstall

```powershell
# Stop and remove containers (keeps images + data)
.\Uninstall-IntelliOptics.ps1

# Full removal (containers + images + volumes + .env)
.\Uninstall-IntelliOptics.ps1 -RemoveAll
```

## Troubleshooting

### Port already in use
Change `CLOUD_HTTP_PORT` or `EDGE_PORT` in `.env`:
```
CLOUD_HTTP_PORT=8080
EDGE_PORT=30102
```

### Backend won't start
Check Supabase credentials:
```powershell
docker compose -f docker-compose.prod.yml logs cloud-backend | Select-String -Pattern "error"
```

### Edge inference slow to start
The inference service downloads YOLOE and VLM models on first run. This can take 2-5 minutes. Check progress:
```powershell
docker compose -f docker-compose.prod.yml logs -f edge-inference
```

### Frontend shows blank page
Check that cloud-nginx is routing correctly:
```powershell
docker compose -f docker-compose.prod.yml logs cloud-nginx
```

### Health check timeout
Models take time to load. Wait 2-3 minutes, then check:
```powershell
docker compose -f docker-compose.prod.yml ps
curl http://localhost/api/health
curl http://localhost:30101/health
```

### Rebuild a single service
```powershell
docker compose -f docker-compose.prod.yml build cloud-frontend
docker compose -f docker-compose.prod.yml up -d cloud-frontend
```
