#Requires -Version 5.1
<#
.SYNOPSIS
    IntelliOptics 2.5 Production Installer

.DESCRIPTION
    Installs the full IntelliOptics stack (cloud + edge) on a Windows Server
    with Docker Desktop. Checks prerequisites, configures environment,
    builds images, starts services, and creates the admin user.

.EXAMPLE
    .\Install-IntelliOptics.ps1
    .\Install-IntelliOptics.ps1 -SkipBuild   # Use existing images
    .\Install-IntelliOptics.ps1 -NoCache      # Force rebuild from scratch
#>

param(
    [switch]$SkipBuild,
    [switch]$NoCache,
    [switch]$SkipHealthCheck
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# ── Banner ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Blue
Write-Host "    IntelliOptics 2.5 - Production Installer" -ForegroundColor White
Write-Host "    Edge-First AI Inspection Platform" -ForegroundColor Gray
Write-Host "    4wardmotion Solutions, Inc." -ForegroundColor Gray
Write-Host "  ================================================================" -ForegroundColor Blue
Write-Host ""

# ── Step 0: Detect and stop old IntelliOptics 2.0 ─────────────────────
$oldContainers = docker ps --filter "name=intellioptics-cloud-" --filter "name=intellioptics-edge-" --filter "name=intellioptics-inference" -q 2>$null
if ($oldContainers) {
    Write-Host "  Detected running IntelliOptics 2.0 containers:" -ForegroundColor Yellow
    docker ps --filter "name=intellioptics-cloud-" --filter "name=intellioptics-edge-" --filter "name=intellioptics-inference" --format "    {{.Names}}  ({{.Status}})" 2>$null
    Write-Host ""
    Write-Host "  These must be stopped to free ports 80 and 30101." -ForegroundColor Yellow
    $stop = Read-Host "  Stop old 2.0 containers now? (Y/n)"
    if ($stop -eq "n" -or $stop -eq "N") {
        Write-Host "  Cannot continue with old containers running. Exiting." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Stopping old containers..." -ForegroundColor Cyan
    docker stop $oldContainers 2>$null | Out-Null
    docker rm $oldContainers 2>$null | Out-Null
    Write-Host "  Old 2.0 containers stopped and removed." -ForegroundColor Green
    Write-Host ""
}

# ── Step 1: Prerequisites ──────────────────────────────────────────────
Write-Host "Step 1/6: Checking prerequisites..." -ForegroundColor White
& "$ScriptDir\scripts\Test-Prerequisites.ps1"
if ($LASTEXITCODE -ne 0) { exit 1 }

# ── Step 2: Environment ───────────────────────────────────────────────
Write-Host "`nStep 2/6: Configuring environment..." -ForegroundColor White
& "$ScriptDir\scripts\Initialize-Environment.ps1"
if ($LASTEXITCODE -ne 0) { exit 1 }

# ── Step 3: Build ─────────────────────────────────────────────────────
if (-not $SkipBuild) {
    Write-Host "`nStep 3/6: Building Docker images..." -ForegroundColor White
    $buildParams = @{ ComposeFile = "docker-compose.prod.yml" }
    if ($NoCache) { $buildParams.NoCache = $true }
    & "$ScriptDir\scripts\Build-Images.ps1" @buildParams
    if ($LASTEXITCODE -ne 0) { exit 1 }
} else {
    Write-Host "`nStep 3/6: Skipping build (using existing images)." -ForegroundColor Yellow
}

# ── Step 4: Start ─────────────────────────────────────────────────────
Write-Host "`nStep 4/6: Starting services..." -ForegroundColor White
& "$ScriptDir\scripts\Start-Services.ps1" -ComposeFile "docker-compose.prod.yml"
if ($LASTEXITCODE -ne 0) { exit 1 }

# ── Step 5: Health Check ──────────────────────────────────────────────
if (-not $SkipHealthCheck) {
    Write-Host "`nStep 5/6: Running health checks..." -ForegroundColor White
    & "$ScriptDir\scripts\Test-Health.ps1" -ComposeFile "docker-compose.prod.yml"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n  Services started but not all are healthy yet." -ForegroundColor Yellow
        Write-Host "  This is normal if models are still loading (can take 1-2 minutes)." -ForegroundColor Yellow
        Write-Host "  Check status: docker compose -f docker-compose.prod.yml ps" -ForegroundColor Gray
    }
} else {
    Write-Host "`nStep 5/6: Skipping health check." -ForegroundColor Yellow
}

# ── Step 6: Admin User ────────────────────────────────────────────────
Write-Host "`nStep 6/6: Creating admin user..." -ForegroundColor White
& "$ScriptDir\scripts\Create-AdminUser.ps1"

# ── Done ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Green
Write-Host "    IntelliOptics 2.5 installed successfully!" -ForegroundColor Green
Write-Host "  ================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend:  http://localhost/" -ForegroundColor White
Write-Host "  Edge API:  http://localhost:30101/" -ForegroundColor White
Write-Host "  Backend:   http://localhost/api/health" -ForegroundColor White
Write-Host ""
Write-Host "  Login:     admin@intellioptics.com / admin123" -ForegroundColor White
Write-Host "             (change password after first login)" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Useful commands:" -ForegroundColor Gray
Write-Host "    docker compose -f docker-compose.prod.yml ps       # Status" -ForegroundColor Gray
Write-Host "    docker compose -f docker-compose.prod.yml logs -f  # Logs" -ForegroundColor Gray
Write-Host "    .\scripts\Stop-Services.ps1                        # Stop" -ForegroundColor Gray
Write-Host ""
