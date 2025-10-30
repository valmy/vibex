# API Authentication

This document describes the authentication system for the AI Trading Agent API.

## Overview

The API uses wallet-based authentication with Ethereum addresses. Users authenticate by signing a challenge message with their private key, proving ownership of the wallet address.

## Authentication Flow

### 1. Request a Challenge

To begin authentication, request a challenge message for the user's wallet address.

**Endpoint:** `POST /api/v1/auth/challenge`
**Query Parameters:**
- `address` (string, required): The Ethereum wallet address to authenticate

**Example Request:**
```bash
curl -X POST "http://localhost:3000/api/v1/auth/challenge?address=0xCfE0358A18a20790c49F35c09A120083f1882045"
```

**Response:**
```json
{
  "challenge": "37124602975658db84981bd4c9c88f1da3f7f6114e8085a2966989900277f456"
}
```

### 2. Sign the Challenge

The client needs to sign the challenge message with the private key corresponding to the wallet address. This produces a signature.

### 3. Login with Signature

Submit the signed challenge to authenticate and receive a JWT token.

**Endpoint:** `POST /api/v1/auth/login`
**Query Parameters:**
- `challenge` (string, required): The challenge message received in step 1
- `signature` (string, required): The signature produced in step 2 (0x-prefixed hex)
- `address` (string, required): The Ethereum wallet address

**Example Request:**
```bash
curl -X POST "http://localhost:3000/api/v1/auth/login?challenge=37124602975658db84981bd4c9c88f1da3f7f6114e8085a2966989900277f456&signature=0x...&address=0xCfE0358A18a20790c49F35c09A120083f1882045"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 4. Use the Token

Include the JWT token in the `Authorization` header for authenticated requests:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Using Swagger UI (Bearer token)

The API docs now use a simple HTTP Bearer token scheme (no username/password form). To authenticate in Swagger:

1. Complete the challenge + login steps to obtain a JWT.
2. Click "Authorize" in Swagger.
3. Paste the JWT as the Bearer token and confirm.

Swagger will then send the `Authorization: Bearer <token>` header for protected requests.

### Signing From Terminal (no frontend)

You can complete the challenge-response flow entirely from the terminal. Below is a Python-based option that uses `eth-account` to produce a personal_sign (EIP-191) signature.

Prerequisites:

- Python environment with `uv` available
- `jq` for parsing JSON (optional but recommended)

Steps:

```bash
# 1) Install dependency
uv pip install eth-account

# 2) Request challenge
ADDR=0xYourAddressHere
CHALLENGE=$(curl -s -X POST "http://localhost:3000/api/v1/auth/challenge?address=$ADDR" | jq -r .challenge)

# 3) Sign challenge with your wallet's private key (personal_sign / EIP-191)
# IMPORTANT: Use a dedicated dev wallet and keep your key secure
SIG=$(python - <<'PY'
import os
from eth_account import Account
from eth_account.messages import encode_defunct

private_key = os.environ["PRIVATE_KEY"]  # set securely in your environment
challenge = os.environ["CHALLENGE"]

message = encode_defunct(text=challenge)
sig = Account.sign_message(message, private_key=private_key).signature.hex()
if not sig.startswith("0x"):
    sig = "0x" + sig
print(sig)
PY
)

# 4) Login to receive JWT (query parameters)
curl -s -X POST "http://localhost:3000/api/v1/auth/login?challenge=$CHALLENGE&signature=$SIG&address=$ADDR"

# Paste the returned access_token into Swagger's Authorize dialog as a Bearer token
```

Security tips:

1. Prefer a dedicated development wallet and short-lived shells when handling keys.
2. Avoid committing or storing raw private keys; use environment variables or a key manager.
3. Consider hardware wallets or agent-based signing for production workflows.

### Automated CLI sign-and-login

A helper script `backend/scripts/sign.py` automates the full flow (request challenge → sign → login). It prints the JWT and a ready-to-use curl header export. The script ensures the signature is 0x-prefixed and sends parameters as query items.

Usage:

```bash
cd backend

# Configure environment (use a dev wallet only)
export API_BASE=http://localhost:3000   # optional; defaults to http://localhost:3000
export ADDR=0xYourAddressHere
export PRIVATE_KEY=0xYourPrivateKeyHex

# Run the script
uv run python scripts/sign.py

# Output includes the token and a helper export like:
# export AUTH='Authorization: Bearer <token>'
# Then you can call protected endpoints, e.g.:
# curl -H "$AUTH" "$API_BASE/api/v1/auth/me"
```

## Authorization

The system supports role-based access control:

- **Regular Users**: Can access their own data and perform trading operations
- **Admin Users**: Have additional privileges to modify system settings and manage other users

The first user to authenticate is automatically granted admin privileges.

## Protected Endpoints

Certain endpoints require authentication:

- `GET /api/v1/auth/me` - Get current user information
- All trading-related endpoints (accounts, positions, orders, etc.)

Some endpoints require admin privileges:

- User management
- System configuration changes
- Certain administrative trading operations

## Security Notes

1. Challenge messages are single-use and time-limited
2. JWT tokens have a configurable expiration time (default: 30 minutes)
3. All communication should use HTTPS in production
4. Private keys should never be shared or stored in plaintext

## Implementation Details

### New Files Added

1. **`backend/src/app/api/routes/auth.py`** - Authentication routes
2. **`backend/src/app/core/security.py`** - Security utilities for JWT handling
3. **`backend/src/app/middleware.py`** - Admin-only access middleware
4. **`backend/src/app/models/challenge.py`** - Challenge model for storing pending authentications
5. **`backend/src/app/schemas/auth.py`** - Authentication request/response schemas
6. **`backend/src/app/services/auth_service.py`** - Authentication business logic

### Modified Files

1. **`backend/src/app/models/account.py`** - Added User model and relationship to Account
2. **`backend/src/app/schemas/account.py`** - Added User schemas
3. **`backend/src/app/main.py`** - Integrated auth routes and middleware
4. **`backend/pyproject.toml`** - Added authentication dependencies
5. **`backend/.env.example`** - Added JWT configuration settings

### Key Features

- Wallet-based authentication using cryptographic signatures
- JWT token-based session management
- Role-based access control with admin privileges
- Automatic admin assignment for the first authenticated user
- Secure challenge-response authentication flow
- Middleware protection for admin-only endpoints

## Dependencies

The authentication system requires the following dependencies:

- `python-jose[cryptography]` - For JWT token handling
- `passlib[bcrypt]` - For password hashing (future use)
- `web3` - For Ethereum address validation

## Configuration

JWT settings can be configured via environment variables:

- `SECRET_KEY` - Secret key for signing JWT tokens
- `ALGORITHM` - Algorithm for signing tokens (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration time (default: 30)