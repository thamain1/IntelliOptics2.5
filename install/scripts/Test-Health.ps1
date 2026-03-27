# Test-Health.ps1
# Waits for all services to become healthy (up to 3 minutes).

param(
    [string]$ComposeFile = "docker-compose.prod.yml",
    [int]$TimeoutSeconds = 180
)

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }

function Get-ContainerHealth($containerName) {
    $ErrorActionPreference = "Continue"
    $status = docker inspect --format '{{.State.Health.Status}}' $containerName 2>&1
    if ($LASTEXITCODE -ne 0 -or "$status" -match "template parsing error|no such object") {
        # No healthcheck or container not found — check if running
        $state = docker inspect --format '{{.State.Status}}' $containerName 2>&1
        if ($LASTEXITCODE -eq 0 -and "$state" -notmatch "template parsing error|no such object") {
            return $state.Trim()
        }
        return $null
    }
    return $status.Trim()
}

$services = @(
    @{ Name = "io-cloud-backend";   Url = "http://localhost:8000/health";       Label = "Cloud Backend" },
    @{ Name = "io-edge-inference";  Url = "http://localhost:8001/health";       Label = "Edge Inference" },
    @{ Name = "io-edge-api";        Url = $null;                                Label = "Edge API" },
    @{ Name = "io-cloud-nginx";     Url = $null;                                Label = "Cloud Nginx" },
    @{ Name = "io-edge-nginx";      Url = $null;                                Label = "Edge Nginx" }
)

Write-Step "Waiting for services to become healthy (timeout: ${TimeoutSeconds}s)..."

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$allHealthy = $false

while ($stopwatch.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
    $healthy = 0
    $total = $services.Count

    foreach ($svc in $services) {
        $status = Get-ContainerHealth $svc.Name
        if ($status -eq "healthy" -or $status -eq "running") {
            $healthy++
        }
    }

    $elapsed = [math]::Round($stopwatch.Elapsed.TotalSeconds, 0)
    Write-Host "`r  [$elapsed s] $healthy/$total services healthy..." -NoNewline

    if ($healthy -ge $total) {
        $allHealthy = $true
        break
    }

    Start-Sleep -Seconds 5
}

Write-Host ""

if ($allHealthy) {
    Write-Host ""
    Write-Host "  All services healthy!" -ForegroundColor Green
    Write-Host ""
    foreach ($svc in $services) {
        $status = Get-ContainerHealth $svc.Name
        if (-not $status) { $status = "unknown" }
        $color = if ($status -eq "healthy" -or $status -eq "running") { "Green" } else { "Yellow" }
        Write-Host "    $($svc.Label): $status" -ForegroundColor $color
    }
} else {
    Write-Host ""
    Write-Host "  TIMEOUT: Not all services became healthy within ${TimeoutSeconds}s." -ForegroundColor Red
    Write-Host "  Check logs:" -ForegroundColor Yellow
    Write-Host "    docker compose -f $ComposeFile logs cloud-backend" -ForegroundColor Gray
    Write-Host "    docker compose -f $ComposeFile logs edge-inference" -ForegroundColor Gray
    Write-Host "    docker compose -f $ComposeFile logs edge-api" -ForegroundColor Gray

    # Show which ones failed
    foreach ($svc in $services) {
        $status = Get-ContainerHealth $svc.Name
        if (-not $status) { $status = "not found" }
        if ($status -ne "healthy" -and $status -ne "running") {
            Write-Host "    $($svc.Label): $status" -ForegroundColor Red
        }
    }
    exit 1
}
