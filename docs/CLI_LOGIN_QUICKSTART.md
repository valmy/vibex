# CLI Login Quick Start Guide

This guide shows you how to authenticate with the AI Trading Agent API using automated CLI scripts.

## Prerequisites

- Backend server running (`podman-compose up -d`)
- Python environment with `uv` available
- `eth-account` package installed (automatically installed with `uv`)

## Quick Start (3 Steps)

### Step 1: Generate a Test Wallet

```bash
cd backend
uv run python scripts/generate_test_wallet.py
```

**Output:**
```
============================================================
AI Trading Agent - Test Wallet Generator
============================================================

Generating a new test wallet...

[OK] Wallet generated successfully!

------------------------------------------------------------
Wallet Details:
------------------------------------------------------------
Address:     0xdb80Db8614EEc8DAB77955022c74646bb295A888
Private Key: 2ff7975f9b18065ae93f6dc5b990350b0ba2555078185c628e818bd054169b0d
------------------------------------------------------------

Environment Variables:
------------------------------------------------------------
export ADDR=0xdb80Db8614EEc8DAB77955022c74646bb295A888
export PRIVATE_KEY=2ff7975f9b18065ae93f6dc5b990350b0ba2555078185c628e818bd054169b0d
------------------------------------------------------------
```

### Step 2: Set Environment Variables

**Linux/macOS (Bash):**
```bash
export ADDR=0xdb80Db8614EEc8DAB77955022c74646bb295A888
export PRIVATE_KEY=2ff7975f9b18065ae93f6dc5b990350b0ba2555078185c628e818bd054169b0d
```

**Windows (PowerShell):**
```powershell
$env:ADDR="0xdb80Db8614EEc8DAB77955022c74646bb295A888"
$env:PRIVATE_KEY="2ff7975f9b18065ae93f6dc5b990350b0ba2555078185c628e818bd054169b0d"
```

### Step 3: Run Automated Login

**Option A: Using the Demo Script (Recommended)**

**Linux/macOS:**
```bash
cd backend
bash scripts/demo_login.sh
```

**Windows:**
```powershell
cd backend
.\scripts\demo_login.ps1
```

**Option B: Using sign.py Directly**

```bash
cd backend
uv run python scripts/sign.py
```

**Output:**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIweGRiODBkYjg2MTRlZWM4ZGFiNzc5NTUwMjJjNzQ2NDZiYjI5NWE4ODgiLCJleHAiOjE3NjI3NzE4MzZ9.Alp2E2z2v13FiehaNhfxYYzYq9XODm8jUwXq1NaxHWI

Export for curl:
export AUTH='Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
# example: curl -H "$AUTH" http://localhost:3000/api/v1/auth/me
```

## Using the Token

### Linux/macOS (Bash)

```bash
# Set the token
export AUTH='Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'

# Get current user info
curl -H "$AUTH" http://localhost:3000/api/v1/auth/me

# Generate trading decision
curl -X POST -H "$AUTH" -H "Content-Type: application/json" \
  http://localhost:3000/api/v1/decisions/generate \
  -d '{"symbol": "BTCUSDT", "account_id": 1}'

# List accounts
curl -H "$AUTH" http://localhost:3000/api/v1/accounts
```

### Windows (PowerShell)

```powershell
# Set the token
$TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
$headers = @{"Authorization" = "Bearer $TOKEN"}

# Get current user info
Invoke-RestMethod -Uri "http://localhost:3000/api/v1/auth/me" -Headers $headers

# Generate trading decision
$body = @{
    symbol = "BTCUSDT"
    account_id = 1
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:3000/api/v1/decisions/generate" `
  -Headers $headers -Method Post -Body $body -ContentType "application/json"

# List accounts
Invoke-RestMethod -Uri "http://localhost:3000/api/v1/accounts" -Headers $headers
```

## One-Liner Examples

### Get Token and Use It Immediately

**Linux/macOS:**
```bash
# Set wallet credentials
export ADDR=0xYourAddress
export PRIVATE_KEY=0xYourPrivateKey

# Get token and call API in one line
TOKEN=$(cd backend && uv run python scripts/sign.py | head -1)
curl -H "Authorization: Bearer $TOKEN" http://localhost:3000/api/v1/auth/me
```

**Windows:**
```powershell
# Set wallet credentials
$env:ADDR="0xYourAddress"
$env:PRIVATE_KEY="0xYourPrivateKey"

# Get token and call API
cd backend
$output = uv run python scripts/sign.py | Out-String
$TOKEN = ($output -split "`n")[0].Trim()
$headers = @{"Authorization" = "Bearer $TOKEN"}
Invoke-RestMethod -Uri "http://localhost:3000/api/v1/auth/me" -Headers $headers
```

## Complete Example Session

```bash
# 1. Generate test wallet
cd backend
uv run python scripts/generate_test_wallet.py

# 2. Copy and paste the export commands from output
export ADDR=0x...
export PRIVATE_KEY=0x...

# 3. Run demo script
bash scripts/demo_login.sh

# 4. Use the token (copy from demo output)
export AUTH='Authorization: Bearer eyJ...'

# 5. Make authenticated requests
curl -H "$AUTH" http://localhost:3000/api/v1/auth/me
curl -H "$AUTH" http://localhost:3000/api/v1/accounts
```

## Demo Script Output

When you run the demo script, you'll see:

```
==========================================
AI Trading Agent - Automated CLI Login Demo
==========================================

[1/5] Checking if backend is running...
[OK] Backend is running at http://localhost:3000

[2/5] Checking wallet configuration...
[OK] Wallet configured: 0xdb80Db8614EEc8DAB77955022c74646bb295A888

[3/5] Running automated login script...
This will:
  1. Request a challenge from the API
  2. Sign the challenge with your private key
  3. Login and receive a JWT token

[OK] Login successful!

[4/5] JWT Token received:
----------------------------------------
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
----------------------------------------

[5/5] Testing authenticated endpoint...

Calling GET /api/v1/auth/me...
Response:
{
    "id": 630,
    "created_at": "2025-11-10T06:49:00.136360",
    "updated_at": "2025-11-10T06:49:00.136360",
    "address": "0xdb80db8614eec8dab77955022c74646bb295a888",
    "is_admin": false
}

==========================================
[OK] Demo Complete!
==========================================
```

## Troubleshooting

### Backend Not Running

**Error:**
```
ERROR: Backend is not running at http://localhost:3000
```

**Solution:**
```bash
cd backend
podman-compose up -d
```

### Missing Environment Variables

**Error:**
```
Environment variable ADDR is required
Environment variable PRIVATE_KEY is required
```

**Solution:**
```bash
# Generate a new test wallet
cd backend
uv run python scripts/generate_test_wallet.py

# Copy and run the export commands from the output
```

### Authentication Failed

**Error:**
```
HTTP error calling http://localhost:3000/api/v1/auth/login: 401
```

**Possible Causes:**
- Invalid private key
- Challenge expired (time-limited)
- Signature mismatch

**Solution:**
- Verify your private key is correct
- Run the script again to get a fresh challenge
- Ensure the address matches the private key

### Module Not Found

**Error:**
```
ModuleNotFoundError: No module named 'eth_account'
```

**Solution:**
```bash
cd backend
uv pip install eth-account
```

## Security Best Practices

### ⚠️ IMPORTANT SECURITY WARNINGS

1. **Test Wallets Only**
   - Never use wallets with real funds for testing
   - Generate dedicated test wallets for development
   - Keep test and production wallets completely separate

2. **Private Key Protection**
   - Never commit private keys to version control
   - Add `.env` to `.gitignore`
   - Use environment variables or secure key management
   - Rotate keys regularly

3. **Token Security**
   - Tokens expire after 240 minutes (default)
   - Store tokens securely
   - Don't share tokens
   - Implement token refresh for long-running sessions

4. **Production Considerations**
   - Use HTTPS in production
   - Implement rate limiting
   - Monitor for suspicious activity
   - Use hardware wallets for production
   - Implement proper key management systems

## Available Scripts

| Script | Purpose | Platform |
|--------|---------|----------|
| `generate_test_wallet.py` | Generate new test wallet | All |
| `sign.py` | Automated login (returns token) | All |
| `demo_login.sh` | Interactive demo with examples | Linux/macOS |
| `demo_login.ps1` | Interactive demo with examples | Windows |

## See Also

- [API Authentication Documentation](API_AUTH.md)
- [Backend Scripts README](../backend/scripts/README.md)
- [Environment Variables](ENVIRONMENT_VARIABLES.md)
- [API Documentation](http://localhost:3000/docs) (when backend is running)

## Quick Reference

### Generate Wallet
```bash
cd backend && uv run python scripts/generate_test_wallet.py
```

### Login
```bash
cd backend && uv run python scripts/sign.py
```

### Demo (Linux/macOS)
```bash
cd backend && bash scripts/demo_login.sh
```

### Demo (Windows)
```powershell
cd backend && .\scripts\demo_login.ps1
```

