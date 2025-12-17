"""
E2E tests for account management API endpoints.

Tests the complete account management API with real database integration,
including create, list, get, update, delete, and sync-balance endpoints.

**Feature: account-management**
**Validates: Requirements 11.5, 11.6, 11.7**
"""

import logging
from datetime import datetime

import pytest
import pytest_asyncio
from eth_account import Account as EthAccount
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.main import app
from app.models.account import Account, User

logger = logging.getLogger(__name__)

# High IDs for test data (to avoid conflicts with real data)
TEST_USER_ID_BASE = 2000000
TEST_ACCOUNT_ID_BASE = 3000000


class TestAccountManagementAPIE2E:
    """E2E tests for account management API with real database."""

    @pytest_asyncio.fixture
    async def client(self):
        """Create async HTTP client for testing."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    def get_auth_headers(self):
        """Create a helper function to generate JWT auth headers for a user."""

        def _get_headers(user: User) -> dict:
            """Generate Authorization header with JWT token for the given user."""
            token = create_access_token(data={"sub": user.address})
            return {"Authorization": f"Bearer {token}"}

        return _get_headers

    @pytest_asyncio.fixture
    async def test_users(self, db_session):
        """
        Create test users with real Ethereum addresses.

        Generates 3 test users:
        - User 0: Regular user (account owner)
        - User 1: Regular user (non-owner)
        - User 2: Admin user
        """
        created_users = []
        try:
            # First, clean up any existing test users and accounts from previous runs
            try:
                await db_session.execute(delete(Account).where(Account.id >= TEST_ACCOUNT_ID_BASE))
                await db_session.execute(delete(User).where(User.id >= TEST_USER_ID_BASE))
                await db_session.commit()
                logger.info("Cleaned up existing test data")
            except Exception as e:
                logger.warning(f"Error cleaning up existing test data: {e}")
                await db_session.rollback()

            for i in range(3):
                # Generate a real Ethereum account
                eth_account = EthAccount.create()
                address = eth_account.address

                # Create user with high ID
                user = User(
                    id=TEST_USER_ID_BASE + i,
                    address=address,
                    is_admin=(i == 2),  # Third user is admin
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db_session.add(user)
                created_users.append(user)

            await db_session.commit()
            logger.info(f"Created {len(created_users)} test users")
            yield created_users

        finally:
            # Cleanup: delete test users and accounts
            if created_users:
                try:
                    # Delete accounts first (foreign key constraint)
                    await db_session.execute(
                        delete(Account).where(Account.id >= TEST_ACCOUNT_ID_BASE)
                    )
                    # Then delete users
                    user_ids_to_delete = [user.id for user in created_users]
                    delete_stmt = delete(User).where(User.id.in_(user_ids_to_delete))
                    await db_session.execute(delete_stmt)
                    await db_session.commit()
                    logger.info("Cleaned up test users and accounts")
                except Exception as e:
                    logger.warning(f"Error cleaning up test users: {e}")
                    await db_session.rollback()

    @pytest_asyncio.fixture
    async def test_accounts(self, db_session, test_users):
        """
        Create test accounts for the test users.

        Creates 2 accounts for user 0 (owner).
        """
        created_accounts = []
        try:
            owner = test_users[0]

            # Account 1: Paper trading account
            account1 = Account(
                id=TEST_ACCOUNT_ID_BASE,
                name=f"Test Paper Account {TEST_ACCOUNT_ID_BASE}",
                description="Test paper trading account",
                user_id=owner.id,
                status="active",
                is_paper_trading=True,
                balance_usd=10000.0,
                leverage=2.0,
                max_position_size_usd=5000.0,
                risk_per_trade=0.02,
                is_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db_session.add(account1)
            created_accounts.append(account1)

            # Account 2: Real trading account with credentials
            account2 = Account(
                id=TEST_ACCOUNT_ID_BASE + 1,
                name=f"Test Real Account {TEST_ACCOUNT_ID_BASE + 1}",
                description="Test real trading account",
                user_id=owner.id,
                status="active",
                is_paper_trading=False,
                api_key="test_api_key_123",
                api_secret="test_api_secret_456",
                balance_usd=5000.0,
                leverage=3.0,
                max_position_size_usd=3000.0,
                risk_per_trade=0.03,
                is_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db_session.add(account2)
            created_accounts.append(account2)

            await db_session.commit()
            logger.info(f"Created {len(created_accounts)} test accounts")
            yield created_accounts

        finally:
            # Cleanup: delete test accounts
            if created_accounts:
                try:
                    account_ids_to_delete = [acc.id for acc in created_accounts]
                    delete_stmt = delete(Account).where(Account.id.in_(account_ids_to_delete))
                    await db_session.execute(delete_stmt)
                    await db_session.commit()
                    logger.info("Cleaned up test accounts")
                except Exception as e:
                    logger.warning(f"Error cleaning up test accounts: {e}")
                    await db_session.rollback()

    # ========================================================================
    # Test POST /api/v1/accounts - Create Account
    # ========================================================================

    @pytest.mark.asyncio
    async def test_create_account_for_authenticated_user(
        self, client, test_users, get_auth_headers, db_session
    ):
        """
        Test POST /api/v1/accounts creates account for authenticated user.

        **Feature: account-management**
        **Validates: Requirement 11.5**
        """
        owner = test_users[0]
        headers = get_auth_headers(owner)

        # Create a paper trading account
        account_data = {
            "name": f"E2E Test Account {datetime.utcnow().timestamp()}",
            "description": "E2E test account",
            "is_paper_trading": True,
            "balance_usd": 15000.0,
            "leverage": 2.5,
            "max_position_size_usd": 7500.0,
            "risk_per_trade": 0.025,
        }

        response = await client.post("/api/v1/accounts", json=account_data, headers=headers)

        assert (
            response.status_code == 201
        ), f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()

        # Verify response data
        assert data["name"] == account_data["name"]
        assert data["description"] == account_data["description"]
        assert data["user_id"] == owner.id
        assert data["is_paper_trading"] is True
        assert data["balance_usd"] == 15000.0
        assert data["leverage"] == 2.5
        assert data["status"] == "active"
        assert data["has_api_credentials"] is False

        # Cleanup: delete the created account
        try:
            account_id = data["id"]
            delete_stmt = delete(Account).where(Account.id == account_id)
            await db_session.execute(delete_stmt)
            await db_session.commit()
        except Exception as e:
            logger.warning(f"Error cleaning up created account: {e}")

    # ========================================================================
    # Test GET /api/v1/accounts - List Accounts
    # ========================================================================

    @pytest.mark.asyncio
    async def test_list_accounts_returns_only_user_accounts(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test GET /api/v1/accounts returns only user's accounts.

        **Feature: account-management**
        **Validates: Requirement 11.5**
        """
        owner = test_users[0]
        headers = get_auth_headers(owner)

        response = await client.get("/api/v1/accounts", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

        # Verify all accounts belong to the owner
        for account in data["items"]:
            assert account["user_id"] == owner.id

        # Verify our test accounts are in the list
        account_ids = {acc["id"] for acc in data["items"]}
        assert TEST_ACCOUNT_ID_BASE in account_ids
        assert TEST_ACCOUNT_ID_BASE + 1 in account_ids

    # ========================================================================
    # Test GET /api/v1/accounts/{id} - Get Account
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_account_as_owner_returns_200(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test GET /api/v1/accounts/{id} as owner returns 200 OK.

        **Feature: account-management**
        **Validates: Requirement 11.6**
        """
        owner = test_users[0]
        headers = get_auth_headers(owner)
        account = test_accounts[0]

        response = await client.get(f"/api/v1/accounts/{account.id}", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify account data
        assert data["id"] == account.id
        assert data["name"] == account.name
        assert data["user_id"] == owner.id
        assert data["is_paper_trading"] == account.is_paper_trading

    @pytest.mark.asyncio
    async def test_get_account_as_non_owner_returns_403(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test GET /api/v1/accounts/{id} as non-owner returns 403 Forbidden.

        **Feature: account-management**
        **Validates: Requirement 11.7**
        """
        non_owner = test_users[1]  # Regular user, not owner
        headers = get_auth_headers(non_owner)
        account = test_accounts[0]  # Owned by test_users[0]

        response = await client.get(f"/api/v1/accounts/{account.id}", headers=headers)

        assert response.status_code == 403
        data = response.json()
        assert (
            "does not have access" in data["detail"].lower()
            or "forbidden" in data["detail"].lower()
        )

    @pytest.mark.asyncio
    async def test_get_account_as_admin_returns_200(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test GET /api/v1/accounts/{id} as admin returns 200 OK.

        **Feature: account-management**
        **Validates: Requirement 11.6**
        """
        admin = test_users[2]  # Admin user
        headers = get_auth_headers(admin)
        account = test_accounts[0]  # Owned by test_users[0], not admin

        response = await client.get(f"/api/v1/accounts/{account.id}", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify admin can access any account
        assert data["id"] == account.id
        assert data["name"] == account.name

    # ========================================================================
    # Test PUT /api/v1/accounts/{id} - Update Account
    # ========================================================================

    @pytest.mark.asyncio
    async def test_update_account_as_owner_returns_200(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test PUT /api/v1/accounts/{id} as owner returns 200 OK.

        **Feature: account-management**
        **Validates: Requirement 11.6**
        """
        owner = test_users[0]
        headers = get_auth_headers(owner)
        account = test_accounts[0]

        # Update account data
        update_data = {
            "description": "Updated description",
            "leverage": 4.0,
            "max_position_size_usd": 8000.0,
        }

        response = await client.put(
            f"/api/v1/accounts/{account.id}", json=update_data, headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify updates
        assert data["id"] == account.id
        assert data["description"] == "Updated description"
        assert data["leverage"] == 4.0
        assert data["max_position_size_usd"] == 8000.0

    @pytest.mark.asyncio
    async def test_update_account_as_non_owner_returns_403(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test PUT /api/v1/accounts/{id} as non-owner returns 403 Forbidden.

        **Feature: account-management**
        **Validates: Requirement 11.7**
        """
        non_owner = test_users[1]  # Regular user, not owner
        headers = get_auth_headers(non_owner)
        account = test_accounts[0]  # Owned by test_users[0]

        update_data = {"description": "Unauthorized update"}

        response = await client.put(
            f"/api/v1/accounts/{account.id}", json=update_data, headers=headers
        )

        assert response.status_code == 403
        data = response.json()
        assert (
            "does not have access" in data["detail"].lower()
            or "forbidden" in data["detail"].lower()
        )

    # ========================================================================
    # Test DELETE /api/v1/accounts/{id} - Delete Account
    # ========================================================================

    @pytest.mark.asyncio
    async def test_delete_account_as_owner_returns_204(
        self, client, test_users, get_auth_headers, db_session
    ):
        """
        Test DELETE /api/v1/accounts/{id} as owner returns 204 No Content.

        **Feature: account-management**
        **Validates: Requirement 11.6**
        """
        owner = test_users[0]
        headers = get_auth_headers(owner)

        # Create a temporary account to delete
        temp_account = Account(
            id=TEST_ACCOUNT_ID_BASE + 100,
            name=f"Temp Delete Account {datetime.utcnow().timestamp()}",
            user_id=owner.id,
            status="active",
            is_paper_trading=True,
            balance_usd=1000.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(temp_account)
        await db_session.commit()

        # Delete the account
        response = await client.delete(f"/api/v1/accounts/{temp_account.id}", headers=headers)

        assert response.status_code == 204

        # Verify account is deleted
        result = await db_session.execute(select(Account).where(Account.id == temp_account.id))
        deleted_account = result.scalar_one_or_none()
        assert deleted_account is None

    @pytest.mark.asyncio
    async def test_delete_account_as_non_owner_returns_403(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test DELETE /api/v1/accounts/{id} as non-owner returns 403 Forbidden.

        **Feature: account-management**
        **Validates: Requirement 11.7**
        """
        non_owner = test_users[1]  # Regular user, not owner
        headers = get_auth_headers(non_owner)
        account = test_accounts[0]  # Owned by test_users[0]

        response = await client.delete(f"/api/v1/accounts/{account.id}", headers=headers)

        assert response.status_code == 403
        data = response.json()
        assert (
            "does not have access" in data["detail"].lower()
            or "forbidden" in data["detail"].lower()
        )

    # ========================================================================
    # Test POST /api/v1/accounts/{id}/sync-balance - Sync Balance
    # ========================================================================

    @pytest.mark.asyncio
    async def test_sync_balance_for_paper_trading_returns_400(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test POST /api/v1/accounts/{id}/sync-balance for paper trading returns 400 error.

        **Feature: account-management**
        **Validates: Requirement 11.5**
        """
        owner = test_users[0]
        headers = get_auth_headers(owner)
        paper_account = test_accounts[0]  # Paper trading account

        response = await client.post(
            f"/api/v1/accounts/{paper_account.id}/sync-balance", headers=headers
        )

        assert response.status_code == 400
        data = response.json()
        assert "paper trading" in data["detail"].lower() or "not allowed" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_sync_balance_for_real_trading_with_invalid_credentials(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test POST /api/v1/accounts/{id}/sync-balance for real trading with invalid credentials.

        Note: This test expects the sync to fail because the test credentials are not valid
        for the actual AsterDEX API. We're testing that the endpoint properly attempts to
        sync and returns an appropriate error.

        **Feature: account-management**
        **Validates: Requirement 11.5**
        """
        owner = test_users[0]
        headers = get_auth_headers(owner)
        real_account = test_accounts[1]  # Real trading account with test credentials

        response = await client.post(
            f"/api/v1/accounts/{real_account.id}/sync-balance", headers=headers
        )

        # Expect either 401 (invalid credentials) or 502 (API error)
        # Both are acceptable since we're using test credentials
        assert response.status_code in [
            401,
            502,
        ], f"Expected 401 or 502, got {response.status_code}: {response.text}"
