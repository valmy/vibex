# Backend Scripts

This directory contains utility scripts for the AI Trading Agent backend.

## Authentication Scripts

### 🔐 `sign.py` - Automated CLI Login

Automates the complete wallet-based authentication flow:
1. Requests a challenge from the API
2. Signs the challenge with your private key
3. Logs in and receives a JWT token

**Prerequisites:**
- Backend server running at `http://localhost:3000` (or set `API_BASE`)
- Python environment with `uv` available
- `eth-account` package installed

**Usage:**

```bash
cd backend

# Set environment variables
export API_BASE=http://localhost:3000   # optional; defaults to http://localhost:3000
export ADDR=0xYourAddressHere
export PRIVATE_KEY=0xYourPrivateKeyHex

# Run the script
uv run python scripts/sign.py
```

**Output:**

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

Export for curl:
export AUTH='Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
# example: curl -H "$AUTH" http://localhost:3000/api/v1/auth/me
```

**Using the Token:**

```bash
# Export the token
export AUTH='Authorization: Bearer <your_token>'

# Test authenticated endpoint
curl -H "$AUTH" http://localhost:3000/api/v1/auth/me

# Generate trading decision
curl -X POST -H "$AUTH" -H "Content-Type: application/json" \
  http://localhost:3000/api/v1/decisions/generate \
  -d '{"symbol": "BTCUSDT", "account_id": 1}'
```

---

### 🎯 `demo_login.sh` - Interactive Login Demo

A comprehensive demo script that guides you through the automated login process with helpful checks and examples.

**Usage:**

```bash
cd backend

# Set your wallet credentials
export ADDR=0xYourAddressHere
export PRIVATE_KEY=0xYourPrivateKeyHex

# Run the demo
bash scripts/demo_login.sh
```

**What it does:**
1. ✓ Checks if backend is running
2. ✓ Validates wallet configuration
3. ✓ Runs automated login
4. ✓ Tests authenticated endpoint
5. ✓ Provides usage examples

---

### 🔑 `generate_test_wallet.py` - Test Wallet Generator

Generates a new Ethereum wallet for development and testing purposes.

**Usage:**

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

✓ Wallet generated successfully!

------------------------------------------------------------
Wallet Details:
------------------------------------------------------------
Address:     0x1234567890abcdef1234567890abcdef12345678
Private Key: 0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
------------------------------------------------------------

Environment Variables:
------------------------------------------------------------
export ADDR=0x1234567890abcdef1234567890abcdef12345678
export PRIVATE_KEY=0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
------------------------------------------------------------
```

**⚠️ SECURITY WARNING:**
- Only use generated wallets for development/testing
- Never use these wallets with real funds
- Never commit private keys to version control
- Store private keys securely (e.g., in `.env` file)

---

## Complete Authentication Workflow

### Step 1: Generate a Test Wallet

```bash
cd backend
uv run python scripts/generate_test_wallet.py
```

Copy the `export` commands from the output.

### Step 2: Set Environment Variables

```bash
export ADDR=0x...
export PRIVATE_KEY=0x...
```

### Step 3: Run Automated Login

**Option A: Using sign.py directly**

```bash
uv run python scripts/sign.py
```

**Option B: Using the demo script**

```bash
bash scripts/demo_login.sh
```

### Step 4: Use the Token

```bash
# Export the token (from sign.py output)
export AUTH='Authorization: Bearer <your_token>'

# Make authenticated requests
curl -H "$AUTH" http://localhost:3000/api/v1/auth/me
```

---

## Manual Authentication (Without Scripts)

If you prefer to do it manually:

### 1. Request Challenge

```bash
ADDR=0xYourAddressHere
curl -X POST "http://localhost:3000/api/v1/auth/challenge?address=$ADDR"
```

Response:
```json
{
  "challenge": "37124602975658db84981bd4c9c88f1da3f7f6114e8085a2966989900277f456"
}
```

### 2. Sign Challenge

```bash
CHALLENGE=37124602975658db84981bd4c9c88f1da3f7f6114e8085a2966989900277f456
PRIVATE_KEY=0xYourPrivateKeyHex

SIG=$(python3 - <<'PY'
import os
from eth_account import Account
from eth_account.messages import encode_defunct

private_key = os.environ["PRIVATE_KEY"]
challenge = os.environ["CHALLENGE"]

message = encode_defunct(text=challenge)
sig = Account.sign_message(message, private_key=private_key).signature.hex()
if not sig.startswith("0x"):
    sig = "0x" + sig
print(sig)
PY
)
```

### 3. Login

```bash
curl -X POST "http://localhost:3000/api/v1/auth/login?challenge=$CHALLENGE&signature=$SIG&address=$ADDR"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## Other Scripts

### `postgres-tuning.conf`
PostgreSQL performance tuning configuration.

### `run-tests.sh`
Script to run the test suite.

### `setup-monitoring.sh`
Sets up monitoring and observability tools.

### `start-test-db.sh`
Starts a test database instance.

---

## Troubleshooting

### Backend Not Running

```
ERROR: Backend is not running at http://localhost:3000
```

**Solution:**
```bash
cd backend
podman-compose up -d
```

### Missing Environment Variables

```
Environment variable ADDR is required
Environment variable PRIVATE_KEY is required
```

**Solution:**
```bash
# Generate a test wallet
uv run python scripts/generate_test_wallet.py

# Copy and run the export commands from the output
export ADDR=0x...
export PRIVATE_KEY=0x...
```

### Authentication Failed

```
HTTP error calling http://localhost:3000/api/v1/auth/login: 401
```

**Possible causes:**
- Invalid private key
- Challenge expired (challenges are time-limited)
- Signature mismatch

**Solution:**
- Verify your private key is correct
- Run the script again to get a fresh challenge
- Ensure the address matches the private key

### Module Not Found

```
ModuleNotFoundError: No module named 'eth_account'
```

**Solution:**
```bash
cd backend
uv pip install eth-account
```

---

## Security Best Practices

1. **Use Test Wallets Only**
   - Never use wallets with real funds for testing
   - Generate dedicated test wallets for development

2. **Protect Private Keys**
   - Never commit private keys to version control
   - Use environment variables or `.env` files
   - Add `.env` to `.gitignore`

3. **Secure Storage**
   - Store private keys in secure key management systems
   - Use hardware wallets for production
   - Rotate keys regularly

4. **Network Security**
   - Use HTTPS in production
   - Implement rate limiting
   - Monitor for suspicious activity

5. **Token Management**
   - Tokens expire after 240 minutes (default)
   - Store tokens securely
   - Implement token refresh mechanisms

---

## See Also

- [API Authentication Documentation](../../docs/API_AUTH.md)
- [Environment Variables](../../docs/ENVIRONMENT_VARIABLES.md)
- [API Documentation](http://localhost:3000/docs) (when backend is running)

