# Test-Prerequisites.ps1
# Checks that Docker, disk space, and ports are available.

param(
    [int]$CloudPort = 80,
    [int]$EdgePort = 30101
)

$ErrorActionPreference = "Stop"

function Write-Status($msg) { Write-Host "  [CHECK] $msg" -ForegroundColor Cyan }
function Write-Pass($msg)   { Write-Host "  [PASS]  $msg" -ForegroundColor Green }
function Write-Fail($msg)   { Write-Host "  [FAIL]  $msg" -ForegroundColor Red }

$failed = $false

# 1. Docker installed
Write-Status "Docker CLI..."
try {
    $null = docker --version 2>&1
    Write-Pass "Docker CLI found."
} catch {
    Write-Fail "Docker CLI not found. Install Docker Desktop: https://docs.docker.com/desktop/install/windows-install/"
    $failed = $true
}

# 2. Docker daemon running
Write-Status "Docker daemon..."
try {
    $info = docker info 2>&1
    if ($LASTEXITCODE -ne 0) { throw "not running" }
    Write-Pass "Docker daemon is running."
} catch {
    Write-Fail "Docker daemon is not running. Start Docker Desktop and try again."
    $failed = $true
}

# 3. Docker Compose
Write-Status "Docker Compose..."
try {
    $null = docker compose version 2>&1
    Write-Pass "Docker Compose found."
} catch {
    Write-Fail "Docker Compose not found. Update Docker Desktop to get Compose V2."
    $failed = $true
}

# 4. Disk space (need ~20 GB free)
Write-Status "Disk space..."
$drive = (Get-Location).Drive
$freeGB = [math]::Round((Get-PSDrive $drive.Name).Free / 1GB, 1)
if ($freeGB -ge 20) {
    Write-Pass "Disk space: ${freeGB} GB free."
} else {
    Write-Fail "Only ${freeGB} GB free. Need at least 20 GB for Docker images and models."
    $failed = $true
}

# 5. Port availability
Write-Status "Port $CloudPort (cloud)..."
$portInUse = Get-NetTCPConnection -LocalPort $CloudPort -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Fail "Port $CloudPort is in use. Stop the service using it or set CLOUD_HTTP_PORT in .env."
    $failed = $true
} else {
    Write-Pass "Port $CloudPort is available."
}

Write-Status "Port $EdgePort (edge)..."
$portInUse = Get-NetTCPConnection -LocalPort $EdgePort -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Fail "Port $EdgePort is in use. Stop the service using it or set EDGE_PORT in .env."
    $failed = $true
} else {
    Write-Pass "Port $EdgePort is available."
}

# 6. Git (informational)
Write-Status "Git..."
try {
    $null = git --version 2>&1
    Write-Pass "Git found."
} catch {
    Write-Host "  [WARN]  Git not found (optional, needed for updates)." -ForegroundColor Yellow
}

if ($failed) {
    Write-Host ""
    Write-Fail "Prerequisites check FAILED. Fix the issues above and try again."
    exit 1
}

Write-Host ""
Write-Pass "All prerequisites passed."
