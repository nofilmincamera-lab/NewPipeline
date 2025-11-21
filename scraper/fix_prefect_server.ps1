# Fix Prefect Server Database Connection (PowerShell)
# This script helps set up the Prefect server with proper password configuration

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Prefect Server Configuration Fix" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if POSTGRES_PASSWORD is set
$postgresPassword = $env:POSTGRES_PASSWORD
if ([string]::IsNullOrEmpty($postgresPassword)) {
    Write-Host "WARNING: POSTGRES_PASSWORD environment variable is not set" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Option 1: Set environment variable:" -ForegroundColor Green
    Write-Host "  `$env:POSTGRES_PASSWORD = 'your_password'" -ForegroundColor Gray
    Write-Host "  docker-compose restart prefect-server" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Option 2: Use secret file (default):" -ForegroundColor Green
    Write-Host "  Ensure ../ops/secrets/postgres_password.txt exists" -ForegroundColor Gray
    Write-Host ""
    
    # Check if secret file exists
    $secretFile = "..\ops\secrets\postgres_password.txt"
    if (Test-Path $secretFile) {
        Write-Host "[OK] Secret file found: $secretFile" -ForegroundColor Green
        Write-Host "The Prefect server should use this file automatically." -ForegroundColor Gray
    } else {
        Write-Host "[ERROR] Secret file not found: $secretFile" -ForegroundColor Red
        Write-Host "Please create it or set POSTGRES_PASSWORD environment variable" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[OK] POSTGRES_PASSWORD environment variable is set" -ForegroundColor Green
    Write-Host "The Prefect server will use this value." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Restarting Prefect server..." -ForegroundColor Cyan
Set-Location scraper
docker-compose restart prefect-server
Set-Location ..

Write-Host ""
Write-Host "Waiting for server to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Checking Prefect server status..." -ForegroundColor Cyan
docker logs bpo-prefect-server --tail 20

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Check Prefect UI at: http://localhost:4200" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan

