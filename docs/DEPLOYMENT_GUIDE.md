# IntelliOptics 2.0 - Centralized SaaS Deployment Guide

This guide details the process for deploying the **IntelliOptics Central Hub** (the SaaS core) and onboarding **Distributed Clients** (Edge Hubs). 

---

## 1. The Architecture
*   **Central Hub (Azure):** A single multi-tenant infrastructure hosting the API, Frontend, and Global Database.
*   **Edge Hubs (Client Sites):** Standardized, "stock" hardware/software packages installed at client locations that dial home to the Central Hub.

---

## Part A: Central Hub Deployment (Platform Owner Only)
*You only do this ONCE to set up the entire platform infrastructure.*

### 1. Provision Central Resources (Azure)
Run these commands once to create the shared platform infrastructure.

```bash
# 1. Resource Group
az group create --name "rg-intellioptics-central" --location "eastus"

# 2. Shared Registry (For Distributing Stock Builds)
az acr create \
  --resource-group "rg-intellioptics-central" \
  --name "acrintellioptics" \
  --sku Basic \
  --admin-enabled true

# 3. Global Database (Multi-tenant)
# This one database server handles all organizations via row-level isolation.
az postgres flexible-server create \
  --resource-group "rg-intellioptics-central" \
  --name "psql-intellioptics-central" \
  --database-name "intellioptics" \
  --admin-user "ioadmin" \
  --admin-password "YourSecurePassword123!"

# 4. Central API & Frontend
# Deploy the Backend and Worker to Azure Container Apps
# Deploy the Frontend to Azure Static Web Apps
```

### 2. Publish Stock Images
Build and push the images once to your central registry. These are the "Stock Builds" pulled by every client edge device.
```bash
# Edge API
docker build -t acrintellioptics.azurecr.io/edge-api:stable ./edge/edge-api
docker push acrintellioptics.azurecr.io/edge-api:stable

# Inference Engine
docker build -t acrintellioptics.azurecr.io/inference:stable ./edge/inference
docker push acrintellioptics.azurecr.io/inference:stable
```

---

## Part B: Onboarding a New Client (Site Deployment)
*Follow these steps for every new site/customer. No new Azure resources required.*

### 1. Register Client in Central Hub
1.  Log into your **Central Admin Dashboard**.
2.  Navigate to **Admin > Organizations**.
3.  Click **"Add New Client"**.
    *   Name: "Acme Corp - Warehouse A"
4.  The system will generate a unique **INTELLIOPTICS_API_TOKEN**. **Copy this.**

### 2. Edge Installation (The "Stock" Deployment)
*Perform this on the hardware (Jetson/PC) at the client's physical location.*

1.  **Prepare the Environment**:
    Ensure Docker and the NVIDIA Container Toolkit are installed on the device.

2.  **Download the Deployment Bundle**:
    The client only needs the `docker-compose.yml` and a `.env` file.
    ```bash
mkdir intellioptics && cd intellioptics
# (Optional) Curl these from your public/private distribution point
curl -O https://your-dist-site.com/stock/docker-compose.yml
```

3.  **Apply Client Customization**:
    Create a `.env` file to link this stock install to the Central Hub.
    ```bash
nano .env
```
    **Required entries:**
    *   `UPSTREAM_CLOUD_API`: `https://api.intellioptics.io` (Your Central Hub URL)
    *   `INTELLIOPTICS_API_TOKEN`: `eyJhbGci...` (The token you copied in Step 1)
    *   `HUB_NAME`: `Warehouse-A-South`

4.  **Launch the Services**:
    ```bash
    # This pulls the 'stable' stock images from your central registry
    docker compose up -d
    ```

---

## Part C: Management & Updates

### 1. Centralized Updates
To push a software update to **all** clients:
1.  Update the code in the repository.
2.  Build and push a new image with the `:stable` tag to your Central ACR.
3.  Client Hubs will receive the update the next time they restart or run `docker compose pull`.

### 2. Remote Configuration
Once an Edge Hub is connected, all camera configurations, detector assignments, and alert thresholds are managed **remotely** via the Central Hub UI. There is no need to visit the client site for configuration changes.

---

## Part D: Estimated Time per Client
*   **Administrative Onboarding:** 2 Minutes (Creating the Org and Token).
*   **On-Site Installation:** 15-20 Minutes (Primarily Docker pull time).
*   **Total Time to "Live":** Under 30 minutes per site.