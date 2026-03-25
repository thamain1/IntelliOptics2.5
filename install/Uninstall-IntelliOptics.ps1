#Requires -Version 5.1
<#
.SYNOPSIS
    IntelliOptics 2.5 Uninstaller

.DESCRIPTION
    Stops all services, removes containers, and optionally removes images and volumes.

.EXAMPLE
    .\Uninstall-IntelliOptics.ps1              # Stop + remove containers
    .\Uninstall-IntelliOptics.ps1 -RemoveAll   # Also remove images + volumes
#>

param(
    [switch]$RemoveAll
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host ""
Write-Host "  IntelliOptics 2.5 - Uninstaller" -ForegroundColor Red
Write-Host ""

# Confirm
if ($RemoveAll) {
    Write-Host "  WARNING: This will remove all containers, images, AND volumes (data)." -ForegroundColor Yellow
    $confirm = Read-Host "  Type 'yes' to confirm"
    if ($confirm -ne "yes") {
        Write-Host "  Cancelled." -ForegroundColor Gray
        exit 0
    }
}

# Stop and remove containers
Write-Host "`n>> Stopping and removing containers..." -ForegroundColor Cyan
docker compose -f docker-compose.prod.yml down 2>&1

if ($RemoveAll) {
    # Remove images
    Write-Host "`n>> Removing Docker images..." -ForegroundColor Cyan
    $images = docker images --filter "label=com.docker.compose.project" --format "{{.ID}}" 2>$null
    if ($images) {
        docker rmi $images -f 2>&1 | Out-Null
    }
    # Also remove specifically named images
    $prefixes = @("install-cloud-backend", "install-cloud-frontend", "install-cloud-worker", "install-edge-api", "install-edge-inference")
    foreach ($prefix in $prefixes) {
        $img = docker images --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -like "*$prefix*" }
        if ($img) { docker rmi $img -f 2>&1 | Out-Null }
    }
    Write-Host "  Images removed." -ForegroundColor Green

    # Remove volumes
    Write-Host "`n>> Removing Docker volumes..." -ForegroundColor Cyan
    docker compose -f docker-compose.prod.yml down -v 2>&1 | Out-Null
    Write-Host "  Volumes removed." -ForegroundColor Green

    # Remove .env
    if (Test-Path ".env") {
        Remove-Item ".env" -Force
        Write-Host "  .env file removed." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "  IntelliOptics uninstalled." -ForegroundColor Green
if (-not $RemoveAll) {
    Write-Host "  Images and volumes preserved. Use -RemoveAll to delete everything." -ForegroundColor Gray
}
Write-Host ""
