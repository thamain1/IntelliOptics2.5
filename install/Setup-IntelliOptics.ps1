#Requires -Version 5.1
<#
.SYNOPSIS
    Standalone IntelliOptics 2.5 Installer

.DESCRIPTION
    Single script that takes a fresh Windows machine from zero to a fully
    running IntelliOptics 2.5 stack. Installs Git and Docker Desktop if
    missing, clones the repo, then hands off to the existing install pipeline.

.PARAMETER InstallPath
    Root directory for the installation. Default: C:\IntelliOptics

.PARAMETER Branch
    Git branch to clone/checkout. Default: main

.PARAMETER NoCache
    Pass -NoCache to force Docker image rebuilds from scratch.

.EXAMPLE
    .\Setup-IntelliOptics.ps1
    .\Setup-IntelliOptics.ps1 -InstallPath "D:\IntelliOptics" -Branch dev
    .\Setup-IntelliOptics.ps1 -NoCache
#>

param(
    [string]$InstallPath = "C:\IntelliOptics",
    [switch]$NoCache,
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

# ── Banner ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor Blue
Write-Host "    IntelliOptics 2.5 - Standalone Setup" -ForegroundColor White
Write-Host "    Edge-First AI Inspection Platform" -ForegroundColor Gray
Write-Host "    4wardmotion Solutions, Inc." -ForegroundColor Gray
Write-Host "  ================================================================" -ForegroundColor Blue
Write-Host ""

# ── Helpers ─────────────────────────────────────────────────────────────

function Write-Step {
    param([string]$Step, [string]$Message)
    Write-Host "Step $Step : $Message" -ForegroundColor White
}

function Write-Ok {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor Cyan
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [!] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

function Refresh-Path {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath    = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"
}

function Test-CommandExists {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

function Test-WingetAvailable {
    $null = Get-Command winget -ErrorAction SilentlyContinue
    return $?
}

# ── Step 0: Require Administrator ───────────────────────────────────────
Write-Step "0/4" "Checking administrator privileges..."

$currentPrincipal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Fail "This script must be run as Administrator."
    Write-Host ""
    Write-Host "  Right-click PowerShell and select 'Run as administrator'," -ForegroundColor Yellow
    Write-Host "  then run this script again." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Ok "Running as Administrator."

# ── Step 1: Check / Install Git ─────────────────────────────────────────
Write-Step "1/4" "Checking Git..."

if (Test-CommandExists "git") {
    $gitVersion = git --version 2>&1
    Write-Ok "Git already installed ($gitVersion)."
} else {
    Write-Info "Git not found. Installing..."

    if (Test-WingetAvailable) {
        Write-Info "Installing Git via winget..."
        winget install Git.Git --accept-source-agreements --accept-package-agreements --silent
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "winget install failed for Git. Please install Git manually and re-run."
            exit 1
        }
    } else {
        Write-Info "winget not available. Downloading Git installer..."
        $gitInstallerUrl = "https://github.com/git-for-windows/git/releases/latest/download/Git-2.47.1.2-64-bit.exe"
        $gitInstallerPath = Join-Path $env:TEMP "git-installer.exe"

        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $gitInstallerUrl -OutFile $gitInstallerPath -UseBasicParsing
        } catch {
            Write-Fail "Failed to download Git installer."
            Write-Host "  Please install Git manually from https://git-scm.com/download/win" -ForegroundColor Yellow
            Write-Host "  Then re-run this script." -ForegroundColor Yellow
            exit 1
        }

        Write-Info "Running Git installer (silent)..."
        Start-Process -FilePath $gitInstallerPath -ArgumentList "/VERYSILENT", "/NORESTART" -Wait -NoNewWindow
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Git installer exited with an error. Please install Git manually and re-run."
            exit 1
        }
        Remove-Item $gitInstallerPath -Force -ErrorAction SilentlyContinue
    }

    # Refresh PATH and verify
    Refresh-Path
    Start-Sleep -Seconds 2

    if (Test-CommandExists "git") {
        $gitVersion = git --version 2>&1
        Write-Ok "Git installed successfully ($gitVersion)."
    } else {
        Write-Fail "Git was installed but is not in PATH."
        Write-Host "  You may need to restart this terminal, then re-run the script." -ForegroundColor Yellow
        exit 1
    }
}

# ── Step 2: Check / Install Docker Desktop ──────────────────────────────
Write-Step "2/4" "Checking Docker Desktop..."

if (Test-CommandExists "docker") {
    $dockerVersion = docker --version 2>&1
    Write-Ok "Docker already installed ($dockerVersion)."
} else {
    Write-Info "Docker Desktop not found. Installing..."

    if (Test-WingetAvailable) {
        Write-Info "Installing Docker Desktop via winget..."
        winget install Docker.DockerDesktop --accept-source-agreements --accept-package-agreements --silent
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "winget install failed for Docker Desktop."
            Write-Host "  Please install Docker Desktop manually from https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Fail "Docker Desktop must be installed manually (requires GUI for WSL2/Hyper-V setup)."
        Write-Host ""
        Write-Host "  1. Download from: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
        Write-Host "  2. Install and complete the WSL2/Hyper-V configuration." -ForegroundColor Yellow
        Write-Host "  3. Restart your machine if prompted." -ForegroundColor Yellow
        Write-Host "  4. Re-run this script." -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }

    # Refresh PATH
    Refresh-Path
    Start-Sleep -Seconds 2

    if (-not (Test-CommandExists "docker")) {
        Write-Warn "Docker Desktop was installed but requires a restart."
        Write-Host ""
        Write-Host "  Please restart your computer, then re-run this script." -ForegroundColor Yellow
        Write-Host ""
        exit 0
    }
}

# Wait for Docker daemon to be ready
Write-Info "Waiting for Docker daemon to start..."
$dockerReady = $false
for ($i = 0; $i -lt 30; $i++) {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerReady = $true
        break
    }
    Start-Sleep -Seconds 5
}

if (-not $dockerReady) {
    Write-Fail "Docker daemon did not start within 150 seconds."
    Write-Host "  Make sure Docker Desktop is running, then re-run this script." -ForegroundColor Yellow
    exit 1
}
Write-Ok "Docker daemon is running."

# Verify Docker Compose v2
$composeVersion = docker compose version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Compose v2 is not available."
    Write-Host "  Please update Docker Desktop to a version that includes Compose v2." -ForegroundColor Yellow
    exit 1
}
Write-Ok "Docker Compose available ($composeVersion)."

# ── Step 3: Clone / Update Repository ───────────────────────────────────
Write-Step "3/4" "Preparing repository..."

$repoUrl  = "https://github.com/thamain1/IntelliOptics2.5.git"
$repoPath = Join-Path $InstallPath "IntelliOptics2.5"

# Ensure parent directory exists
if (-not (Test-Path $InstallPath)) {
    Write-Info "Creating install directory: $InstallPath"
    New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
}

if (Test-Path (Join-Path $repoPath ".git")) {
    Write-Info "Existing clone found. Pulling latest changes..."
    Push-Location $repoPath
    try {
        git checkout $Branch 2>&1 | Out-Null
        git pull origin $Branch 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "git pull failed. Continuing with existing code."
        } else {
            Write-Ok "Repository updated."
        }
    } finally {
        Pop-Location
    }
} elseif (Test-Path $repoPath) {
    # Directory exists but is not a git repo — try to init and pull
    Write-Warn "Directory $repoPath exists but is not a git repo."
    Write-Info "Attempting to initialize and pull..."
    Push-Location $repoPath
    try {
        git init 2>&1 | Out-Null
        git remote add origin $repoUrl 2>&1 | Out-Null
        git fetch origin $Branch 2>&1 | Out-Null
        git checkout -f $Branch 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Could not recover existing directory as a git repo."
            Write-Host "  Delete or rename $repoPath, then re-run this script." -ForegroundColor Yellow
            exit 1
        }
        Write-Ok "Repository recovered."
    } finally {
        Pop-Location
    }
} else {
    Write-Info "Cloning IntelliOptics 2.5 into $repoPath..."
    git clone --branch $Branch $repoUrl $repoPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "git clone failed. Check your network connection and GitHub access."
        exit 1
    }
    Write-Ok "Repository cloned."
}

# ── Step 4: Hand Off to Existing Installer ──────────────────────────────
Write-Step "4/4" "Running IntelliOptics installer..."
Write-Host ""

$installerPath = Join-Path $repoPath "install\Install-IntelliOptics.ps1"

if (-not (Test-Path $installerPath)) {
    Write-Fail "Install-IntelliOptics.ps1 not found at $installerPath"
    Write-Host "  The repository may be incomplete. Try deleting $repoPath and re-running." -ForegroundColor Yellow
    exit 1
}

$installArgs = @{}
if ($NoCache) { $installArgs.NoCache = $true }

& $installerPath @installArgs
exit $LASTEXITCODE
