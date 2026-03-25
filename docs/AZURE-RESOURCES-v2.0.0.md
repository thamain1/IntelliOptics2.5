# IntelliOptics 2.0 - Azure Resources Inventory

**Date:** January 20, 2026
**Version:** v2.0.0
**Environment:** Production

---

## Overview

This document lists all Azure resources and third-party services used by IntelliOptics 2.0 production deployment.

---

## 1. Azure Container Registry (ACR)

| Property | Value |
|----------|-------|
| **Resource Type** | Azure Container Registry |
| **Name** | `acrintellioptics` |
| **URL** | `acrintellioptics.azurecr.io` |
| **SKU** | Standard (recommended) |
| **Purpose** | Store Docker images for cloud and edge deployment |

### Repositories
| Repository | Description |
|------------|-------------|
| `intellioptics/backend` | Cloud backend API |
| `intellioptics/frontend` | Cloud web frontend |
| `intellioptics/worker` | Cloud async worker |
| `intellioptics/edge-api` | Edge API service |
| `intellioptics/inference` | Edge inference service |

---

## 2. Azure Database for PostgreSQL

| Property | Value |
|----------|-------|
| **Resource Type** | Azure Database for PostgreSQL - Flexible Server |
| **Purpose** | Central database for detectors, queries, escalations, users |
| **SKU** | Burstable B1ms (dev) or General Purpose (prod) |
| **Version** | PostgreSQL 15 |

### Configuration
| Setting | Value |
|---------|-------|
| Database Name | `intellioptics` |
| Username | `intellioptics` |
| Port | 5432 |
| SSL Mode | Require (production) |

### Environment Variable
```
POSTGRES_DSN=postgresql://intellioptics:<password>@<server>.postgres.database.azure.com:5432/intellioptics?sslmode=require
```

---

## 3. Azure Blob Storage

| Property | Value |
|----------|-------|
| **Resource Type** | Azure Storage Account |
| **Purpose** | Store detection images, model files, training data |
| **SKU** | Standard LRS (dev) or Standard GRS (prod) |
| **Access Tier** | Hot |

### Containers
| Container | Purpose |
|-----------|---------|
| `intellioptics-images` | Detection query images |
| `intellioptics-models` | ONNX model files |
| `intellioptics-training` | Training export data |

### Environment Variable
```
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=<account>;AccountKey=<key>;EndpointSuffix=core.windows.net
```

---

## 4. Azure Service Bus

| Property | Value |
|----------|-------|
| **Resource Type** | Azure Service Bus Namespace |
| **Purpose** | Async message queuing for inference jobs and escalations |
| **SKU** | Basic or Standard |

### Queues
| Queue Name | Purpose |
|------------|---------|
| `image-queries` | Incoming inference requests |
| `inference-results` | Completed inference results |
| `image-escalations` | Escalated queries for human review |
| `fallback-jobs` | Cloud fallback processing |

### Environment Variable
```
SERVICE_BUS_CONN=Endpoint=sb://<namespace>.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=<key>
```

---

## 5. Azure Active Directory (Optional)

| Property | Value |
|----------|-------|
| **Resource Type** | Azure AD App Registration |
| **Purpose** | User authentication (SSO) |

### Configuration
| Setting | Description |
|---------|-------------|
| `AZURE_CLIENT_ID` | Application (client) ID |
| `AZURE_TENANT_ID` | Directory (tenant) ID |
| `AZURE_CLIENT_SECRET` | Client secret (if using confidential client) |

---

## 6. Azure Application Insights (Optional)

| Property | Value |
|----------|-------|
| **Resource Type** | Application Insights |
| **Purpose** | Application monitoring, logging, performance tracking |

### Environment Variable
```
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=<key>;IngestionEndpoint=https://<region>.in.applicationinsights.azure.com/
```

---

## 7. Third-Party Services

### SendGrid (Email Alerts)

| Property | Value |
|----------|-------|
| **Service** | SendGrid (Twilio) |
| **Purpose** | Email notifications for escalations and alerts |
| **URL** | https://app.sendgrid.com |

#### Configuration
| Setting | Description |
|---------|-------------|
| `SENDGRID_API_KEY` | API key from SendGrid dashboard |
| `SENDGRID_FROM_EMAIL` | Verified sender email address |

---

### Twilio (SMS Alerts)

| Property | Value |
|----------|-------|
| **Service** | Twilio |
| **Purpose** | SMS notifications for critical alerts |
| **URL** | https://www.twilio.com/console |

#### Configuration
| Setting | Description |
|---------|-------------|
| `TWILIO_ACCOUNT_SID` | Account SID |
| `TWILIO_AUTH_TOKEN` | Auth token |
| `TWILIO_PHONE_FROM` | Twilio phone number |

---

## 8. Resource Summary

### Required Resources
| Resource | Azure Service | Required |
|----------|--------------|----------|
| Container Registry | Azure Container Registry | ✅ Yes |
| Database | Azure PostgreSQL Flexible Server | ✅ Yes |
| Image Storage | Azure Blob Storage | ✅ Yes |
| Message Queue | Azure Service Bus | ✅ Yes |

### Optional Resources
| Resource | Azure Service | Required |
|----------|--------------|----------|
| Authentication | Azure Active Directory | ❌ Optional |
| Monitoring | Azure Application Insights | ❌ Optional |
| Email Alerts | SendGrid | ❌ Optional |
| SMS Alerts | Twilio | ❌ Optional |
| Caching | Azure Cache for Redis | ❌ Optional |

---

## 9. Estimated Monthly Costs

| Resource | SKU | Est. Cost/Month |
|----------|-----|-----------------|
| Container Registry | Standard | ~$20 |
| PostgreSQL Flexible | B1ms (1 vCore, 2GB) | ~$25 |
| PostgreSQL Flexible | D2s_v3 (2 vCore, 8GB) | ~$100 |
| Blob Storage | Standard LRS, 100GB | ~$5 |
| Service Bus | Standard | ~$10 |
| Application Insights | 5GB/month | ~$10 |
| **Total (Dev)** | | **~$70/month** |
| **Total (Prod)** | | **~$150-200/month** |

*Costs are estimates and vary by region and usage.*

---

## 10. Resource Provisioning Checklist

### Azure Portal Setup
- [ ] Create Resource Group: `rg-intellioptics-prod`
- [ ] Create Container Registry: `acrintellioptics`
- [ ] Create Storage Account: `stintelliopticsprod`
- [ ] Create PostgreSQL Flexible Server: `psql-intellioptics-prod`
- [ ] Create Service Bus Namespace: `sb-intellioptics-prod`
- [ ] Create Service Bus Queues (4 queues)
- [ ] Create Blob Containers (3 containers)
- [ ] Configure firewall rules for PostgreSQL
- [ ] Generate SAS tokens for blob access

### Optional Setup
- [ ] Create App Registration in Azure AD
- [ ] Create Application Insights resource
- [ ] Create SendGrid account and verify sender
- [ ] Create Twilio account and get phone number

---

## 11. Environment Variables Reference

### Required
```bash
# Database
POSTGRES_DSN=postgresql://intellioptics:<password>@<server>.postgres.database.azure.com:5432/intellioptics?sslmode=require

# Storage
AZURE_STORAGE_CONNECTION_STRING=<connection-string>
BLOB_CONTAINER_NAME=intellioptics-images
MODEL_CONTAINER_NAME=intellioptics-models

# Service Bus
SERVICE_BUS_CONN=<connection-string>

# Security
API_SECRET_KEY=<32-char-random-string>
```

### Optional
```bash
# Azure AD
AZURE_CLIENT_ID=<client-id>
AZURE_TENANT_ID=<tenant-id>

# SendGrid
SENDGRID_API_KEY=<api-key>
SENDGRID_FROM_EMAIL=alerts@yourdomain.com

# Twilio
TWILIO_ACCOUNT_SID=<account-sid>
TWILIO_AUTH_TOKEN=<auth-token>
TWILIO_PHONE_FROM=+1234567890

# Monitoring
APPLICATIONINSIGHTS_CONNECTION_STRING=<connection-string>
```

---

## 12. Architecture Diagram

```
                                    ┌─────────────────────────────────────┐
                                    │           AZURE CLOUD               │
                                    └─────────────────────────────────────┘
                                                     │
        ┌────────────────────────────────────────────┼────────────────────────────────────────────┐
        │                                            │                                            │
        ▼                                            ▼                                            ▼
┌───────────────┐                          ┌─────────────────┐                          ┌─────────────────┐
│  Azure ACR    │                          │  Azure Blob     │                          │  Azure Service  │
│               │                          │  Storage        │                          │  Bus            │
│ • backend     │                          │                 │                          │                 │
│ • frontend    │                          │ • images        │                          │ • image-queries │
│ • worker      │                          │ • models        │                          │ • results       │
│ • edge-api    │                          │ • training      │                          │ • escalations   │
│ • inference   │                          │                 │                          │                 │
└───────────────┘                          └─────────────────┘                          └─────────────────┘
        │                                            │                                            │
        │                                            │                                            │
        └────────────────────────────────────────────┼────────────────────────────────────────────┘
                                                     │
                                                     ▼
                                          ┌─────────────────┐
                                          │ Azure PostgreSQL│
                                          │ Flexible Server │
                                          │                 │
                                          │ • detectors     │
                                          │ • queries       │
                                          │ • users         │
                                          │ • escalations   │
                                          └─────────────────┘
                                                     │
                     ┌───────────────────────────────┼───────────────────────────────┐
                     │                               │                               │
                     ▼                               ▼                               ▼
            ┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
            │    SendGrid     │            │     Twilio      │            │   App Insights  │
            │  (Email Alerts) │            │  (SMS Alerts)   │            │  (Monitoring)   │
            └─────────────────┘            └─────────────────┘            └─────────────────┘
```

---

## Contact

For Azure resource access or provisioning requests, contact the DevOps team.
