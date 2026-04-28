# IntelliOptics 2.5 — Remote Install Handoff

**Read this entire file first.** This is the authoritative install + demo prep reference.
Target deployment: a single Windows 11 Pro machine (the "remote" / demo machine).
Demo: Thursday 2026-04-30, federal/military audience, "show as much capability as possible."
Last updated: 2026-04-28.

---

## 0 · TL;DR — install in 8 commands

```powershell
# 0. Stop any old IntelliOptics 1.0 / 2.0 (see §3 for full cleanup if these don't catch everything)
docker ps --format "{{.Names}}" | Select-String "intellioptics|^io-" | ForEach-Object { docker stop $_ }
docker ps -a --format "{{.Names}}" | Select-String "intellioptics|^io-" | ForEach-Object { docker rm $_ }

# 1. Clone fresh
cd C:\Dev
git clone https://github.com/thamain1/IntelliOptics2.5.git intellioptics_2.5
cd intellioptics_2.5\install

# 2. Create .env from secrets file the user will transfer to you separately
#    (see §4 — paste the contents of secrets-for-remote.env into install\.env)
notepad .env

# 3. Run the installer (interactive — accepts defaults)
powershell -ExecutionPolicy Bypass -File .\Install-IntelliOptics.ps1
```

The installer handles: prereq check → env validation → Docker build (~16 GB image) →
service start (7 containers) → health check → admin user provisioning. **Total time:
20–40 min on first run** (mostly the build, which downloads Moondream 2B fp32 once
and bakes it into the image).

After install, browse to `http://localhost/` and log in with `jmorgan@4wardmotions.com` /
`g@za8560EYAS`.

---

## 1 · What you're installing

IntelliOptics 2.5 is a real-time edge-AI inspection platform. **Single-machine
deployment** = cloud + edge stacks both run on the demo PC, in 7 Docker containers
on one Docker network (`intellioptics-net`).

Capabilities on stage:
| # | Capability | URL / path | Notes |
|---|---|---|---|
| 1 | Live YOLOE detection (376-class baked vocab) | Demo Stream → IntelliSearch | Fast on CPU |
| 2 | Open-vocab IntelliSearch (YOLOE + VLM fallback for novel prompts) | Demo Stream → IntelliSearch with prompt | VLM = 10–30s thinking time |
| 3 | Vehicle ID (plate OCR + color + make/model) | `/vehicle-search` | Fast |
| 4 | Forensic BOLO video search | `/forensic-search` | User will record video on remote |
| 5 | IntelliPark dashboard | `/parking` | Fast |
| 6 | Active learning workflow (label → train → promote) | `/escalation-queue`, `/training` | High-impact for ML-savvy audience |
| 7 | Moondream VLM Q&A / OCR / detect | `/open-vocab` | 10–30s per call on CPU |

---

## 2 · Hardware / network preflight

Target machine specs (verified 2026-04-28):
- **Ryzen AI 9 HX 370** (12 core / 24 thread) — plenty fast for CPU inference
- **64 GB RAM** (61.6 usable) — abundant headroom (Moondream fp32 needs ~11 GB)
- **AMD Radeon 890M iGPU, 2 GB shared** — **NOT USABLE** (no NVIDIA, no PyTorch CUDA path)
- **932 GB storage** (810 GB free) — plenty for ~30 GB total install (Docker image + models + videos)
- **Windows 11 Pro 24H2**

**CRITICAL:** Do NOT uncomment the `deploy.resources.reservations.devices` GPU block in
`install/docker-compose.prod.yml`. There is no NVIDIA GPU. Leave inference on CPU.

**Network:** Outbound internet required during install (Docker Hub for base images,
HuggingFace for Moondream weights, Supabase, SendGrid). All standard HTTPS.

**Ports the host will bind:** 80, 443, 30101. Make sure nothing else holds these:
```powershell
Get-NetTCPConnection -LocalPort 80,443,30101 -State Listen -ErrorAction SilentlyContinue
```

**Docker Desktop:** required. Install from `https://www.docker.com/products/docker-desktop`
if not present. Confirm WSL2 backend is enabled (default on Win11 24H2).

---

## 3 · Stopping old IntelliOptics installs

The user reports IntelliOptics 1.0 may still be running on the target. The 2.5
installer's Step 0 only checks for 2.0 container names (`intellioptics-cloud-*`,
`intellioptics-edge-*`, `intellioptics-inference`). Run these BEFORE the installer:

```powershell
# A. Stop ALL Docker containers with intellioptics in the name (covers 1.0, 2.0, custom)
docker ps -a --format "{{.Names}}" | Select-String "(?i)intellioptics|^io-" | ForEach-Object { docker stop $_; docker rm $_ }

# B. Check for non-Docker installs of IO 1.0 (might be a Windows service or a raw Python process)
Get-Service | Where-Object { $_.DisplayName -match "intellioptics|IO " } | ForEach-Object { Stop-Service $_.Name -Force; Set-Service $_.Name -StartupType Disabled }
Get-Process | Where-Object { $_.ProcessName -match "intellioptics" } | Stop-Process -Force

# C. Confirm ports are free
Get-NetTCPConnection -LocalPort 80,443,30101,8000,8001,8718,30101 -State Listen -ErrorAction SilentlyContinue

# D. Old volumes from 2.0/1.0 — ONLY remove if you are SURE you don't need the data
docker volume ls | Select-String "intellioptics|^io-"
# If you want to wipe them: docker volume rm <name>
```

If port 80 is still bound after all of the above, IIS may be running:
```powershell
Stop-Service W3SVC -Force; Set-Service W3SVC -StartupType Disabled
```

---

## 4 · The `.env` file

The user will transfer a file called `secrets-for-remote.env` from the dev machine
to the demo machine. **Copy its contents into `install\.env`** (same directory as
`Install-IntelliOptics.ps1`). The installer reads `.env` directly.

**What's in it (categorized):**
- Database (Supabase, project `uwhbbnouxmpounqeudiw`) — pre-filled, do not change
- API security: `API_SECRET_KEY` is pre-generated; `JWT_ALGORITHM=HS256`
- Admin accounts:
  - `jmorgan@4wardmotions.com` / `g@za8560EYAS` (permanent support admin)
  - `admin@intellioptics.com` / `admin123` (bootstrap, only created if missing)
- SendGrid: real key included (alerts@4wardmotions.com sender)
- Twilio: blank by default (SMS not in demo scope; uncomment in `Twilio Recovery.txt` if needed)
- App: `APP_ENV=production`, `LOG_LEVEL=INFO`, `CORS_ALLOWED_ORIGINS=http://localhost`
- Edge: `EDGE_DEVICE_ID=edge-prod-001`, default thresholds
- Ports: 80 / 443 / 30101 (only change if you must)

**Do NOT commit `.env`.** It is in `.gitignore`.

---

## 5 · Running the installer step-by-step

```powershell
cd C:\Dev\intellioptics_2.5\install
powershell -ExecutionPolicy Bypass -File .\Install-IntelliOptics.ps1
```

The installer goes through 6 steps:

1. **Prerequisites** (`Test-Prerequisites.ps1`) — verifies Docker Desktop is running,
   confirms compose v2 syntax works, checks disk space.
2. **Environment** (`Initialize-Environment.ps1`) — validates `.env`, auto-generates
   `API_SECRET_KEY` if blank.
3. **Build** (`Build-Images.ps1`) — `docker compose build`. **This is the long step
   (~15–25 min)** because the inference image bakes in Moondream 2B fp32 (multi-stage:
   exporter → vlm-downloader → runtime).
4. **Start** (`Start-Services.ps1`) — `docker compose up -d`.
5. **Health check** (`Test-Health.ps1`) — pings each service. May report degraded
   on first run while VLM finishes loading (1–2 min after start).
6. **Admin user** (`Create-AdminUser.ps1`) — seeds the two admin accounts.

**If the build step fails with `docker-credential-desktop not found`**, this is the
known Windows Docker Desktop credential-helper bug. Fix:
```powershell
Copy-Item ~\.docker\config.json ~\.docker\config.json.bak
notepad ~\.docker\config.json
# Remove the line:  "credsStore": "desktop"
# Save and re-run the installer with -SkipBuild removed
```

**Re-run options:**
- `.\Install-IntelliOptics.ps1 -SkipBuild` — skip Docker build, use existing images
- `.\Install-IntelliOptics.ps1 -NoCache` — force rebuild from scratch (rarely needed)
- `.\Install-IntelliOptics.ps1 -SkipHealthCheck` — bypass health check (for slow VLM load)

---

## 6 · Post-install validation — run all 10 of these

If any of these fail, **DO NOT GO TO THE DEMO** — fix first. They take ~5 min total.

```powershell
# Containers up
docker compose -f docker-compose.prod.yml ps

# Should see 7 services, all "Up" or "Up (healthy)":
#   io-cloud-nginx, io-cloud-backend, io-cloud-frontend, io-cloud-worker,
#   io-edge-nginx, io-edge-api, io-edge-inference

# 1. Cloud backend health
curl http://localhost/api/health

# 2. Cloud frontend served
curl -I http://localhost/   # expect 200

# 3. Edge API health
curl http://localhost:30101/health

# 4. Edge inference health (look for yoloe_loaded=true AND vlm_loaded=true)
docker exec io-edge-inference curl http://localhost:8001/health

# 5. YOLOE detection works (uses test image — substitute any jpg path)
docker exec io-edge-inference curl -X POST -F "image=@/tmp/test.jpg" "http://localhost:8001/yoloe?prompts=person,car&conf=0.25&vlm_fallback=false"

# 6. VLM responds (slow — 15–30s on this CPU; that's normal)
docker exec io-edge-inference curl -X POST -F "image=@/tmp/test.jpg" "http://localhost:8001/vlm/query" -F "question=What is in this image?"

# 7. Login flow works (create-admin already ran in step 6 of installer)
# Open browser to http://localhost/  →  log in as jmorgan@4wardmotions.com / g@za8560EYAS

# 8. Detector list loads after login
# Click "Detectors" in nav — should populate from Supabase

# 9. Live overlay renders
# Click "Demo Stream" → load any RTSP/YouTube/webcam → IntelliSearch with prompt "person"
# Bounding boxes should overlay at ~30fps

# 10. Forensic search page renders
# Click "Forensic Search" — page loads with empty job list (will populate after recording video)
```

---

## 7 · Demo flow — 7 segments, ~30–40 minutes total

Open the IntelliOptics2.5 deck (`docs/IntelliOptics2.5_v3.pptx` or
`docs/client-deck.html`) on a second display alongside the live UI.

**Pre-warm before going live:** Run a YOLOE call and a VLM query 60 seconds before stage
time. The first VLM query after startup is the slowest (~30s) because of model JIT.
Subsequent calls are 10–20s.

| # | Segment | URL | Action | Talking-point |
|---|---|---|---|---|
| 1 | Login + dashboard tour | `http://localhost/` | Sign in, click through nav | "Single pane of glass; everything runs locally — no cloud round-trips for inference" |
| 2 | Live YOLOE overlay | `/demo-streams` | Pick a feed, click play | "30fps real-time detection at the edge — runs on this PC, not in the cloud" |
| 3 | Open-vocab IntelliSearch | `/demo-streams` → IntelliSearch | Type a prompt like "person carrying a backpack" | "Open-vocabulary — no retraining needed for new objects. The visual language model is reasoning about the scene now…" (covers the 10–30s VLM beat) |
| 4 | Vehicle ID | `/vehicle-search` | Upload `docs/car.jpg` (committed test fixture) | "Plate OCR + color + make/model from a single image. Works for stills, video, or live streams." |
| 5 | Forensic BOLO search | `/forensic-search` | Submit a query like "silver SUV" against the recorded video | "Search hours of footage in seconds. Critical for post-incident review." |
| 6 | IntelliPark dashboard | `/parking` | Show occupancy + violations | "Same vision pipeline applied to parking enforcement. Real-time occupancy, automatic violation detection." |
| 7 | Active learning loop | `/escalation-queue` → `/training` | Show the queue, label one, kick a training run | "When the model is uncertain, a human reviews. Labels feed back into training automatically — the system gets smarter every day." |

**Fallbacks if a feature glitches on stage:**
- VLM hangs > 30s → kill the request, restart with `docker restart io-edge-inference` (60s).
- Live overlay is stuttery → switch to a recorded video instead of live RTSP.
- Forensic search returns nothing → use a different query phrase, or fall back to vehicle ID.
- Whole stack misbehaves → see §9 hard reset (under 5 min).

---

## 8 · Top 5 troubleshooting issues

### Issue 1 — `docker-credential-desktop not found` on build
```powershell
notepad ~\.docker\config.json
# Remove "credsStore": "desktop", save, retry build
```

### Issue 2 — Port 80 already bound (IIS, Skype legacy, or old IO)
```powershell
Get-NetTCPConnection -LocalPort 80 -State Listen | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Get-Process -Id $_ }
# Stop the offending process. If it's IIS:
Stop-Service W3SVC -Force
```

### Issue 3 — Health check fails with `vlm_loaded=false`
The first VLM load on a cold container takes 30–60s (the `lifespan` handler pre-loads
Moondream). Wait 90s, re-check `/health`. If still false:
```powershell
docker logs io-edge-inference --tail 100
# Look for "PyTorch loaded" and "Moondream loaded" lines.
# If OOM: confirm 64 GB RAM is recognized by Docker Desktop (Settings → Resources → Memory).
```

### Issue 4 — Login fails after install
```powershell
docker exec io-cloud-backend python /app/app/create_admin.py
# Re-seeds both admin accounts using ADMIN_EMAIL / ADMIN_PASSWORD from .env
```
Container name is `io-cloud-backend` (not `intellioptics-cloud-backend` — that was 2.0).

### Issue 5 — VLM volume holding old/corrupted weights
```powershell
docker volume rm install_vlm_models
# Re-pull on next build. Adds ~5 min to next install run.
```

---

## 9 · Hard reset (nuke + restart) — under 5 minutes

If everything is broken and the demo is in 15 minutes:

```powershell
cd C:\Dev\intellioptics_2.5\install
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d
# Wait 60–90s for services to settle and VLM to pre-load
docker compose -f docker-compose.prod.yml ps
```

This keeps images cached (no rebuild) but wipes container state. Faster than a full
reinstall. Login still works because the bootstrap admin auto-seeds on backend start.

---

## 10 · Federal / military audience FAQ

Likely questions and short answers:

- **"Can this run air-gapped?"** Yes — the inference path is fully local. Cloud is
  only Supabase (DB) + SendGrid (email alerts) + Twilio (SMS). For a no-internet
  deployment, swap Supabase → on-prem Postgres (env var `POSTGRES_DSN`) and disable
  alerts. Demo today is connected because that's the simplest path.

- **"What's the licensing situation on the models?"** Moondream is Apache 2.0
  (free for any use including commercial). YOLOE is on a pure-ONNX runtime path —
  Apache 2.0 — no Ultralytics dependency at runtime. The training-time Ultralytics
  is AGPL-3.0; we're not redistributing it. Clean for client deployment.

- **"Where does the data live?"** Supabase (PostgreSQL on AWS us-east-1) for the
  default deployment. Customer-specific deployments use a per-customer Supabase
  project or on-prem Postgres. Images stored in Supabase Storage (50 MB/file) or
  customer-provided S3-compatible storage.

- **"How does it handle classified data?"** Default deployment is not FedRAMP /
  FISMA accredited. The architecture supports a fully-local install (no cloud
  dependencies) for accredited environments. We can scope an air-gap install for
  any procurement.

- **"How fast does it learn new objects?"** Open-vocab uses YOLOE's 376-class baked
  vocabulary plus VLM rescue for any novel prompt — zero training. For higher
  precision on a specific object, the active-learning loop closes overnight: review
  uncertain detections, label them, automatic retrain at threshold, canary deploy,
  promote.

---

## 11 · After the demo

If the customer asks for a follow-up install on their hardware: the `Install-IntelliOptics.ps1`
script + `.env.template` is the same procedure. The only customizations are:
- Different Supabase project (or on-prem Postgres) — change `POSTGRES_DSN` and `SUPABASE_*`
- Different admin email — change `ADMIN_EMAIL`
- For a **detection-only** client (no IntelliPark / no vehicle ID), an `IO_FEATURES`
  env-flag system is on the roadmap (see `~/.claude/projects/c--Dev/memory/project_io_feature_flags.md`).

---

## Appendix · Critical recent commits (in case you need to verify the clone)

- `799d646` (2026-04-28) — vlm_fallback param + auto-training auth fix (THIS IS THE TIP)
- `8bc9f36` (2026-04-22) — bbox normalization + standard detector overlays
- `123a72b` (2026-04-22) — OODD per-detector threshold + drift endpoint
- `2864161` — temporal deduplication
- `3fcf319` — escalation queue priority

If `git log --oneline` doesn't show `799d646` at HEAD, **stop and pull again** — you
got a stale clone.
