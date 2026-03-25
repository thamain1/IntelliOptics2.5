# Initialize-Environment.ps1
# Generates .env from template, auto-generates secrets, prompts for Supabase creds.

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
$content = $content -replace "^API_SECRET_KEY=.*$", "API_SECRET_KEY=$secret"
Write-Host "  Auto-generated a 256-bit secret key."

# Prompt for Supabase credentials
Write-Step "Supabase Configuration"
Write-Host "  Enter your Supabase project credentials (from Settings > Database / API)."
Write-Host "  Press Enter to skip optional fields.`n"

$pgDsn = Read-Host "  POSTGRES_DSN (postgresql://postgres:PASS@db.PROJECT.supabase.co:5432/postgres)"
if ($pgDsn) { $content = $content -replace "^POSTGRES_DSN=.*$", "POSTGRES_DSN=$pgDsn" }

$supaUrl = Read-Host "  SUPABASE_URL (https://PROJECT.supabase.co)"
if ($supaUrl) { $content = $content -replace "^SUPABASE_URL=.*$", "SUPABASE_URL=$supaUrl" }

$supaAnon = Read-Host "  SUPABASE_ANON_KEY"
if ($supaAnon) { $content = $content -replace "^SUPABASE_ANON_KEY=.*$", "SUPABASE_ANON_KEY=$supaAnon" }

$supaService = Read-Host "  SUPABASE_SERVICE_KEY"
if ($supaService) { $content = $content -replace "^SUPABASE_SERVICE_KEY=.*$", "SUPABASE_SERVICE_KEY=$supaService" }

# Optional: SendGrid
Write-Step "Alert Configuration (optional - press Enter to skip)"
$sgKey = Read-Host "  SENDGRID_API_KEY"
if ($sgKey) { $content = $content -replace "^SENDGRID_API_KEY=.*$", "SENDGRID_API_KEY=$sgKey" }

# Write final .env
$content | Set-Content $EnvFile -NoNewline
Write-Host "`n  .env file created successfully." -ForegroundColor Green

# Validate required fields
$envLines = Get-Content $EnvFile
$missing = @()
foreach ($line in $envLines) {
    if ($line -match "^POSTGRES_DSN=postgresql://postgres:YOUR_PASSWORD") { $missing += "POSTGRES_DSN" }
    if ($line -match "^SUPABASE_URL=https://YOUR_PROJECT") { $missing += "SUPABASE_URL" }
}
if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "  WARNING: The following required values still have placeholder values:" -ForegroundColor Yellow
    foreach ($m in $missing) { Write-Host "    - $m" -ForegroundColor Yellow }
    Write-Host "  Edit install/.env before starting services." -ForegroundColor Yellow
}
