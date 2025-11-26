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

### Authentication Required

The following endpoints require authentication:

- `GET /api/v1/auth/me` - Get current user information
- **Write Operations** (POST/PUT/DELETE) for trading endpoints:
  - `POST /api/v1/accounts` - Create account
  - `PUT /api/v1/accounts/{id}` - Update account
  - `DELETE /api/v1/accounts/{id}` - Delete account
  - `POST /api/v1/positions` - Create position
  - `PUT /api/v1/positions/{id}` - Update position
  - `DELETE /api/v1/positions/{id}` - Delete position
  - `POST /api/v1/orders` - Create order
  - `PUT /api/v1/orders/{id}` - Update order
  - `DELETE /api/v1/orders/{id}` - Delete order
- **Market Data** write operations:
  - `POST /api/v1/market-data/sync/{symbol}` - Sync market data for symbol
  - `POST /api/v1/market-data/sync-all` - Sync all market data

### Public Endpoints (No Authentication Required)

The following endpoints are publicly accessible:

- **Read Operations** (GET) for trading data:
  - `GET /api/v1/accounts` - List accounts
  - `GET /api/v1/accounts/{id}` - Get account details
  - `GET /api/v1/positions` - List positions
  - `GET /api/v1/positions/{id}` - Get position details
  - `GET /api/v1/orders` - List orders
  - `GET /api/v1/orders/{id}` - Get order details
  - `GET /api/v1/trades` - List trades (read-only)
  - `GET /api/v1/trades/{id}` - Get trade details (read-only)
- **Market Data** read endpoints:
  - `GET /api/v1/market-data` - List market data
  - `GET /api/v1/market-data/{id}` - Get market data details
  - `GET /api/v1/market-data/symbol/{symbol}` - Get market data by symbol
  - `GET /api/v1/market-data/range/{symbol}` - Get market data range
- **System** endpoints (health, status)

### Admin-Only Endpoints

Some endpoints require admin privileges:

- User management operations
- System configuration changes
- Certain administrative trading operations

## User Management Endpoints

The following endpoints allow admin users to manage other users and their admin status. All user management endpoints require admin authentication.

### List All Users

**Endpoint:** `GET /api/v1/users`

**Authentication:** Required (Admin only)

**Query Parameters:**

- `skip` (integer, optional): Number of users to skip for pagination. Default: 0
- `limit` (integer, optional): Maximum number of users to return. Default: 100

**Example Request:**

```bash
curl -X GET "http://localhost:3000/api/v1/users?skip=0&limit=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Success Response (200 OK):**

```json
{
  "users": [
    {
      "id": 1,
      "address": "0x1234567890123456789012345678901234567890",
      "is_admin": true,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    },
    {
      "id": 2,
      "address": "0x0987654321098765432109876543210987654321",
      "is_admin": false,
      "created_at": "2025-01-02T10:30:00Z",
      "updated_at": "2025-01-02T10:30:00Z"
    }
  ],
  "total": 42,
  "skip": 0,
  "limit": 10
}
```

**Error Responses:**

- **401 Unauthorized**: Missing or invalid JWT token
  ```json
  {
    "detail": "Not authenticated"
  }
  ```

- **403 Forbidden**: User is not an admin
  ```json
  {
    "detail": "Admin privileges required"
  }
  ```

- **422 Unprocessable Entity**: Invalid pagination parameters
  ```json
  {
    "detail": "skip must be non-negative"
  }
  ```

### Get User Details

**Endpoint:** `GET /api/v1/users/{user_id}`

**Authentication:** Required (Admin only)

**Path Parameters:**

- `user_id` (integer, required): The ID of the user to retrieve

**Example Request:**

```bash
curl -X GET "http://localhost:3000/api/v1/users/1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Success Response (200 OK):**

```json
{
  "id": 1,
  "address": "0x1234567890123456789012345678901234567890",
  "is_admin": true,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

**Error Responses:**

- **401 Unauthorized**: Missing or invalid JWT token
  ```json
  {
    "detail": "Not authenticated"
  }
  ```

- **403 Forbidden**: User is not an admin
  ```json
  {
    "detail": "Admin privileges required"
  }
  ```

- **404 Not Found**: User does not exist
  ```json
  {
    "detail": "User with id 999 not found"
  }
  ```

### Promote User to Admin

**Endpoint:** `PUT /api/v1/users/{user_id}/promote`

**Authentication:** Required (Admin only)

**Path Parameters:**

- `user_id` (integer, required): The ID of the user to promote

**Description:** Grants admin privileges to the specified user, allowing them to manage other users and access admin-only endpoints.

**Example Request:**

```bash
curl -X PUT "http://localhost:3000/api/v1/users/2/promote" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Success Response (200 OK):**

```json
{
  "id": 2,
  "address": "0x0987654321098765432109876543210987654321",
  "is_admin": true,
  "created_at": "2025-01-02T10:30:00Z",
  "updated_at": "2025-01-02T15:45:00Z"
}
```

**Error Responses:**

- **401 Unauthorized**: Missing or invalid JWT token
  ```json
  {
    "detail": "Not authenticated"
  }
  ```

- **403 Forbidden**: User is not an admin
  ```json
  {
    "detail": "Admin privileges required"
  }
  ```

- **404 Not Found**: User does not exist
  ```json
  {
    "detail": "User with id 999 not found"
  }
  ```

### Revoke Admin Status

**Endpoint:** `PUT /api/v1/users/{user_id}/revoke`

**Authentication:** Required (Admin only)

**Path Parameters:**

- `user_id` (integer, required): The ID of the user to revoke admin status from

**Description:** Removes admin privileges from the specified user, restricting them to regular user access.

**Example Request:**

```bash
curl -X PUT "http://localhost:3000/api/v1/users/2/revoke" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Success Response (200 OK):**

```json
{
  "id": 2,
  "address": "0x0987654321098765432109876543210987654321",
  "is_admin": false,
  "created_at": "2025-01-02T10:30:00Z",
  "updated_at": "2025-01-02T16:00:00Z"
}
```

**Error Responses:**

- **401 Unauthorized**: Missing or invalid JWT token
  ```json
  {
    "detail": "Not authenticated"
  }
  ```

- **403 Forbidden**: User is not an admin
  ```json
  {
    "detail": "Admin privileges required"
  }
  ```

- **404 Not Found**: User does not exist
  ```json
  {
    "detail": "User with id 999 not found"
  }
  ```

## Admin-Only Endpoints Summary

The following table summarizes all admin-only endpoints:

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|----------------|
| GET | `/api/v1/users` | List all users with pagination | Admin |
| GET | `/api/v1/users/{user_id}` | Get specific user details | Admin |
| PUT | `/api/v1/users/{user_id}/promote` | Promote user to admin | Admin |
| PUT | `/api/v1/users/{user_id}/revoke` | Revoke admin status | Admin |

## Account Management Endpoints

The following endpoints allow users to manage their trading accounts. Regular users can only access their own accounts, while admin users can access any account.

### Account Ownership Rules

- **Regular Users**: Can only create, read, update, and delete their own accounts
- **Admin Users**: Can read, update, and delete any account (but cannot create accounts for other users)
- **Account Association**: Accounts are automatically associated with the authenticated user who creates them

### Trading Modes

Accounts support two trading modes:

1. **Paper Trading** (`is_paper_trading: true`)
   - Simulated trading with virtual funds
   - Requires `balance_usd` to be set
   - No API credentials required
   - Cannot sync balance from exchange

2. **Real Trading** (`is_paper_trading: false`)
   - Live trading with real funds
   - Requires `api_key` and `api_secret` for AsterDEX API
   - Balance synced from exchange via API
   - API credentials are encrypted and masked in responses

### Account Status States

Accounts can be in one of three states:

- **active**: Account is actively trading
- **paused**: Trading is temporarily suspended, positions remain open
- **stopped**: Trading is stopped, all positions should be closed

Status transitions are validated:
- `active` → `paused` or `stopped`
- `paused` → `active` or `stopped`
- `stopped` → `active` (requires valid credentials for real trading)

### Create Account

**Endpoint:** `POST /api/v1/accounts`

**Authentication:** Required (Regular user or Admin)

**Request Body:**

```json
{
  "name": "My Trading Account",
  "description": "Main trading account for BTC/ETH",
  "is_paper_trading": true,
  "balance_usd": 10000.0,
  "leverage": 2.0,
  "max_position_size_usd": 5000.0,
  "risk_per_trade": 0.02
}
```

**For Real Trading:**

```json
{
  "name": "Live Trading Account",
  "description": "Real trading with AsterDEX",
  "is_paper_trading": false,
  "leverage": 3.0,
  "max_position_size_usd": 10000.0,
  "risk_per_trade": 0.01,
  "api_key": "your-asterdex-api-key",
  "api_secret": "your-asterdex-api-secret"
}
```

**Example Request:**

```bash
curl -X POST "http://localhost:3000/api/v1/accounts" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Trading Account",
    "description": "Main trading account",
    "is_paper_trading": true,
    "balance_usd": 10000.0,
    "leverage": 2.0,
    "max_position_size_usd": 5000.0,
    "risk_per_trade": 0.02
  }'
```

**Success Response (201 Created):**

```json
{
  "id": 1,
  "name": "My Trading Account",
  "description": "Main trading account",
  "user_id": 1,
  "leverage": 2.0,
  "max_position_size_usd": 5000.0,
  "risk_per_trade": 0.02,
  "balance_usd": 10000.0,
  "is_paper_trading": true,
  "api_key": null,
  "api_secret": null,
  "status": "active",
  "created_at": "2025-11-26T10:00:00Z",
  "updated_at": "2025-11-26T10:00:00Z"
}
```

**Error Responses:**

- **400 Bad Request**: Duplicate account name or validation error
  ```json
  {
    "detail": "Account with name 'My Trading Account' already exists for this user"
  }
  ```

- **400 Bad Request**: Real trading account missing credentials
  ```json
  {
    "detail": "Real trading accounts require api_key and api_secret"
  }
  ```

- **401 Unauthorized**: Missing or invalid JWT token
  ```json
  {
    "detail": "Not authenticated"
  }
  ```

### List Accounts

**Endpoint:** `GET /api/v1/accounts`

**Authentication:** Required (Regular user or Admin)

**Query Parameters:**

- `skip` (integer, optional): Number of accounts to skip for pagination. Default: 0
- `limit` (integer, optional): Maximum number of accounts to return. Default: 100, Max: 1000

**Description:** Returns only accounts owned by the authenticated user. Admin users also only see their own accounts.

**Example Request:**

```bash
curl -X GET "http://localhost:3000/api/v1/accounts?skip=0&limit=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Success Response (200 OK):**

```json
{
  "total": 2,
  "items": [
    {
      "id": 1,
      "name": "My Trading Account",
      "description": "Main trading account",
      "user_id": 1,
      "leverage": 2.0,
      "max_position_size_usd": 5000.0,
      "risk_per_trade": 0.02,
      "balance_usd": 10000.0,
      "is_paper_trading": true,
      "api_key": null,
      "api_secret": null,
      "status": "active",
      "created_at": "2025-11-26T10:00:00Z",
      "updated_at": "2025-11-26T10:00:00Z"
    },
    {
      "id": 2,
      "name": "Live Trading",
      "description": "Real trading account",
      "user_id": 1,
      "leverage": 3.0,
      "max_position_size_usd": 10000.0,
      "risk_per_trade": 0.01,
      "balance_usd": 25000.0,
      "is_paper_trading": false,
      "api_key": "***MASKED***",
      "api_secret": "***MASKED***",
      "status": "active",
      "created_at": "2025-11-26T11:00:00Z",
      "updated_at": "2025-11-26T11:00:00Z"
    }
  ]
}
```

**Error Responses:**

- **401 Unauthorized**: Missing or invalid JWT token

### Get Account Details

**Endpoint:** `GET /api/v1/accounts/{id}`

**Authentication:** Required (Account owner or Admin)

**Path Parameters:**

- `id` (integer, required): The ID of the account to retrieve

**Description:** Returns account details. Regular users can only access their own accounts. Admin users can access any account.

**Example Request:**

```bash
curl -X GET "http://localhost:3000/api/v1/accounts/1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Success Response (200 OK):**

```json
{
  "id": 1,
  "name": "My Trading Account",
  "description": "Main trading account",
  "user_id": 1,
  "leverage": 2.0,
  "max_position_size_usd": 5000.0,
  "risk_per_trade": 0.02,
  "balance_usd": 10000.0,
  "is_paper_trading": true,
  "api_key": null,
  "api_secret": null,
  "status": "active",
  "created_at": "2025-11-26T10:00:00Z",
  "updated_at": "2025-11-26T10:00:00Z"
}
```

**Error Responses:**

- **401 Unauthorized**: Missing or invalid JWT token
- **403 Forbidden**: User does not own this account and is not an admin
  ```json
  {
    "detail": "You do not have access to this account"
  }
  ```

- **404 Not Found**: Account does not exist
  ```json
  {
    "detail": "Account with id 999 not found"
  }
  ```

### Update Account

**Endpoint:** `PUT /api/v1/accounts/{id}`

**Authentication:** Required (Account owner or Admin)

**Path Parameters:**

- `id` (integer, required): The ID of the account to update

**Request Body:**

```json
{
  "name": "Updated Account Name",
  "description": "Updated description",
  "leverage": 2.5,
  "max_position_size_usd": 6000.0,
  "risk_per_trade": 0.015,
  "status": "paused"
}
```

**Example Request:**

```bash
curl -X PUT "http://localhost:3000/api/v1/accounts/1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Account Name",
    "leverage": 2.5,
    "status": "paused"
  }'
```

**Success Response (200 OK):**

```json
{
  "id": 1,
  "name": "Updated Account Name",
  "description": "Main trading account",
  "user_id": 1,
  "leverage": 2.5,
  "max_position_size_usd": 5000.0,
  "risk_per_trade": 0.02,
  "balance_usd": 10000.0,
  "is_paper_trading": true,
  "api_key": null,
  "api_secret": null,
  "status": "paused",
  "created_at": "2025-11-26T10:00:00Z",
  "updated_at": "2025-11-26T12:00:00Z"
}
```

**Error Responses:**

- **400 Bad Request**: Invalid status transition
  ```json
  {
    "detail": "Cannot transition from stopped to paused"
  }
  ```

- **401 Unauthorized**: Missing or invalid JWT token
- **403 Forbidden**: User does not own this account and is not an admin
- **404 Not Found**: Account does not exist

### Delete Account

**Endpoint:** `DELETE /api/v1/accounts/{id}`

**Authentication:** Required (Account owner or Admin)

**Path Parameters:**

- `id` (integer, required): The ID of the account to delete

**Description:** Deletes the account and all associated data (positions, orders, trades). This operation cannot be undone.

**Example Request:**

```bash
curl -X DELETE "http://localhost:3000/api/v1/accounts/1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Success Response (204 No Content):**

No response body.

**Error Responses:**

- **401 Unauthorized**: Missing or invalid JWT token
- **403 Forbidden**: User does not own this account and is not an admin
  ```json
  {
    "detail": "You do not have access to this account"
  }
  ```

- **404 Not Found**: Account does not exist
  ```json
  {
    "detail": "Account with id 999 not found"
  }
  ```

### Sync Balance from Exchange

**Endpoint:** `POST /api/v1/accounts/{id}/sync-balance`

**Authentication:** Required (Account owner or Admin)

**Path Parameters:**

- `id` (integer, required): The ID of the account to sync balance for

**Description:** Syncs the account balance from the AsterDEX exchange API. Only available for real trading accounts (not paper trading).

**Example Request:**

```bash
curl -X POST "http://localhost:3000/api/v1/accounts/1/sync-balance" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Success Response (200 OK):**

```json
{
  "id": 1,
  "name": "Live Trading",
  "description": "Real trading account",
  "user_id": 1,
  "leverage": 3.0,
  "max_position_size_usd": 10000.0,
  "risk_per_trade": 0.01,
  "balance_usd": 26543.21,
  "is_paper_trading": false,
  "api_key": "***MASKED***",
  "api_secret": "***MASKED***",
  "status": "active",
  "created_at": "2025-11-26T11:00:00Z",
  "updated_at": "2025-11-26T13:00:00Z"
}
```

**Error Responses:**

- **400 Bad Request**: Paper trading account cannot sync balance
  ```json
  {
    "detail": "Cannot sync balance for paper trading accounts"
  }
  ```

- **400 Bad Request**: Missing API credentials
  ```json
  {
    "detail": "Account must have valid API credentials to sync balance"
  }
  ```

- **401 Unauthorized**: Missing or invalid JWT token
- **403 Forbidden**: User does not own this account and is not an admin
- **404 Not Found**: Account does not exist
- **502 Bad Gateway**: Failed to connect to AsterDEX API
  ```json
  {
    "detail": "Failed to sync balance from AsterDEX API: Connection timeout"
  }
  ```

### Account Management Endpoints Summary

| Method | Endpoint | Description | Auth Required | Ownership |
|--------|----------|-------------|---------------|-----------|
| POST | `/api/v1/accounts` | Create new account | User/Admin | Creates for authenticated user |
| GET | `/api/v1/accounts` | List user's accounts | User/Admin | Returns only user's accounts |
| GET | `/api/v1/accounts/{id}` | Get account details | User/Admin | Owner or Admin |
| PUT | `/api/v1/accounts/{id}` | Update account | User/Admin | Owner or Admin |
| DELETE | `/api/v1/accounts/{id}` | Delete account | User/Admin | Owner or Admin |
| POST | `/api/v1/accounts/{id}/sync-balance` | Sync balance from exchange | User/Admin | Owner or Admin |

## Common Error Responses

### 401 Unauthorized

Returned when the request lacks valid authentication credentials.

**Causes:**
- Missing `Authorization` header
- Invalid or expired JWT token
- Malformed token format

**Response:**
```json
{
  "detail": "Not authenticated"
}
```

**Solution:** Complete the authentication flow to obtain a valid JWT token and include it in the `Authorization: Bearer <token>` header.

### 403 Forbidden

Returned when the authenticated user lacks the required privileges.

**Causes:**
- Regular user attempting to access admin-only endpoints
- Insufficient permissions for the requested operation

**Response:**
```json
{
  "detail": "Admin privileges required"
}
```

**Solution:** Only admin users can access user management endpoints. Contact a system administrator to request admin privileges.

### 404 Not Found

Returned when the requested resource does not exist.

**Causes:**
- User ID does not exist in the database
- Invalid resource identifier

**Response:**
```json
{
  "detail": "User with id 999 not found"
}
```

**Solution:** Verify the user ID is correct by listing users first with `GET /api/v1/users`.

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
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration time (default: 240)
