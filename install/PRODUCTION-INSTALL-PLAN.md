# IntelliOptics 2.5 — Production Install System

## Repository
- **Source repo**: https://github.com/thamain1/IntelliOptics2.5
- **All work happens in this repo** — code fixes, install scripts, compose files, configs
- Target deployment: clone this repo on a remote Windows Server with Docker Desktop, run installer

## Context
The IntelliOptics 2.0 `install/` directory has stale Azure-specific scripts (ACR hardcoded, old image tags v2.0.0-v2.0.3). IntelliOptics 2.5 is a fresh repo where we rebuild the full install system from scratch so the full stack (cloud + edge) can be cloned, built, and run on a remote Windows Server machine with Docker Desktop.

Key problems to fix from 2.0:
- Old install scripts reference Azure Container Registry — no longer relevant
- Edge-api has hardcoded `/opt/intellioptics/` paths that break in containers
- Cloud/edge stacks communicate via `host.docker.internal` — fragile
- No unified compose file for single-machine full-stack deployment
- No `.dockerignore` files (bloated image builds)

## Plan

### 1. Fix hardcoded `/opt/` paths in edge-api (prerequisite)

| File | Change |
|------|--------|
| `edge/edge-api/app/core/deviceid.py` | `WELL_KNOWN_PATH` → `os.environ.get("IO_DEVICE_PATH", "/data/device")` |
| `edge/edge-api/app/escalation_queue/constants.py` | `DEFAULT_QUEUE_BASE_DIR` → `os.environ.get("IO_QUEUE_PATH", "/data/queue")` |
| `edge/edge-api/app/metrics/iq_activity.py` | base_dir → `os.environ.get("IO_METRICS_PATH", "/data/metrics")` |
| `edge/scripts/download-models.py` | base_path → `os.environ.get("MODEL_REPOSITORY", "/models")` |

Defaults use `/data/` which the edge-api Dockerfile already creates and the compose mounts as a volume.

### 2. Fix frontend API URL

**File:** `cloud/frontend/src/App.tsx`

Change `axios.defaults.baseURL = 'http://localhost:8000'` → `import.meta.env.VITE_API_BASE_URL || ''`

Empty string = relative URLs in production (nginx proxies `/api/` to backend). Dev can set `VITE_API_BASE_URL=http://localhost:8000`.

### 3. Add `.dockerignore` files

Create in `cloud/frontend/`, `cloud/backend/`, `cloud/worker/`, `edge/edge-api/`, `edge/inference/`:
- Exclude `node_modules/`, `dist/`, `__pycache__/`, `.env`, `*.pyc`, `.git`

### 4. Delete old install files

Remove:
- `install/install-windows.ps1`
- `install/deploy-azure.ps1`
- `install/docker-compose.prod.yml`
- `install/.env.template`
- `install/nginx.conf`

Keep `install/README.md` (will be overwritten).

### 5. Create unified `install/docker-compose.prod.yml`

Single compose file with all 8 services on one Docker network (`intellioptics-net`):

**Cloud services:** cloud-nginx (ports 80/443), cloud-backend, cloud-frontend, cloud-worker
**Edge services:** edge-nginx (port 30101), edge-api, edge-inference

Key design decisions:
- **Single network** — cloud-backend reaches edge-inference directly as `edge-inference:8001` (no `host.docker.internal`)
- **No exposed internal ports** — only nginx ports (80, 443, 30101) are exposed to host
- **No cloud postgres** — production uses Supabase
- **Edge postgres commented out** — not needed when cloud+edge are co-located
- **GPU support commented out** with clear label to uncomment
- **Named volumes** for models, data, videos (fixes relative `../videos` path issue)
- **Build contexts** point to `../cloud/backend`, `../edge/inference`, etc.

### 6. Create merged `install/.env.template`

Single env file organized by section:
- DATABASE (Supabase): `POSTGRES_DSN`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`
- API SECURITY: `API_SECRET_KEY` (auto-generated), `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- ALERTS (optional): SendGrid, Twilio
- APPLICATION: `APP_ENV`, `LOG_LEVEL`, `CORS_ALLOWED_ORIGINS`
- EDGE DEVICE: `EDGE_DEVICE_ID`, thresholds
- PORTS: `CLOUD_HTTP_PORT`, `EDGE_PORT`

### 7. Create config directory

```
install/config/
  edge-config.yaml    # Copy from edge/config/ with prod defaults
  nginx-cloud.conf    # Copy from cloud/nginx/nginx.conf
  nginx-edge.conf     # Copy from edge/nginx/nginx.conf
```

### 8. Create PowerShell install script

**`install/Install-IntelliOptics.ps1`** — main orchestrator calling modular scripts:

```
install/scripts/
  Test-Prerequisites.ps1       # Docker running, ports free, disk space
  Initialize-Environment.ps1   # .env generation, secret auto-gen, Supabase prompts
  Build-Images.ps1             # Build all 7 images with progress
  Start-Services.ps1           # docker compose up -d
  Test-Health.ps1              # Retry loop checking all services (3 min timeout)
  Create-AdminUser.ps1         # docker exec create_admin.py
  Stop-Services.ps1            # Graceful shutdown
```

**Also create `install/Uninstall-IntelliOptics.ps1`** for clean removal.

### 9. Write `install/README.md`

Comprehensive guide covering:
- Prerequisites (Docker Desktop, Git, 20GB disk)
- Quick start (3 commands)
- Configuration reference
- GPU setup
- Troubleshooting
- Useful commands (logs, restart, stop)

## Files to Modify/Create

All paths are relative to the IntelliOptics2.5 repo root.

| Action | File |
|--------|------|
| Edit | `edge/edge-api/app/core/deviceid.py` |
| Edit | `edge/edge-api/app/escalation_queue/constants.py` |
| Edit | `edge/edge-api/app/metrics/iq_activity.py` |
| Edit | `edge/scripts/download-models.py` |
| Edit | `cloud/frontend/src/App.tsx` |
| Create | `cloud/frontend/.dockerignore` |
| Create | `cloud/backend/.dockerignore` |
| Create | `cloud/worker/.dockerignore` |
| Create | `edge/edge-api/.dockerignore` |
| Create | `edge/inference/.dockerignore` |
| Delete | `install/install-windows.ps1` |
| Delete | `install/deploy-azure.ps1` |
| Delete | `install/docker-compose.prod.yml` (old) |
| Delete | `install/.env.template` (old) |
| Delete | `install/nginx.conf` (old) |
| Create | `install/docker-compose.prod.yml` (new unified) |
| Create | `install/.env.template` (new merged) |
| Create | `install/config/edge-config.yaml` |
| Create | `install/config/nginx-cloud.conf` |
| Create | `install/config/nginx-edge.conf` |
| Create | `install/Install-IntelliOptics.ps1` |
| Create | `install/Uninstall-IntelliOptics.ps1` |
| Create | `install/scripts/Test-Prerequisites.ps1` |
| Create | `install/scripts/Initialize-Environment.ps1` |
| Create | `install/scripts/Build-Images.ps1` |
| Create | `install/scripts/Start-Services.ps1` |
| Create | `install/scripts/Test-Health.ps1` |
| Create | `install/scripts/Create-AdminUser.ps1` |
| Create | `install/scripts/Stop-Services.ps1` |
| Rewrite | `install/README.md` |

## Verification
1. Clone `https://github.com/thamain1/IntelliOptics2.5` on a clean Windows Server with Docker Desktop
2. Run `.\install\Install-IntelliOptics.ps1`
3. Script checks prerequisites, prompts for Supabase creds, builds images, starts services
4. All 7 containers healthy within 3 minutes
5. Frontend accessible at `http://localhost/`
6. Edge API accessible at `http://localhost:30101/`
7. Admin login works with generated credentials
8. Cloud backend can reach edge inference (test IntelliSearch or open-vocab detection)
