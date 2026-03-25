# Start-Services.ps1
# Starts all IntelliOptics services using docker compose.

param(
    [string]$ComposeFile = "docker-compose.prod.yml"
)

$ErrorActionPreference = "Stop"

Write-Host "`n>> Starting IntelliOptics services..." -ForegroundColor Cyan

docker compose -f $ComposeFile up -d 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Failed to start services." -ForegroundColor Red
    Write-Host "  Check logs: docker compose -f $ComposeFile logs" -ForegroundColor Yellow
    exit 1
}

Write-Host "  All services started." -ForegroundColor Green
Write-Host "  Run 'docker compose -f $ComposeFile ps' to see status." -ForegroundColor Gray
