# IntelliOptics 2.0 - Windows Installation Script
# Version: v2.0.0
# Usage: Run as Administrator in PowerShell

param(
    [switch]$SkipPrerequisites,
    [switch]$SkipEnvSetup
)

$ErrorActionPreference = "Stop"
$ACR_NAME = "acrintellioptics"
$VERSION = "v2.0.0"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  IntelliOptics 2.0 Installation Script" -ForegroundColor Cyan
Write-Host "  Version: $VERSION" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
function Test-Prerequisites {
    Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Yellow

    # Check Docker
    try {
        $dockerVersion = docker --version
        Write-Host "  [OK] Docker: $dockerVersion" -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Docker is not installed or not running" -ForegroundColor Red
        Write-Host "  Please install Docker Desktop from https://www.docker.com/products/docker-desktop" -ForegroundColor Red
        exit 1
    }

    # Check Docker Compose
    try {
        $composeVersion = docker compose version
        Write-Host "  [OK] Docker Compose: $composeVersion" -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Docker Compose is not available" -ForegroundColor Red
        exit 1
    }

    # Check Azure CLI
    try {
        $azVersion = az --version | Select-Object -First 1
        Write-Host "  [OK] Azure CLI: $azVersion" -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Azure CLI is not installed" -ForegroundColor Red
        Write-Host "  Please install from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli-windows" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
}

# Login to ACR
function Connect-ACR {
    Write-Host "[2/5] Logging in to Azure Container Registry..." -ForegroundColor Yellow

    try {
        az acr login --name $ACR_NAME
        Write-Host "  [OK] Logged in to $ACR_NAME.azurecr.io" -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Failed to login to ACR" -ForegroundColor Red
        Write-Host "  Make sure you are logged in to Azure (run 'az login' first)" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
}

# Pull images
function Get-Images {
    Write-Host "[3/5] Pulling images from ACR (this may take a while)..." -ForegroundColor Yellow

    $images = @(
        "$ACR_NAME.azurecr.io/intellioptics/backend:$VERSION",
        "$ACR_NAME.azurecr.io/intellioptics/frontend:$VERSION",
        "$ACR_NAME.azurecr.io/intellioptics/worker:$VERSION"
    )

    foreach ($image in $images) {
        Write-Host "  Pulling $image..." -ForegroundColor Gray
        docker pull $image
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [ERROR] Failed to pull $image" -ForegroundColor Red
            exit 1
        }
        Write-Host "  [OK] $image" -ForegroundColor Green
    }

    # Also pull postgres and nginx
    Write-Host "  Pulling postgres:15-alpine..." -ForegroundColor Gray
    docker pull postgres:15-alpine
    Write-Host "  Pulling nginx:1.25-alpine..." -ForegroundColor Gray
    docker pull nginx:1.25-alpine

    Write-Host ""
}

# Setup environment
function Set-Environment {
    Write-Host "[4/5] Setting up environment..." -ForegroundColor Yellow

    if (Test-Path ".env") {
        Write-Host "  [INFO] .env file already exists" -ForegroundColor Yellow
        $overwrite = Read-Host "  Overwrite? (y/N)"
        if ($overwrite -ne "y" -and $overwrite -ne "Y") {
            Write-Host "  [SKIP] Keeping existing .env file" -ForegroundColor Yellow
            return
        }
    }

    if (-not (Test-Path ".env.template")) {
        Write-Host "  [ERROR] .env.template not found" -ForegroundColor Red
        exit 1
    }

    Copy-Item ".env.template" ".env"
    Write-Host "  [OK] Created .env file from template" -ForegroundColor Green
    Write-Host ""
    Write-Host "  IMPORTANT: Edit .env file with your credentials before starting" -ForegroundColor Yellow
    Write-Host "  Required settings:" -ForegroundColor Yellow
    Write-Host "    - POSTGRES_PASSWORD" -ForegroundColor Gray
    Write-Host "    - AZURE_STORAGE_CONNECTION_STRING" -ForegroundColor Gray
    Write-Host "    - API_SECRET_KEY" -ForegroundColor Gray
    Write-Host ""
}

# Copy nginx config
function Copy-NginxConfig {
    if (-not (Test-Path "nginx.conf")) {
        if (Test-Path "../cloud/nginx/nginx.conf") {
            Copy-Item "../cloud/nginx/nginx.conf" "nginx.conf"
            Write-Host "  [OK] Copied nginx.conf" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] nginx.conf not found, using default" -ForegroundColor Yellow
        }
    }
}

# Start services
function Start-Services {
    Write-Host "[5/5] Starting services..." -ForegroundColor Yellow

    docker compose -f docker-compose.prod.yml up -d

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] Failed to start services" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "  Waiting for services to be healthy..." -ForegroundColor Gray
    Start-Sleep -Seconds 10

    # Check health
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 30
        if ($response.StatusCode -eq 200) {
            Write-Host "  [OK] Backend is healthy" -ForegroundColor Green
        }
    } catch {
        Write-Host "  [WARN] Backend health check failed (may still be starting)" -ForegroundColor Yellow
    }

    Write-Host ""
}

# Main
if (-not $SkipPrerequisites) {
    Test-Prerequisites
}

Connect-ACR
Get-Images

if (-not $SkipEnvSetup) {
    Set-Environment
}

Copy-NginxConfig

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Edit .env file with your credentials" -ForegroundColor White
Write-Host "  2. Run: docker compose -f docker-compose.prod.yml up -d" -ForegroundColor White
Write-Host "  3. Access the app at http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  View logs:    docker compose -f docker-compose.prod.yml logs -f" -ForegroundColor Gray
Write-Host "  Stop:         docker compose -f docker-compose.prod.yml down" -ForegroundColor Gray
Write-Host "  Restart:      docker compose -f docker-compose.prod.yml restart" -ForegroundColor Gray
Write-Host ""
