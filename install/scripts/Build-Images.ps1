# Build-Images.ps1
# Builds all Docker images for IntelliOptics 2.5.

param(
    [string]$ComposeFile = "docker-compose.prod.yml",
    [switch]$NoCache
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }

$buildArgs = @("-f", $ComposeFile, "build")
if ($NoCache) { $buildArgs += "--no-cache" }

$services = @(
    @{ Name = "cloud-backend";   Desc = "Cloud Backend (FastAPI)" },
    @{ Name = "cloud-frontend";  Desc = "Cloud Frontend (React)" },
    @{ Name = "cloud-worker";    Desc = "Cloud Worker (ONNX)" },
    @{ Name = "edge-api";        Desc = "Edge API" },
    @{ Name = "edge-inference";  Desc = "Edge Inference (YOLOE, VLM)" }
)

Write-Step "Building $($services.Count) Docker images..."
Write-Host "  This may take 5-15 minutes on first build.`n"

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

foreach ($svc in $services) {
    Write-Host "  Building $($svc.Desc)..." -ForegroundColor White -NoNewline
    $svcStart = [System.Diagnostics.Stopwatch]::StartNew()

    $svcArgs = $buildArgs + $svc.Name
    docker compose @svcArgs 2>&1 | Out-Null

    if ($LASTEXITCODE -ne 0) {
        Write-Host " FAILED" -ForegroundColor Red
        Write-Host ""
        Write-Host "Build failed for $($svc.Name). Run with verbose output:" -ForegroundColor Red
        Write-Host "  docker compose -f $ComposeFile build $($svc.Name)" -ForegroundColor Yellow
        exit 1
    }

    $elapsed = [math]::Round($svcStart.Elapsed.TotalSeconds, 0)
    Write-Host " done (${elapsed}s)" -ForegroundColor Green
}

$total = [math]::Round($stopwatch.Elapsed.TotalMinutes, 1)
Write-Host "`n  All images built successfully in ${total} minutes." -ForegroundColor Green
