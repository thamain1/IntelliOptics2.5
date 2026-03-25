# IntelliOptics 2.0 - Migration & Launch Plan

**Objective**: Initialize a new version-controlled repository from the local development build and deploy the full SaaS stack (Cloud + 2.0 Edge) to Azure.

**Date**: January 13, 2026
**Source Directory**: `C:\dev\IntelliOptics 2.0`

---

## Phase 1: Repository Initialization
*Goal: Secure the local code into a clean Git history.*

1.  **Prepare the Directory**
    *   Open terminal in `C:\dev\IntelliOptics 2.0`.
    *   Verify `.gitignore` protects secrets (Checked: `.env`, `__pycache__`, `node_modules` are ignored).

2.  **Initialize Git**
    ```bash
    cd "C:\dev\IntelliOptics 2.0"
    git init
    git branch -M main
    ```

3.  **First Commit**
    ```bash
    git add .
    git commit -m "Initial commit: IntelliOptics 2.0 Cloud & Edge Architecture"
    ```

4.  **Push to New Remote**
    *   *Prerequisite*: Create a new empty repository on GitHub/Azure DevOps/GitLab.
    ```bash
    git remote add origin <NEW_REPO_URL>
    git push -u origin main
    ```

---

## Phase 2: Central Cloud Infrastructure (Azure)
*Goal: Provision the shared resources for the SaaS hub.*

**1. Set Variables (PowerShell)**
```powershell
$RG = "rg-intellioptics-central"
$LOC = "eastus"
$ACR = "acrintellioptics" + (Get-Random -Minimum 1000 -Maximum 9999)
$DB = "psql-intellioptics-central" + (Get-Random -Minimum 1000 -Maximum 9999)
```

**2. Execute Provisioning Commands**
```powershell
# Resource Group
az group create --name $RG --location $LOC

# Container Registry
az acr create --resource-group $RG --name $ACR --sku Basic --admin-enabled true

# PostgreSQL (Flexible Server)
az postgres flexible-server create --resource-group $RG --name $DB --location $LOC --admin-user "ioadmin" --admin-password "Start123!Strong" --sku-name Standard_B1ms --tier Burstable --version 13 --storage-size 32

# Allow Azure Services to access DB
az postgres flexible-server firewall-rule create --resource-group $RG --name "$DB-allow-azure" --rule-name "AllowAzureServices" --server-name $DB --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0

# Service Bus
az servicebus namespace create --resource-group $RG --name ("sb-intellioptics-" + (Get-Random)) --location $LOC --sku Standard

# Storage Account
az storage account create --name ("stio" + (Get-Random)) --resource-group $RG --location $LOC --sku Standard_LRS
```

---

## Phase 3: Build & Publish Containers
*Goal: Push the "Cloud" and "Stock Edge" images to the registry.*

**1. Login**
```powershell
az acr login --name $ACR
```

**2. Build & Push Cloud Backend**
```powershell
docker build -t "$ACR.azurecr.io/backend:latest" -f cloud/backend/Dockerfile cloud/backend
docker push "$ACR.azurecr.io/backend:latest"
```

**3. Build & Push Cloud Worker**
```powershell
docker build -t "$ACR.azurecr.io/worker:latest" -f cloud/worker/Dockerfile cloud/worker
docker push "$ACR.azurecr.io/worker:latest"
```

**4. Build & Push Stock Edge Components (IntelliOptics 2.0 Edge)**
```powershell
# Edge API
docker build -t "$ACR.azurecr.io/edge-api:stable" -f edge/edge-api/Dockerfile edge/edge-api
docker push "$ACR.azurecr.io/edge-api:stable"

# Inference Engine
docker build -t "$ACR.azurecr.io/inference:stable" -f edge/inference/Dockerfile edge/inference
docker push "$ACR.azurecr.io/inference:stable"
```

---

## Phase 4: Deploy Cloud Services
*Goal: Launch the Central Hub.*

**1. Create Container App Environment**
```powershell
az containerapp env create --name "cae-intellioptics" --resource-group $RG --location $LOC
```

**2. Deploy Backend API**
```powershell
# Retrieve Secrets for Env Vars first
$DbConn = "postgresql://ioadmin:Start123!Strong@$DB.postgres.database.azure.com:5432/intellioptics"
# ... (Get ServiceBus & Storage connection strings via Azure Portal or CLI)

az containerapp create --name "ca-backend" --resource-group $RG --environment "cae-intellioptics" `
  --image "$ACR.azurecr.io/backend:latest" --target-port 8000 --ingress external `
  --registry-server "$ACR.azurecr.io" --env-vars DATABASE_URL=$DbConn ...
```

**3. Deploy Frontend (Static Web App)**
```powershell
cd cloud/frontend
az staticwebapp create --name "swa-intellioptics" --resource-group $RG --location "eastus2" --source . --output-location "dist" --app-location "."
```

---

## Phase 5: "IntelliOptics 2.0 Edge" Distribution
*Goal: Verify the new edge package is ready for clients.*

1.  **Verify Images**: Ensure `edge-api:stable` and `inference:stable` are in the ACR repository.
2.  **Package Installer**:
    *   The `edge/` directory in the repo *is* the installer.
    *   Clients will download `docker-compose.yml` and `.env.template` from the raw Git URL of the new repo.
3.  **Test Deployment**:
    *   On a local test machine (simulate a client), create a `.env` file pointing to the new Azure Backend URL.
    *   Run `docker compose up`.
    *   Confirm it registers as a Hub in the Azure Dashboard.

---

## Next Actions
1.  **Execute Phase 1** immediately to secure the code.
2.  **Execute Phase 2 & 3** to stand up the environment.
3.  **Update `DEPLOYMENT_GUIDE.md`** with the actual URLs and ACR names generated during this process.
