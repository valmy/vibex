#!/bin/bash
# Demo script for automated CLI login using the sign.py script
# This demonstrates the wallet-based authentication flow

set -e  # Exit on error

echo "=========================================="
echo "AI Trading Agent - Automated CLI Login Demo"
echo "=========================================="
echo ""

# Check if backend is running
echo "[1/5] Checking if backend is running..."
API_BASE="${API_BASE:-http://localhost:3000}"
if ! curl -s -f "$API_BASE/health" > /dev/null 2>&1; then
    echo "ERROR: Backend is not running at $API_BASE"
    echo "Please start the backend first:"
    echo "  cd backend && podman-compose up -d"
    exit 1
fi
echo "✓ Backend is running at $API_BASE"
echo ""

# Check if we have a test wallet configured
echo "[2/5] Checking wallet configuration..."
if [ -z "$ADDR" ] || [ -z "$PRIVATE_KEY" ]; then
    echo "WARNING: No wallet configured in environment variables"
    echo ""
    echo "You need to set ADDR and PRIVATE_KEY environment variables."
    echo ""
    echo "For testing purposes, you can use the test wallet from the database:"
    echo "  export ADDR=0xCfbEE662dc66475Bf5F3b7203b4b6EE03028952F"
    echo "  export PRIVATE_KEY=<your_test_private_key>"
    echo ""
    echo "Or generate a new test wallet using Python:"
    echo "  python3 -c 'from eth_account import Account; acc = Account.create(); print(f\"Address: {acc.address}\"); print(f\"Private Key: {acc.key.hex()}\")'"
    echo ""
    echo "SECURITY WARNING: Only use test wallets for development!"
    echo "Never use real wallets with funds for testing!"
    exit 1
fi
echo "✓ Wallet configured: $ADDR"
echo ""

# Run the automated sign.py script
echo "[3/5] Running automated login script..."
echo "This will:"
echo "  1. Request a challenge from the API"
echo "  2. Sign the challenge with your private key"
echo "  3. Login and receive a JWT token"
echo ""

cd "$(dirname "$0")/.."  # Change to backend directory

# Run sign.py and capture output
OUTPUT=$(uv run python scripts/sign.py 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: Login failed!"
    echo "$OUTPUT"
    exit 1
fi

# Extract the token (first line of output)
TOKEN=$(echo "$OUTPUT" | head -1)
echo "✓ Login successful!"
echo ""

# Display the token and usage instructions
echo "[4/5] JWT Token received:"
echo "----------------------------------------"
echo "$TOKEN"
echo "----------------------------------------"
echo ""

# Export for curl usage
export AUTH="Authorization: Bearer $TOKEN"
echo "[5/5] Testing authenticated endpoint..."
echo ""

# Test the /api/v1/auth/me endpoint
echo "Calling GET /api/v1/auth/me..."
ME_RESPONSE=$(curl -s -H "$AUTH" "$API_BASE/api/v1/auth/me")
echo "Response:"
echo "$ME_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$ME_RESPONSE"
echo ""

echo "=========================================="
echo "✓ Demo Complete!"
echo "=========================================="
echo ""
echo "You can now use the token for authenticated requests:"
echo ""
echo "  export AUTH='Authorization: Bearer $TOKEN'"
echo ""
echo "Examples:"
echo "  # Get current user info"
echo "  curl -H \"\$AUTH\" $API_BASE/api/v1/auth/me"
echo ""
echo "  # Generate trading decision"
echo "  curl -X POST -H \"\$AUTH\" -H \"Content-Type: application/json\" \\"
echo "    $API_BASE/api/v1/decisions/generate \\"
echo "    -d '{\"symbol\": \"BTCUSDT\", \"account_id\": 1}'"
echo ""
echo "  # List accounts"
echo "  curl -H \"\$AUTH\" $API_BASE/api/v1/accounts"
echo ""

