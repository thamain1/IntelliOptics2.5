# IntelliOptics 2.0 - Azure Deployment Script
# Version: v2.0.0
# This script provisions all Azure resources and deploys the centralized web application

param(
    [string]$ResourceGroup = "rg-intellioptics-prod",
    [string]$Location = "eastus",
    [string]$Environment = "prod"
)

# ============================================
# CONFIGURATION
# ============================================
$ACR_NAME = "acrintellioptics"
$ACR_URL = "$ACR_NAME.azurecr.io"
$IMAGE_TAG = "v2.0.0"

# Resource names
$POSTGRES_SERVER = "psql-intellioptics-$Environment"
$STORAGE_ACCOUNT = "stintellioptics$Environment"
$SERVICE_BUS = "sb-intellioptics-$Environment"
$CONTAINER_ENV = "intellioptics-env-$Environment"

# ============================================
# HELPER FUNCTIONS
# ============================================
function Write-Step {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Yellow
}

function Test-CommandExists {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# ============================================
# PREREQUISITES CHECK
# ============================================
Write-Step "Checking Prerequisites"

if (-not (Test-CommandExists "az")) {
    Write-Host "[ERROR] Azure CLI not found. Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Red
    exit 1
}
Write-Success "Azure CLI found"

# Check Azure login
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Info "Not logged in to Azure. Initiating login..."
    az login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Azure login failed" -ForegroundColor Red
        exit 1
    }
}
Write-Success "Logged in as: $($account.user.name)"

# ============================================
# COLLECT CREDENTIALS
# ============================================
Write-Step "Collecting Configuration"

$POSTGRES_ADMIN = "intellioptics"
$POSTGRES_PASSWORD = Read-Host "Enter PostgreSQL admin password (min 8 chars, mixed case, numbers)" -AsSecureString
$POSTGRES_PASSWORD_PLAIN = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($POSTGRES_PASSWORD))

$API_SECRET_KEY = Read-Host "Enter API secret key (32+ characters)" -AsSecureString
$API_SECRET_KEY_PLAIN = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($API_SECRET_KEY))

if ($API_SECRET_KEY_PLAIN.Length -lt 32) {
    Write-Host "[ERROR] API secret key must be at least 32 characters" -ForegroundColor Red
    exit 1
}

# ============================================
# STEP 1: CREATE RESOURCE GROUP
# ============================================
Write-Step "Step 1: Creating Resource Group"

az group create `
    --name $ResourceGroup `
    --location $Location `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Resource group '$ResourceGroup' created in '$Location'"
} else {
    Write-Host "[ERROR] Failed to create resource group" -ForegroundColor Red
    exit 1
}

# ============================================
# STEP 2: CREATE POSTGRESQL FLEXIBLE SERVER
# ============================================
Write-Step "Step 2: Creating PostgreSQL Flexible Server"

Write-Info "This may take 5-10 minutes..."

az postgres flexible-server create `
    --name $POSTGRES_SERVER `
    --resource-group $ResourceGroup `
    --location $Location `
    --admin-user $POSTGRES_ADMIN `
    --admin-password $POSTGRES_PASSWORD_PLAIN `
    --sku-name Standard_B1ms `
    --tier Burstable `
    --storage-size 32 `
    --version 15 `
    --yes `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "PostgreSQL server '$POSTGRES_SERVER' created"
} else {
    Write-Host "[ERROR] Failed to create PostgreSQL server" -ForegroundColor Red
    exit 1
}

# Create database
Write-Info "Creating database 'intellioptics'..."
az postgres flexible-server db create `
    --resource-group $ResourceGroup `
    --server-name $POSTGRES_SERVER `
    --database-name intellioptics `
    --output none

Write-Success "Database 'intellioptics' created"

# Configure firewall to allow Azure services
Write-Info "Configuring firewall rules..."
az postgres flexible-server firewall-rule create `
    --resource-group $ResourceGroup `
    --name $POSTGRES_SERVER `
    --rule-name AllowAzureServices `
    --start-ip-address 0.0.0.0 `
    --end-ip-address 0.0.0.0 `
    --output none

Write-Success "Firewall configured for Azure services"

# Build connection string
$POSTGRES_DSN = "postgresql://${POSTGRES_ADMIN}:${POSTGRES_PASSWORD_PLAIN}@${POSTGRES_SERVER}.postgres.database.azure.com:5432/intellioptics?sslmode=require"

# ============================================
# STEP 3: CREATE STORAGE ACCOUNT
# ============================================
Write-Step "Step 3: Creating Storage Account"

az storage account create `
    --name $STORAGE_ACCOUNT `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku Standard_LRS `
    --kind StorageV2 `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Storage account '$STORAGE_ACCOUNT' created"
} else {
    Write-Host "[ERROR] Failed to create storage account" -ForegroundColor Red
    exit 1
}

# Get connection string
$STORAGE_CONNECTION = az storage account show-connection-string `
    --name $STORAGE_ACCOUNT `
    --resource-group $ResourceGroup `
    --query connectionString `
    --output tsv

# Create blob containers
Write-Info "Creating blob containers..."
$containers = @("intellioptics-images", "intellioptics-models", "intellioptics-training")

foreach ($container in $containers) {
    az storage container create `
        --name $container `
        --connection-string $STORAGE_CONNECTION `
        --output none
    Write-Success "Container '$container' created"
}

# ============================================
# STEP 4: CREATE SERVICE BUS
# ============================================
Write-Step "Step 4: Creating Service Bus Namespace"

az servicebus namespace create `
    --name $SERVICE_BUS `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku Standard `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Service Bus namespace '$SERVICE_BUS' created"
} else {
    Write-Host "[ERROR] Failed to create Service Bus" -ForegroundColor Red
    exit 1
}

# Create queues
Write-Info "Creating Service Bus queues..."
$queues = @("image-queries", "inference-results", "image-escalations", "fallback-jobs")

foreach ($queue in $queues) {
    az servicebus queue create `
        --name $queue `
        --namespace-name $SERVICE_BUS `
        --resource-group $ResourceGroup `
        --output none
    Write-Success "Queue '$queue' created"
}

# Get connection string
$SERVICE_BUS_CONN = az servicebus namespace authorization-rule keys list `
    --resource-group $ResourceGroup `
    --namespace-name $SERVICE_BUS `
    --name RootManageSharedAccessKey `
    --query primaryConnectionString `
    --output tsv

# ============================================
# STEP 5: CREATE CONTAINER APPS ENVIRONMENT
# ============================================
Write-Step "Step 5: Creating Container Apps Environment"

# Install/update containerapp extension
az extension add --name containerapp --upgrade --yes 2>$null

az containerapp env create `
    --name $CONTAINER_ENV `
    --resource-group $ResourceGroup `
    --location $Location `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Container Apps environment '$CONTAINER_ENV' created"
} else {
    Write-Host "[ERROR] Failed to create Container Apps environment" -ForegroundColor Red
    exit 1
}

# ============================================
# STEP 6: CONFIGURE ACR ACCESS
# ============================================
Write-Step "Step 6: Configuring ACR Access"

# Get ACR credentials
$ACR_USERNAME = az acr credential show --name $ACR_NAME --query username --output tsv
$ACR_PASSWORD = az acr credential show --name $ACR_NAME --query "passwords[0].value" --output tsv

Write-Success "ACR credentials retrieved"

# ============================================
# STEP 7: DEPLOY BACKEND
# ============================================
Write-Step "Step 7: Deploying Backend Service"

az containerapp create `
    --name backend `
    --resource-group $ResourceGroup `
    --environment $CONTAINER_ENV `
    --image "$ACR_URL/intellioptics/backend:$IMAGE_TAG" `
    --target-port 8000 `
    --ingress external `
    --registry-server $ACR_URL `
    --registry-username $ACR_USERNAME `
    --registry-password $ACR_PASSWORD `
    --cpu 1.0 `
    --memory 2.0Gi `
    --min-replicas 1 `
    --max-replicas 3 `
    --env-vars `
        "POSTGRES_DSN=$POSTGRES_DSN" `
        "AZURE_STORAGE_CONNECTION_STRING=$STORAGE_CONNECTION" `
        "API_SECRET_KEY=$API_SECRET_KEY_PLAIN" `
        "SERVICE_BUS_CONN=$SERVICE_BUS_CONN" `
        "BLOB_CONTAINER_NAME=intellioptics-images" `
        "APP_ENV=production" `
        "LOG_LEVEL=INFO" `
    --output none

if ($LASTEXITCODE -eq 0) {
    $BACKEND_URL = az containerapp show --name backend --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" --output tsv
    Write-Success "Backend deployed: https://$BACKEND_URL"
} else {
    Write-Host "[ERROR] Failed to deploy backend" -ForegroundColor Red
    exit 1
}

# ============================================
# STEP 8: DEPLOY FRONTEND
# ============================================
Write-Step "Step 8: Deploying Frontend Service"

az containerapp create `
    --name frontend `
    --resource-group $ResourceGroup `
    --environment $CONTAINER_ENV `
    --image "$ACR_URL/intellioptics/frontend:$IMAGE_TAG" `
    --target-port 3000 `
    --ingress external `
    --registry-server $ACR_URL `
    --registry-username $ACR_USERNAME `
    --registry-password $ACR_PASSWORD `
    --cpu 0.5 `
    --memory 1.0Gi `
    --min-replicas 1 `
    --max-replicas 3 `
    --env-vars `
        "REACT_APP_API_URL=https://$BACKEND_URL" `
    --output none

if ($LASTEXITCODE -eq 0) {
    $FRONTEND_URL = az containerapp show --name frontend --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" --output tsv
    Write-Success "Frontend deployed: https://$FRONTEND_URL"
} else {
    Write-Host "[ERROR] Failed to deploy frontend" -ForegroundColor Red
    exit 1
}

# ============================================
# STEP 9: DEPLOY WORKER
# ============================================
Write-Step "Step 9: Deploying Worker Service"

az containerapp create `
    --name worker `
    --resource-group $ResourceGroup `
    --environment $CONTAINER_ENV `
    --image "$ACR_URL/intellioptics/worker:$IMAGE_TAG" `
    --registry-server $ACR_URL `
    --registry-username $ACR_USERNAME `
    --registry-password $ACR_PASSWORD `
    --cpu 2.0 `
    --memory 4.0Gi `
    --min-replicas 1 `
    --max-replicas 5 `
    --env-vars `
        "POSTGRES_DSN=$POSTGRES_DSN" `
        "AZURE_STORAGE_CONNECTION_STRING=$STORAGE_CONNECTION" `
        "SERVICE_BUS_CONN=$SERVICE_BUS_CONN" `
        "BLOB_CONTAINER_NAME=intellioptics-images" `
        "MODEL_CONTAINER_NAME=intellioptics-models" `
        "WORKER_CONCURRENCY=4" `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Worker deployed (no public ingress - internal only)"
} else {
    Write-Host "[ERROR] Failed to deploy worker" -ForegroundColor Red
    exit 1
}

# ============================================
# DEPLOYMENT SUMMARY
# ============================================
Write-Step "Deployment Complete!"

Write-Host "`nResource Group: $ResourceGroup" -ForegroundColor White
Write-Host "Location: $Location`n" -ForegroundColor White

Write-Host "SERVICES DEPLOYED:" -ForegroundColor Green
Write-Host "  PostgreSQL Server: $POSTGRES_SERVER.postgres.database.azure.com" -ForegroundColor White
Write-Host "  Storage Account:   $STORAGE_ACCOUNT" -ForegroundColor White
Write-Host "  Service Bus:       $SERVICE_BUS.servicebus.windows.net" -ForegroundColor White
Write-Host ""
Write-Host "APPLICATION URLs:" -ForegroundColor Green
Write-Host "  Frontend:  https://$FRONTEND_URL" -ForegroundColor White
Write-Host "  Backend:   https://$BACKEND_URL" -ForegroundColor White
Write-Host "  API Docs:  https://$BACKEND_URL/docs" -ForegroundColor White
Write-Host ""

# Save configuration to file
$configFile = "azure-deployment-$Environment.txt"
@"
# IntelliOptics 2.0 - Azure Deployment Configuration
# Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Environment: $Environment

## Resource Group
RESOURCE_GROUP=$ResourceGroup
LOCATION=$Location

## PostgreSQL
POSTGRES_SERVER=$POSTGRES_SERVER.postgres.database.azure.com
POSTGRES_USER=$POSTGRES_ADMIN
POSTGRES_DB=intellioptics

## Storage
STORAGE_ACCOUNT=$STORAGE_ACCOUNT

## Service Bus
SERVICE_BUS=$SERVICE_BUS.servicebus.windows.net

## Application URLs
FRONTEND_URL=https://$FRONTEND_URL
BACKEND_URL=https://$BACKEND_URL
API_DOCS_URL=https://$BACKEND_URL/docs

## Container Apps
CONTAINER_ENVIRONMENT=$CONTAINER_ENV

## Notes
- Passwords and connection strings are NOT stored in this file
- Use Azure Key Vault for production secrets management
- Configure custom domain and SSL in Azure Portal
"@ | Out-File -FilePath $configFile -Encoding UTF8

Write-Info "Configuration saved to: $configFile"
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Open https://$FRONTEND_URL in your browser" -ForegroundColor White
Write-Host "  2. Create your first admin user" -ForegroundColor White
Write-Host "  3. Configure custom domain (optional)" -ForegroundColor White
Write-Host "  4. Set up Azure Key Vault for secrets (recommended)" -ForegroundColor White
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  az containerapp logs show --name backend --resource-group $ResourceGroup --follow" -ForegroundColor Gray
Write-Host ""
