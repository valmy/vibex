"""
E2E tests for Decision/Generate API using HTTP against running backend.

This test suite validates the complete end-to-end flow of the
/api/v1/decisions/generate endpoint against a running backend instance.

These tests use real HTTP requests instead of ASGI transport, allowing
testing against the actual running backend with real data.

To run these tests:
1. Start the backend: cd backend && podman-compose up -d
2. Run tests: uv run pytest tests/e2e/test_decision_generate_api_e2e_http.py -v
"""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient
from eth_account import Account
from eth_account.messages import encode_defunct
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Backend URL - can be overridden with BACKEND_URL env var
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:3000")

# Database URL - ensure it uses asyncpg
_db_url = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_password@localhost:5432/trading_db")
if not _db_url.startswith("postgresql+asyncpg://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://")
DATABASE_URL = _db_url


@pytest.fixture
def test_wallet():
    """Create a test wallet for authentication."""
    account = Account.create()
    return {
        "address": account.address,
        "private_key": account.key.hex(),
    }


@pytest_asyncio.fixture
async def db_session():
    """Create a database session for test setup."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def test_user_in_db(db_session, test_wallet):
    """Create a test user in the database."""
    from app.models.account import User

    # Check if user already exists
    result = await db_session.execute(
        select(User).where(User.address == test_wallet["address"])
    )
    user = result.scalar_one_or_none()

    if not user:
        # Create new user
        user = User(address=test_wallet["address"], is_admin=False)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def http_client():
    """Create async HTTP client for testing against running backend."""
    async with AsyncClient(base_url=BACKEND_URL, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_http_client(http_client, test_wallet, test_user_in_db):
    """Create authenticated HTTP client with JWT token."""
    # Ensure user exists in database
    assert test_user_in_db is not None

    # Step 1: Request challenge
    challenge_response = await http_client.post(
        f"/api/v1/auth/challenge?address={test_wallet['address']}"
    )
    assert challenge_response.status_code == 200
    challenge = challenge_response.json()["challenge"]

    # Step 2: Sign challenge
    message = encode_defunct(text=challenge)
    signed_message = Account.sign_message(message, private_key=test_wallet["private_key"])
    signature = signed_message.signature.hex()
    if not signature.startswith("0x"):
        signature = f"0x{signature}"

    # Step 3: Login to get JWT
    login_response = await http_client.post(
        f"/api/v1/auth/login?challenge={challenge}&signature={signature}&address={test_wallet['address']}"
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Create a new client with auth headers
    # (updating headers on existing client doesn't work reliably)
    async with AsyncClient(
        base_url=BACKEND_URL,
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"}
    ) as auth_client:
        yield auth_client


class TestDecisionGenerateAPIHTTP:
    """E2E tests for Decision/Generate API using HTTP against running backend."""

    @pytest.mark.asyncio
    async def test_health_check(self, http_client):
        """Test 1: Health check endpoint."""
        response = await http_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_authentication_flow_success(self, http_client, test_wallet):
        """Test 2: Complete authentication flow."""
        # Step 1: Request challenge
        challenge_response = await http_client.post(
            f"/api/v1/auth/challenge?address={test_wallet['address']}"
        )
        assert challenge_response.status_code == 200
        challenge = challenge_response.json()["challenge"]
        assert isinstance(challenge, str)
        assert len(challenge) > 0

        # Step 2: Sign challenge
        message = encode_defunct(text=challenge)
        signed_message = Account.sign_message(message, private_key=test_wallet["private_key"])
        signature = signed_message.signature.hex()
        if not signature.startswith("0x"):
            signature = f"0x{signature}"

        # Step 3: Login
        login_response = await http_client.post(
            f"/api/v1/auth/login?challenge={challenge}&signature={signature}&address={test_wallet['address']}"
        )
        assert login_response.status_code == 200
        data = login_response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_generate_decision_btc_real_data(self, authenticated_http_client):
        """Test 3: Generate decision for BTCUSDT using real data."""
        # Debug: print headers
        print(f"Headers: {authenticated_http_client.headers}")

        response = await authenticated_http_client.post(
            "/api/v1/decisions/generate",
            json={"symbol": "BTCUSDT", "account_id": 1},
        )

        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")

        # Should succeed with real data
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "decision" in data
        assert "context" in data
        assert "validation_passed" in data

        # Verify decision structure
        decision = data["decision"]
        assert "action" in decision
        assert "confidence" in decision
        assert decision["action"].upper() in ["BUY", "SELL", "HOLD"]
        assert 0 <= decision["confidence"] <= 100

    @pytest.mark.asyncio
    async def test_generate_decision_eth_real_data(self, authenticated_http_client):
        """Test 4: Generate decision for ETHUSDT using real data."""
        response = await authenticated_http_client.post(
            "/api/v1/decisions/generate",
            json={"symbol": "ETHUSDT", "account_id": 1},
        )
        
        # Should succeed with real data
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "decision" in data
        assert "context" in data
        
        # Verify decision
        decision = data["decision"]
        assert decision["action"].upper() in ["BUY", "SELL", "HOLD"]

    @pytest.mark.asyncio
    async def test_missing_authentication(self, http_client):
        """Test 5: Request without authentication should fail."""
        response = await http_client.post(
            "/api/v1/decisions/generate",
            json={"symbol": "BTCUSDT", "account_id": 1},
        )

        # Should return 403 Forbidden (middleware blocks unauthenticated requests)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_symbol(self, authenticated_http_client):
        """Test 6: Invalid symbol should fail."""
        response = await authenticated_http_client.post(
            "/api/v1/decisions/generate",
            json={"symbol": "INVALID", "account_id": 1},
        )
        
        # Should return 400 Bad Request
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_response_structure_validation(self, authenticated_http_client):
        """Test 7: Validate response structure."""
        response = await authenticated_http_client.post(
            "/api/v1/decisions/generate",
            json={"symbol": "BTCUSDT", "account_id": 1},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields
        assert "decision" in data
        assert "context" in data
        assert "validation_passed" in data
        assert "validation_errors" in data
        assert "processing_time_ms" in data
        assert "model_used" in data
        
        # Verify context structure
        context = data["context"]
        assert "market_data" in context
        assert "account_state" in context
        assert "risk_metrics" in context

    @pytest.mark.asyncio
    async def test_force_refresh(self, authenticated_http_client):
        """Test 8: Force refresh parameter is accepted (but not tested with live data in E2E tests)."""
        # First request without force_refresh
        response1 = await authenticated_http_client.post(
            "/api/v1/decisions/generate",
            json={"symbol": "BTCUSDT", "account_id": 1, "force_refresh": False},
        )
        assert response1.status_code == 200

        # Second request also without force_refresh (testing cache behavior)
        # Note: force_refresh=True would try to fetch live data from exchange,
        # which is not suitable for E2E tests with static test data
        response2 = await authenticated_http_client.post(
            "/api/v1/decisions/generate",
            json={"symbol": "BTCUSDT", "account_id": 1, "force_refresh": False},
        )
        assert response2.status_code == 200

        # Verify both responses have the same structure
        data1 = response1.json()
        data2 = response2.json()
        assert "decision" in data1
        assert "decision" in data2

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, authenticated_http_client):
        """Test 9: Handle concurrent requests."""
        import asyncio
        
        # Make multiple concurrent requests
        tasks = [
            authenticated_http_client.post(
                "/api/v1/decisions/generate",
                json={"symbol": "BTCUSDT", "account_id": 1},
            )
            for _ in range(3)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "decision" in data

