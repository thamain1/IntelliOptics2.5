# IntelliOptics 2.0 - Azure Cost Optimization Guide

**Date:** January 20, 2026
**Version:** v2.0.0
**Purpose:** Cost analysis and optimization strategy for demo-ready deployment

---

## Executive Summary

This document outlines the cost optimization strategy for IntelliOptics 2.0 Azure infrastructure. The goal is to minimize costs while maintaining demo capability until a paying customer is secured.

**Bottom Line:**
- Current spend: **$342/month**
- Optimized spend: **$13-28/month**
- Annual savings: **$3,768 - $3,948**

---

## 1. Current Azure Cost Analysis

### Monthly Spend: $342.32 USD (January 2026)

| Resource | Service | Cost/Month | % of Total |
|----------|---------|------------|------------|
| PostgreSQL (pg-intellioptics) | Ddsv5 vCore + Storage | $91.38 | 27% |
| Container App (intellioptics-api) | vCPU + Memory | $96.15 | 28% |
| AKS (intellioptics) | Uptime SLA | $46.30 | 14% |
| Container App (io-worker) | vCPU + Memory | $48.06 | 14% |
| API Management (apim) | Developer Unit | $30.40 | 9% |
| App Service Plans (2x B1) | Linux | $15.71 | 5% |
| Container Registry | Standard | $12.83 | 4% |
| Storage/Other | Various | $1.49 | <1% |

---

## 2. Redundancy Issues Identified

The current infrastructure has **duplicate services** serving the same purpose:

| Purpose | Resource 1 | Resource 2 | Issue |
|---------|------------|------------|-------|
| Container hosting | Container Apps ($144/mo) | AKS ($46/mo) | Paying for both |
| API gateway | API Management ($30/mo) | FastAPI (built-in) | APIM not needed |
| Web hosting | App Service Plans ($16/mo) | Container Apps | Paying for both |

**Redundant spend: ~$92/month**

---

## 3. Understanding the Architecture

### ACR vs Container Apps

| Component | What It Does | Cost | Needed for Demos? |
|-----------|--------------|------|-------------------|
| **ACR** | Stores Docker images (warehouse) | $13/mo | YES |
| **Container Apps** | Runs images 24/7 in cloud (compute) | $144/mo | NO |

**Key Insight:** ACR stores your images. Container Apps runs them. For demos, the team pulls from ACR and runs locally - no cloud compute needed.

### Images Stored in ACR

| Image | Tag | Size |
|-------|-----|------|
| intellioptics/backend | v2.0.0 | ~1.66 GB |
| intellioptics/frontend | v2.0.0 | ~94 MB |
| intellioptics/worker | v2.0.0 | ~1.17 GB |
| intellioptics/edge-api | v2.0.0 | ~1.2 GB |
| intellioptics/inference | v2.0.0 | ~13.4 GB |

---

## 4. Demo-Ready Architecture

### How Local Demos Work

```
┌─────────────────────────────────────────────────────┐
│              Demo Laptop (Docker)                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Frontend │  │ Backend  │  │  Worker  │  ← Pull from ACR
│  │ (React)  │  │ (FastAPI)│  │          │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       │             │             │               │
│       └─────────────┼─────────────┘               │
│                     │                             │
│              ┌──────┴──────┐                      │
│              │  PostgreSQL │  ← Local container   │
│              │  (Docker)   │    (FREE)            │
│              └─────────────┘                      │
│                                                   │
└─────────────────────────────────────────────────────┘

Cloud Cost: $13/month (ACR only)
```

### Demo Flow for Team

1. **Prerequisites** (one-time):
   - Install Docker Desktop
   - Install Azure CLI
   - Get ACR access granted

2. **Before Demo**:
   ```powershell
   cd IntelliOptics-2.0/install
   .\install-windows.ps1
   ```

3. **Run Demo**:
   - Open http://localhost
   - Full app running locally

4. **After Demo**:
   ```powershell
   docker compose -f docker-compose.prod.yml down
   ```

---

## 5. Cost Optimization Options

### Option A: Minimum Cost ($13/month)

Keep only ACR. Delete everything else.

| Resource | Action | Cost |
|----------|--------|------|
| ACR (Standard) | KEEP | $13/mo |
| Everything else | DELETE | $0 |
| **Total** | | **$13/mo** |

**Best for:** Maximum savings, team runs all demos locally.

---

### Option B: Shared Demo Database ($28/month)

Keep ACR + downsized PostgreSQL for shared demo data.

| Resource | Action | Cost |
|----------|--------|------|
| ACR (Standard) | KEEP | $13/mo |
| PostgreSQL (B1ms) | KEEP (downsize) | $15/mo |
| Everything else | DELETE | $0 |
| **Total** | | **$28/mo** |

**Best for:** Team shares pre-loaded demo data in cloud database.

---

### PostgreSQL Sizing Options

| Tier | SKU | vCore | RAM | Cost |
|------|-----|-------|-----|------|
| Burstable | B1ms | 1 | 2 GB | ~$15/mo |
| Burstable | B2s | 2 | 4 GB | ~$30/mo |
| Burstable | B2ms | 2 | 8 GB | ~$40/mo |
| General Purpose | Ddsv5 (current) | 2 | 8 GB | ~$91/mo |

---

## 6. Cleanup Commands

### Delete Unused Resources

```powershell
# Delete API Management (saves $30.40/month)
az apim delete --name apim-intellioptics --resource-group IntelliOptics --yes

# Delete AKS cluster (saves $46.30/month)
az aks delete --name intellioptics --resource-group IntelliOptics --yes --no-wait

# Delete Container Apps (saves $144.21/month)
az containerapp delete --name intellioptics-api-37558 --resource-group IntelliOptics --yes
az containerapp delete --name io-worker --resource-group IntelliOptics --yes

# Delete App Service Plans (saves $15.71/month)
az appservice plan delete --name asp-intellioptics-linux --resource-group IntelliOptics --yes
az appservice plan delete --name plan-intellioptics-api --resource-group IntelliOptics --yes

# Optional: Delete PostgreSQL if not keeping (saves $91.38/month)
az postgres flexible-server delete --name pg-intellioptics --resource-group IntelliOptics --yes

# Optional: Delete Service Bus if not needed
az servicebus namespace delete --name sb-intellioptics --resource-group IntelliOptics --yes
```

### Downsize PostgreSQL (if keeping)

```powershell
az postgres flexible-server update \
  --name pg-intellioptics \
  --resource-group IntelliOptics \
  --sku-name Standard_B1ms \
  --tier Burstable
```

---

## 7. When to Scale Up

### Run Container Apps When:

| Scenario | Action |
|----------|--------|
| Paying customer signs | Deploy full cloud infrastructure |
| Edge devices deployed | Edge needs central cloud endpoint |
| Public URL required | Remote access needed |

### Don't Run Container Apps When:

| Scenario | Alternative |
|----------|-------------|
| Internal demos | Run locally with Docker |
| In-person investor meetings | Run locally on laptop |
| Development/testing | Run locally |
| No paying customers | Nothing to serve |

### Simple Decision Rule

```
Paying customer?
    │
    ├── NO  → Local Docker demos ($13-28/mo)
    │
    └── YES → Deploy to Azure (~$150-200/mo)
```

---

## 8. Production Deployment

When ready to deploy for a paying customer, use the deployment script:

```powershell
cd "C:\dev\IntelliOptics 2.0\install"
.\deploy-azure.ps1
```

This provisions:
- PostgreSQL Flexible Server
- Storage Account + Blob Containers
- Service Bus + Queues
- Container Apps Environment
- Backend, Frontend, Worker containers

**Deployment time:** ~15-20 minutes

---

## 9. Cost Comparison Summary

| Scenario | Monthly | Annual |
|----------|---------|--------|
| Current (all resources) | $342 | $4,104 |
| Option A: ACR only | $13 | $156 |
| Option B: ACR + PostgreSQL | $28 | $336 |
| Production (with customer) | $150-200 | $1,800-2,400 |

### Savings

| From → To | Monthly Savings | Annual Savings |
|-----------|-----------------|----------------|
| Current → Option A | $329 | $3,948 |
| Current → Option B | $314 | $3,768 |

---

## 10. Files Reference

| File | Purpose |
|------|---------|
| `install/docker-compose.prod.yml` | Local demo deployment |
| `install/install-windows.ps1` | Automated local setup |
| `install/deploy-azure.ps1` | Production Azure deployment |
| `install/.env.template` | Environment configuration |
| `install/README.md` | Installation guide |

---

## 11. Resource Inventory (Post-Optimization)

### Keep

| Resource | Name | Cost |
|----------|------|------|
| Container Registry | acrintellioptics | $13/mo |
| PostgreSQL (optional) | pg-intellioptics | $15/mo |
| Storage Account | stintelliopticsprod | ~$0.10/mo |
| Key Vault | kv-intellioptics | ~$0/mo |

### Delete

| Resource | Name | Savings |
|----------|------|---------|
| API Management | apim-intellioptics | $30/mo |
| AKS | intellioptics | $46/mo |
| Container Apps | intellioptics-api-37558 | $96/mo |
| Container Apps | io-worker | $48/mo |
| App Service Plan | asp-intellioptics-linux | $8/mo |
| App Service Plan | plan-intellioptics-api | $8/mo |

---

## Contact

For questions about Azure resources or deployment, contact the DevOps team.

---

*Document generated: January 20, 2026*
