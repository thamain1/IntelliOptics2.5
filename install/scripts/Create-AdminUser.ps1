# Create-AdminUser.ps1
# Creates the initial admin user in the cloud backend.

param(
    [string]$Container = "io-cloud-backend"
)

$ErrorActionPreference = "Stop"

Write-Host "`n>> Creating admin user..." -ForegroundColor Cyan

# Check if container is running
$state = docker inspect --format '{{.State.Status}}' $Container 2>$null
if ($state -ne "running") {
    Write-Host "  Backend container is not running. Start services first." -ForegroundColor Red
    exit 1
}

# Run the seed_admin script inside the container
$ErrorActionPreference = "Continue"
docker exec $Container python -m app.seed_admin 2>&1
$ErrorActionPreference = "Stop"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "  Admin user created successfully." -ForegroundColor Green
    Write-Host "  Default credentials:" -ForegroundColor White
    Write-Host "    Email:    admin@intellioptics.com" -ForegroundColor White
    Write-Host "    Password: admin123" -ForegroundColor White
    Write-Host ""
    Write-Host "  IMPORTANT: Change the admin password after first login!" -ForegroundColor Yellow
} else {
    # seed_admin may fail if user already exists - that's OK
    Write-Host "  Admin user may already exist (this is normal on re-install)." -ForegroundColor Yellow
}
