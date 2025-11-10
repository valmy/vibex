# Demo script for automated CLI login using the sign.py script (PowerShell version)
# This demonstrates the wallet-based authentication flow

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "AI Trading Agent - Automated CLI Login Demo" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if backend is running
Write-Host "[1/5] Checking if backend is running..." -ForegroundColor Yellow
$API_BASE = if ($env:API_BASE) { $env:API_BASE } else { "http://localhost:3000" }

try {
    $response = Invoke-RestMethod -Uri "$API_BASE/health" -Method Get -TimeoutSec 5 -ErrorAction Stop
    Write-Host "[OK] Backend is running at $API_BASE" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Backend is not running at $API_BASE" -ForegroundColor Red
    Write-Host "Please start the backend first:" -ForegroundColor Yellow
    Write-Host "  cd backend && podman-compose up -d" -ForegroundColor White
    exit 1
}
Write-Host ""

# Check if we have a test wallet configured
Write-Host "[2/5] Checking wallet configuration..." -ForegroundColor Yellow
if (-not $env:ADDR -or -not $env:PRIVATE_KEY) {
    Write-Host "[WARNING] No wallet configured in environment variables" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "You need to set ADDR and PRIVATE_KEY environment variables." -ForegroundColor White
    Write-Host ""
    Write-Host "For testing purposes, you can use the test wallet from the database:" -ForegroundColor White
    Write-Host '  $env:ADDR="0xCfbEE662dc66475Bf5F3b7203b4b6EE03028952F"' -ForegroundColor Cyan
    Write-Host '  $env:PRIVATE_KEY="<your_test_private_key>"' -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Or generate a new test wallet using Python:" -ForegroundColor White
    Write-Host "  cd backend && uv run python scripts/generate_test_wallet.py" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[WARNING] SECURITY WARNING: Only use test wallets for development!" -ForegroundColor Red
    Write-Host "Never use real wallets with funds for testing!" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Wallet configured: $env:ADDR" -ForegroundColor Green
Write-Host ""

# Run the automated sign.py script
Write-Host "[3/5] Running automated login script..." -ForegroundColor Yellow
Write-Host "This will:" -ForegroundColor White
Write-Host "  1. Request a challenge from the API" -ForegroundColor White
Write-Host "  2. Sign the challenge with your private key" -ForegroundColor White
Write-Host "  3. Login and receive a JWT token" -ForegroundColor White
Write-Host ""

# Change to backend directory
Push-Location (Join-Path $PSScriptRoot "..")

try {
    # Run sign.py and capture output
    $output = uv run python scripts/sign.py 2>&1 | Out-String
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Login failed!" -ForegroundColor Red
        Write-Host $output -ForegroundColor Red
        exit 1
    }
    
    # Extract the token (first line of output)
    $lines = $output -split "`n"
    $TOKEN = $lines[0].Trim()
    
    Write-Host "[OK] Login successful!" -ForegroundColor Green
    Write-Host ""
    
    # Display the token and usage instructions
    Write-Host "[4/5] JWT Token received:" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host $TOKEN -ForegroundColor White
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host ""
    
    # Test the /api/v1/auth/me endpoint
    Write-Host "[5/5] Testing authenticated endpoint..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Calling GET /api/v1/auth/me..." -ForegroundColor White
    
    try {
        $headers = @{
            "Authorization" = "Bearer $TOKEN"
        }
        $meResponse = Invoke-RestMethod -Uri "$API_BASE/api/v1/auth/me" -Headers $headers -Method Get
        
        Write-Host "Response:" -ForegroundColor White
        $meResponse | ConvertTo-Json -Depth 10 | Write-Host
        Write-Host ""
        
        Write-Host "==========================================" -ForegroundColor Cyan
        Write-Host "[OK] Demo Complete!" -ForegroundColor Green
        Write-Host "==========================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "You can now use the token for authenticated requests:" -ForegroundColor White
        Write-Host ""
        Write-Host '  $TOKEN = "' -NoNewline -ForegroundColor Cyan
        Write-Host $TOKEN -NoNewline -ForegroundColor White
        Write-Host '"' -ForegroundColor Cyan
        Write-Host '  $headers = @{"Authorization" = "Bearer $TOKEN"}' -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Examples:" -ForegroundColor White
        Write-Host "  # Get current user info" -ForegroundColor Gray
        Write-Host '  Invoke-RestMethod -Uri "' -NoNewline -ForegroundColor Cyan
        Write-Host "$API_BASE/api/v1/auth/me" -NoNewline -ForegroundColor White
        Write-Host '" -Headers $headers' -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  # Generate trading decision" -ForegroundColor Gray
        Write-Host '  $body = @{' -ForegroundColor Cyan
        Write-Host '    symbol = "BTCUSDT"' -ForegroundColor Cyan
        Write-Host '    account_id = 1' -ForegroundColor Cyan
        Write-Host '  } | ConvertTo-Json' -ForegroundColor Cyan
        Write-Host '  Invoke-RestMethod -Uri "' -NoNewline -ForegroundColor Cyan
        Write-Host "$API_BASE/api/v1/decisions/generate" -NoNewline -ForegroundColor White
        Write-Host '" `' -ForegroundColor Cyan
        Write-Host '    -Headers $headers -Method Post -Body $body -ContentType "application/json"' -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  # List accounts" -ForegroundColor Gray
        Write-Host '  Invoke-RestMethod -Uri "' -NoNewline -ForegroundColor Cyan
        Write-Host "$API_BASE/api/v1/accounts" -NoNewline -ForegroundColor White
        Write-Host '" -Headers $headers' -ForegroundColor Cyan
        Write-Host ""
        
    } catch {
        Write-Host "[ERROR] Failed to test authenticated endpoint" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        exit 1
    }
    
} finally {
    Pop-Location
}

