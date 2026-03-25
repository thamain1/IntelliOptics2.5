# Stop-Services.ps1
# Gracefully stops all IntelliOptics services.

param(
    [string]$ComposeFile = "docker-compose.prod.yml"
)

Write-Host "`n>> Stopping IntelliOptics services..." -ForegroundColor Cyan

docker compose -f $ComposeFile down 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "  All services stopped." -ForegroundColor Green
} else {
    Write-Host "  Some services may not have stopped cleanly." -ForegroundColor Yellow
    Write-Host "  Run: docker compose -f $ComposeFile down --remove-orphans" -ForegroundColor Gray
}
