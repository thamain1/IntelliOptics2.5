# IntelliOptics 2.0 - Release v2.0.0 Deployment Summary

**Date:** January 20, 2026
**Version:** v2.0.0
**Prepared by:** Development Team

---

## Overview

IntelliOptics 2.0 has been packaged and deployed to Azure Container Registry and GitHub. This document provides all the information needed to deploy the application on a test PC or production environment.

---

## 1. Azure Container Registry (ACR)

### Registry Information
- **Registry:** `acrintellioptics.azurecr.io`
- **Repository Path:** `intellioptics/`

### Published Images

#### Cloud Components
| Image | Tags | Size |
|-------|------|------|
| `intellioptics/backend` | v2.0.0, v2.0.0-20260120, latest | ~1.66 GB |
| `intellioptics/frontend` | v2.0.0, v2.0.0-20260120, latest | ~94 MB |
| `intellioptics/worker` | v2.0.0, v2.0.0-20260120, latest | ~1.17 GB |

#### Edge Components
| Image | Tags | Size |
|-------|------|------|
| `intellioptics/edge-api` | v2.0.0, v2.0.0-20260120, latest | ~1.2 GB |
| `intellioptics/inference` | v2.0.0, v2.0.0-20260120, latest | ~13.4 GB |

### Tagging Convention
- `v2.0.0` - Semantic version (immutable release)
- `v2.0.0-20260120` - Version with build date
- `latest` - Always points to most recent build

### Pull Commands
```bash
# Login to ACR (requires Azure CLI)
az acr login --name acrintellioptics

# Pull Cloud images
docker pull acrintellioptics.azurecr.io/intellioptics/backend:v2.0.0
docker pull acrintellioptics.azurecr.io/intellioptics/frontend:v2.0.0
docker pull acrintellioptics.azurecr.io/intellioptics/worker:v2.0.0

# Pull Edge images
docker pull acrintellioptics.azurecr.io/intellioptics/edge-api:v2.0.0
docker pull acrintellioptics.azurecr.io/intellioptics/inference:v2.0.0
```

---

## 2. GitHub Repository

### Repository URL
**https://github.com/thamain1/IntelliOptics-2.0**

### Repository Structure
```
IntelliOptics-2.0/
├── cloud/                    # Central web application
│   ├── backend/              # FastAPI backend
│   ├── frontend/             # React/TypeScript frontend
│   ├── worker/               # Async inference worker
│   ├── nginx/                # Nginx configuration
│   └── docker-compose.yml    # Development compose
├── edge/                     # Edge deployment
│   ├── edge-api/             # Edge API service
│   ├── inference/            # Inference service
│   └── docker-compose.yml    # Edge compose
├── install/                  # Test PC installer
│   ├── docker-compose.prod.yml
│   ├── install-windows.ps1
│   ├── .env.template
│   └── README.md
├── docs/                     # Documentation
└── logo/                     # Branding assets
```

### Clone Command
```bash
git clone https://github.com/thamain1/IntelliOptics-2.0.git
```

---

## 3. Test PC Installation

### Prerequisites
1. **Docker Desktop** - https://www.docker.com/products/docker-desktop
2. **Azure CLI** - https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
3. **Azure Account** with ACR access

### Quick Installation (Windows)

```powershell
# 1. Clone the repository
git clone https://github.com/thamain1/IntelliOptics-2.0.git
cd IntelliOptics-2.0/install

# 2. Run the installer (as Administrator)
.\install-windows.ps1

# 3. Edit .env with your credentials
notepad .env

# 4. Start the application
docker compose -f docker-compose.prod.yml up -d
```

### Manual Installation

```powershell
# 1. Login to Azure
az login
az acr login --name acrintellioptics

# 2. Pull images
docker pull acrintellioptics.azurecr.io/intellioptics/backend:v2.0.0
docker pull acrintellioptics.azurecr.io/intellioptics/frontend:v2.0.0
docker pull acrintellioptics.azurecr.io/intellioptics/worker:v2.0.0
docker pull postgres:15-alpine
docker pull nginx:1.25-alpine

# 3. Configure environment
cd IntelliOptics-2.0/install
copy .env.template .env
# Edit .env with your credentials

# 4. Start services
docker compose -f docker-compose.prod.yml up -d
```

### Access Points
| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Documentation | http://localhost:8000/docs |

---

## 4. Edge Deployment

Edge deployment is for on-premise inference at the edge (factory floor, remote sites, etc.)

### Edge Pull Commands
```powershell
az acr login --name acrintellioptics

docker pull acrintellioptics.azurecr.io/intellioptics/edge-api:v2.0.0
docker pull acrintellioptics.azurecr.io/intellioptics/inference:v2.0.0
docker pull postgres:15-alpine
docker pull nginx:1.25-alpine
```

### Edge Configuration
Copy `edge/.env.template` to `edge/.env` and configure:

| Variable | Description |
|----------|-------------|
| `INTELLIOPTICS_API_TOKEN` | API token from central cloud app |
| `CENTRAL_WEB_APP_URL` | URL of the central cloud deployment |
| `POSTGRES_PASSWORD` | Local edge database password |

### Edge Deployment
```powershell
cd edge
docker compose up -d
```

### Edge Access Points
| Service | URL |
|---------|-----|
| Edge API | http://localhost:8080 |
| Inference Service | http://localhost:8001 |

---

## 5. Required Configuration

### Minimum Required Settings (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | Database password | `MySecureP@ssw0rd!` |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Storage connection | `DefaultEndpointsProtocol=https;...` |
| `API_SECRET_KEY` | JWT signing key (32+ chars) | `your-32-character-secret-key-here!!` |

### Optional Settings

| Variable | Description |
|----------|-------------|
| `SENDGRID_API_KEY` | Email alerts via SendGrid |
| `TWILIO_ACCOUNT_SID` | SMS alerts via Twilio |
| `TWILIO_AUTH_TOKEN` | Twilio authentication |
| `SERVICE_BUS_CONN` | Azure Service Bus for async processing |

---

## 5. Management Commands

```powershell
# View all logs
docker compose -f docker-compose.prod.yml logs -f

# View specific service logs
docker compose -f docker-compose.prod.yml logs -f backend

# Stop all services
docker compose -f docker-compose.prod.yml down

# Restart all services
docker compose -f docker-compose.prod.yml restart

# Update to latest images
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# Check service health
docker compose -f docker-compose.prod.yml ps
```

---

## 6. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Network                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐              │
│  │  nginx  │───▶│ frontend │    │  worker  │              │
│  │  :80    │    │  :3000   │    │ (async)  │              │
│  └────┬────┘    └──────────┘    └────┬─────┘              │
│       │                              │                     │
│       ▼                              ▼                     │
│  ┌──────────┐                  ┌──────────┐               │
│  │ backend  │◀────────────────▶│ postgres │               │
│  │  :8000   │                  │  :5432   │               │
│  └──────────┘                  └──────────┘               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Troubleshooting

### Issue: Can't pull images from ACR
```powershell
# Ensure you're logged in
az login
az acr login --name acrintellioptics

# Verify ACR access
az acr repository list --name acrintellioptics
```

### Issue: Backend won't start
```powershell
# Check database is running
docker compose -f docker-compose.prod.yml logs postgres

# Verify .env has POSTGRES_PASSWORD set
```

### Issue: Frontend can't connect to backend
```powershell
# Ensure backend is healthy
curl http://localhost:8000/health

# Check backend logs
docker compose -f docker-compose.prod.yml logs backend
```

---

## 8. Security Notes

- `.env` files are **excluded from git** and must be configured locally
- Never commit credentials to the repository
- Rotate credentials if they've been exposed
- Use Azure Key Vault for production deployments

---

## 9. Support & Documentation

- **Deployment Guide:** `docs/DEPLOYMENT_GUIDE.md`
- **Quick Start:** `docs/QUICKSTART.md`
- **Architecture:** `docs/ARCHITECTURE.md`
- **Install README:** `install/README.md`

---

## 10. Version History

| Version | Date | Changes |
|---------|------|---------|
| v2.0.0 | 2026-01-20 | Initial release to ACR and GitHub |

---

## Contact

For questions or issues, contact the development team.
