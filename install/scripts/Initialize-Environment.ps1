# Initialize-Environment.ps1
# Generates .env from template, auto-generates API secret key.
# Supabase and SendGrid credentials are pre-configured in the template.

param(
    [string]$EnvFile = ".env",
    [string]$TemplatePath = ".env.template"
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }

# If .env already exists, ask before overwriting
if (Test-Path $EnvFile) {
    Write-Host ""
    Write-Host "An .env file already exists." -ForegroundColor Yellow
    $overwrite = Read-Host "Overwrite it? (y/N)"
    if ($overwrite -ne "y" -and $overwrite -ne "Y") {
        Write-Host "Keeping existing .env file." -ForegroundColor Green
        return
    }
}

# Copy template
Write-Step "Creating .env from template..."
Copy-Item $TemplatePath $EnvFile -Force

# Read content
$content = Get-Content $EnvFile -Raw

# Auto-generate API_SECRET_KEY
Write-Step "Generating API secret key..."
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$secret = [Convert]::ToBase64String($bytes)
$content = $content -replace "(?m)^API_SECRET_KEY=.*$", "API_SECRET_KEY=$secret"
Write-Host "  Auto-generated a 256-bit secret key."

# Write final .env
$content | Set-Content $EnvFile -NoNewline

Write-Host ""
Write-Host "  .env file created successfully." -ForegroundColor Green
Write-Host "  Supabase and SendGrid credentials are pre-configured." -ForegroundColor Green
Write-Host "  API_SECRET_KEY has been auto-generated." -ForegroundColor Green
