"""
E2E tests for strategy management API endpoints.

Tests the complete strategy assignment and switching API with real database integration,
including GET /account/{id}, POST /account/{id}/assign, and POST /account/{id}/switch.

**Feature: strategy-management**
**Validates: Strategy assignment, switching, and retrieval via HTTP API**
"""

import logging
from datetime import datetime

import pytest
import pytest_asyncio
from eth_account import Account as EthAccount
from httpx import ASGITransport, AsyncClient
from sqlalchemy import and_, delete, select

from app.core.security import create_access_token
from app.main import app
from app.models.account import Account, User
from app.models.strategy import StrategyAssignment as StrategyAssignmentModel
from app.services.llm.strategy_manager import StrategyManager

logger = logging.getLogger(__name__)

# High IDs for test data (to avoid conflicts with real data)
TEST_USER_ID_BASE = 4000000
TEST_ACCOUNT_ID_BASE = 5000000


class TestStrategyAPIE2E:
    """E2E tests for strategy API with real database."""

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
            # First, clean up any existing test data from previous runs
            try:
                await db_session.execute(
                    delete(StrategyAssignmentModel).where(
                        StrategyAssignmentModel.account_id >= TEST_ACCOUNT_ID_BASE
                    )
                )
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
            # Cleanup: delete test users, accounts, and assignments
            if created_users:
                try:
                    await db_session.execute(
                        delete(StrategyAssignmentModel).where(
                            StrategyAssignmentModel.account_id >= TEST_ACCOUNT_ID_BASE
                        )
                    )
                    await db_session.execute(
                        delete(Account).where(Account.id >= TEST_ACCOUNT_ID_BASE)
                    )
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
                name=f"Test Strategy Account {TEST_ACCOUNT_ID_BASE}",
                description="Test account for strategy API tests",
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

            # Account 2: Second account for testing
            account2 = Account(
                id=TEST_ACCOUNT_ID_BASE + 1,
                name=f"Test Strategy Account {TEST_ACCOUNT_ID_BASE + 1}",
                description="Second test account for strategy API tests",
                user_id=owner.id,
                status="active",
                is_paper_trading=True,
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
            # Cleanup handled by test_users fixture
            pass

    @pytest_asyncio.fixture
    async def strategy_manager(self, db_session_factory):
        """Create and initialize StrategyManager with predefined strategies."""
        manager = StrategyManager(session_factory=db_session_factory)
        await manager.initialize()
        return manager

    @pytest_asyncio.fixture
    async def assigned_strategy(self, db_session, db_session_factory, test_accounts):
        """Assign a strategy to the first test account."""
        manager = StrategyManager(session_factory=db_session_factory)
        await manager.initialize()

        # Get the first available strategy
        strategies = await manager.get_available_strategies()
        assert len(strategies) > 0, "No strategies available"

        # Assign to first test account
        assignment = await manager.assign_strategy_to_account(
            account_id=test_accounts[0].id,
            strategy_id=strategies[0].strategy_id,
            assigned_by="test_fixture",
            switch_reason="Initial assignment for testing",
        )
        yield {
            "assignment": assignment,
            "strategy": strategies[0],
            "account": test_accounts[0],
            "manager": manager,
            "all_strategies": strategies,
        }

    # ========================================================================
    # GET /api/v1/strategies/account/{account_id} - Happy Path Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_account_strategy_returns_assigned_strategy(
        self, client, test_users, assigned_strategy, get_auth_headers
    ):
        """
        Test GET /api/v1/strategies/account/{account_id} returns assigned strategy.

        **Feature: strategy-management**
        **Test ID: GET_HP_01**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = assigned_strategy["account"].id

        response = await client.get(f"/api/v1/strategies/account/{account_id}", headers=headers)

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        # Verify response contains expected strategy fields
        assert "strategy_id" in data
        assert "strategy_name" in data
        assert "strategy_type" in data
        assert "risk_parameters" in data
        assert data["strategy_id"] == assigned_strategy["strategy"].strategy_id

    @pytest.mark.asyncio
    async def test_get_account_strategy_validates_response_schema(
        self, client, test_users, assigned_strategy, get_auth_headers
    ):
        """
        Test GET /api/v1/strategies/account/{account_id} returns complete schema.

        **Feature: strategy-management**
        **Test ID: GET_HP_02**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = assigned_strategy["account"].id

        response = await client.get(f"/api/v1/strategies/account/{account_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        required_fields = [
            "strategy_id",
            "strategy_name",
            "strategy_type",
            "prompt_template",
            "risk_parameters",
            "timeframe_preference",
            "max_positions",
            "position_sizing",
            "is_active",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    # ========================================================================
    # GET /api/v1/strategies/account/{account_id} - Error Case Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_account_strategy_no_assignment_returns_404(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test GET /api/v1/strategies/account/{account_id} returns 404 when no strategy assigned.

        **Feature: strategy-management**
        **Test ID: GET_ERR_01**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        # Use second account which has no strategy assigned
        account_id = test_accounts[1].id

        response = await client.get(f"/api/v1/strategies/account/{account_id}", headers=headers)

        assert response.status_code == 404
        data = response.json()
        assert "no strategy" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_account_strategy_unauthenticated_returns_401(self, client, test_accounts):
        """
        Test GET /api/v1/strategies/account/{account_id} returns 401/403 without auth.

        **Feature: strategy-management**
        **Test ID: GET_ERR_02**
        Note: This test will fail until Bug #4 is fixed (missing authentication).
        The application returns 403 for unauthenticated requests.
        """
        account_id = test_accounts[0].id

        # No auth headers
        response = await client.get(f"/api/v1/strategies/account/{account_id}")

        # Application returns 403 for unauthenticated requests
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401 or 403, got {response.status_code}: {response.text}"

    # ========================================================================
    # POST /api/v1/strategies/account/{account_id}/assign - Happy Path Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_assign_strategy_first_assignment(
        self, client, test_users, test_accounts, strategy_manager, get_auth_headers
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/assign for first assignment.

        **Feature: strategy-management**
        **Test ID: ASSIGN_HP_01**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = test_accounts[1].id  # Account with no prior assignment

        # Get available strategies
        strategies = await strategy_manager.get_available_strategies()
        assert len(strategies) > 0

        request_data = {
            "strategy_id": strategies[0].strategy_id,
            "assigned_by": "test_admin",
            "switch_reason": "First assignment test",
        }

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/assign",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        assert data["account_id"] == account_id
        assert data["strategy_id"] == strategies[0].strategy_id
        assert data["assigned_by"] == "test_admin"
        assert data["switch_reason"] == "First assignment test"
        assert data["previous_strategy_id"] is None

    @pytest.mark.asyncio
    async def test_assign_strategy_replaces_existing(
        self, client, test_users, assigned_strategy, get_auth_headers, db_session
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/assign replaces existing.

        **Feature: strategy-management**
        **Test ID: ASSIGN_HP_02**
        Note: This test will fail until Bug #2 is fixed (previous_strategy_id returns DB ID).
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = assigned_strategy["account"].id
        current_strategy = assigned_strategy["strategy"]

        # Find a different strategy to assign
        all_strategies = assigned_strategy["all_strategies"]
        new_strategy = next(
            (s for s in all_strategies if s.strategy_id != current_strategy.strategy_id),
            None,
        )
        assert new_strategy is not None, "Need at least 2 strategies for this test"

        request_data = {
            "strategy_id": new_strategy.strategy_id,
            "assigned_by": "test_admin",
            "switch_reason": "Replacing existing strategy",
        }

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/assign",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["account_id"] == account_id
        assert data["strategy_id"] == new_strategy.strategy_id
        # BUG #2: This should be the strategy_id string, not DB ID as string
        assert data["previous_strategy_id"] == current_strategy.strategy_id, (
            f"Expected previous_strategy_id='{current_strategy.strategy_id}', "
            f"got '{data['previous_strategy_id']}'"
        )

    @pytest.mark.asyncio
    async def test_assign_strategy_persists_to_database(
        self, client, test_users, test_accounts, strategy_manager, get_auth_headers, db_session
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/assign persists to DB.

        **Feature: strategy-management**
        **Test ID: ASSIGN_HP_05**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = test_accounts[1].id

        strategies = await strategy_manager.get_available_strategies()
        request_data = {
            "strategy_id": strategies[0].strategy_id,
            "assigned_by": "db_persistence_test",
        }

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/assign",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 200

        # Verify DB state
        await db_session.commit()  # Ensure we see committed data
        result = await db_session.execute(
            select(StrategyAssignmentModel).where(
                and_(
                    StrategyAssignmentModel.account_id == account_id,
                    StrategyAssignmentModel.is_active == True,  # noqa: E712
                )
            )
        )
        db_assignment = result.scalar_one_or_none()
        assert db_assignment is not None
        assert db_assignment.assigned_by == "db_persistence_test"

    # ========================================================================
    # POST /api/v1/strategies/account/{account_id}/assign - Error Case Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_assign_strategy_not_found_returns_400(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/assign returns 400 for invalid strategy.

        **Feature: strategy-management**
        **Test ID: ASSIGN_ERR_01**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = test_accounts[0].id

        request_data = {
            "strategy_id": "nonexistent_strategy_xyz",
            "assigned_by": "test_admin",
        }

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/assign",
            json=request_data,
            headers=headers,
        )

        # 404 is correct for "not found" errors
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_assign_strategy_missing_strategy_id_returns_422(
        self, client, test_users, test_accounts, get_auth_headers
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/assign returns 422 for missing field.

        **Feature: strategy-management**
        **Test ID: ASSIGN_ERR_03**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = test_accounts[0].id

        # Missing strategy_id
        request_data = {"assigned_by": "test_admin"}

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/assign",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_assign_strategy_unauthenticated_returns_401(
        self, client, test_accounts, strategy_manager
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/assign returns 401 without auth.

        **Feature: strategy-management**
        **Test ID: ASSIGN_ERR_05**
        """
        account_id = test_accounts[0].id
        strategies = await strategy_manager.get_available_strategies()

        request_data = {"strategy_id": strategies[0].strategy_id}

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/assign",
            json=request_data,
            # No auth headers
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_assign_strategy_non_admin_returns_403(
        self, client, test_users, test_accounts, strategy_manager, get_auth_headers
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/assign returns 403 for non-admin.

        **Feature: strategy-management**
        **Test ID: ASSIGN_ERR_06**
        """
        regular_user = test_users[0]  # Not admin
        headers = get_auth_headers(regular_user)
        account_id = test_accounts[0].id

        strategies = await strategy_manager.get_available_strategies()
        request_data = {"strategy_id": strategies[0].strategy_id}

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/assign",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_assign_strategy_nonexistent_account_returns_error(
        self, client, test_users, strategy_manager, get_auth_headers
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/assign returns error for non-existent account.

        **Feature: strategy-management**
        **Test ID: ASSIGN_ERR_07**
        Note: This test will fail until Bug #3 is fixed (no account validation).
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        nonexistent_account_id = 99999999

        strategies = await strategy_manager.get_available_strategies()
        request_data = {"strategy_id": strategies[0].strategy_id}

        response = await client.post(
            f"/api/v1/strategies/account/{nonexistent_account_id}/assign",
            json=request_data,
            headers=headers,
        )

        # Should return 400 or 404 for non-existent account
        assert response.status_code in [
            400,
            404,
        ], f"Expected 400 or 404, got {response.status_code}: {response.text}"

    # ========================================================================
    # POST /api/v1/strategies/account/{account_id}/switch - Happy Path Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_switch_strategy_from_one_to_another(
        self, client, test_users, assigned_strategy, get_auth_headers
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/switch successfully switches.

        **Feature: strategy-management**
        **Test ID: SWITCH_HP_01**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = assigned_strategy["account"].id
        current_strategy = assigned_strategy["strategy"]

        # Find a different strategy to switch to
        all_strategies = assigned_strategy["all_strategies"]
        new_strategy = next(
            (s for s in all_strategies if s.strategy_id != current_strategy.strategy_id),
            None,
        )
        assert new_strategy is not None, "Need at least 2 strategies for this test"

        request_data = {
            "strategy_id": new_strategy.strategy_id,
            "switch_reason": "Testing strategy switch",
        }

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/switch",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        assert data["account_id"] == account_id
        assert data["strategy_id"] == new_strategy.strategy_id
        assert data["switch_reason"] == "Testing strategy switch"

    @pytest.mark.asyncio
    async def test_switch_strategy_deactivates_previous(
        self, client, test_users, assigned_strategy, get_auth_headers, db_session
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/switch deactivates previous.

        **Feature: strategy-management**
        **Test ID: SWITCH_HP_02**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = assigned_strategy["account"].id
        current_strategy = assigned_strategy["strategy"]

        # Find a different strategy
        all_strategies = assigned_strategy["all_strategies"]
        new_strategy = next(
            (s for s in all_strategies if s.strategy_id != current_strategy.strategy_id),
            None,
        )
        assert new_strategy is not None

        request_data = {
            "strategy_id": new_strategy.strategy_id,
            "switch_reason": "Testing deactivation",
        }

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/switch",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 200

        # Verify DB state - previous assignment should be deactivated
        await db_session.commit()
        result = await db_session.execute(
            select(StrategyAssignmentModel).where(
                and_(
                    StrategyAssignmentModel.account_id == account_id,
                    StrategyAssignmentModel.is_active == False,  # noqa: E712
                )
            )
        )
        deactivated = result.scalars().all()
        assert len(deactivated) >= 1, "Previous assignment should be deactivated"

    @pytest.mark.asyncio
    async def test_switch_strategy_uses_default_reason(
        self, client, test_users, assigned_strategy, get_auth_headers
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/switch uses default reason.

        **Feature: strategy-management**
        **Test ID: SWITCH_HP_04**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = assigned_strategy["account"].id
        current_strategy = assigned_strategy["strategy"]

        all_strategies = assigned_strategy["all_strategies"]
        new_strategy = next(
            (s for s in all_strategies if s.strategy_id != current_strategy.strategy_id),
            None,
        )
        assert new_strategy is not None

        # No switch_reason provided
        request_data = {"strategy_id": new_strategy.strategy_id}

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/switch",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["switch_reason"] == "API request"  # Default reason

    # ========================================================================
    # POST /api/v1/strategies/account/{account_id}/switch - Error Case Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_switch_strategy_same_strategy_returns_400(
        self, client, test_users, assigned_strategy, get_auth_headers
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/switch returns 400 for same strategy.

        **Feature: strategy-management**
        **Test ID: SWITCH_ERR_03**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = assigned_strategy["account"].id
        current_strategy = assigned_strategy["strategy"]

        # Try to switch to the same strategy
        request_data = {
            "strategy_id": current_strategy.strategy_id,
            "switch_reason": "Should fail - same strategy",
        }

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/switch",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "already using" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_switch_strategy_not_found_returns_404(
        self, client, test_users, assigned_strategy, get_auth_headers
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/switch returns 404 for invalid strategy.

        **Feature: strategy-management**
        **Test ID: SWITCH_ERR_01**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = assigned_strategy["account"].id

        request_data = {
            "strategy_id": "nonexistent_strategy_xyz",
            "switch_reason": "Should fail",
        }

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/switch",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_switch_strategy_unauthenticated_returns_401(self, client, assigned_strategy):
        """
        Test POST /api/v1/strategies/account/{account_id}/switch returns 401 without auth.

        **Feature: strategy-management**
        **Test ID: SWITCH_ERR_05**
        """
        account_id = assigned_strategy["account"].id

        request_data = {"strategy_id": "some_strategy"}

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/switch",
            json=request_data,
            # No auth headers
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_switch_strategy_non_admin_returns_403(
        self, client, test_users, assigned_strategy, get_auth_headers
    ):
        """
        Test POST /api/v1/strategies/account/{account_id}/switch returns 403 for non-admin.

        **Feature: strategy-management**
        **Test ID: SWITCH_ERR_06**
        """
        regular_user = test_users[0]  # Not admin
        headers = get_auth_headers(regular_user)
        account_id = assigned_strategy["account"].id

        all_strategies = assigned_strategy["all_strategies"]
        new_strategy = all_strategies[1] if len(all_strategies) > 1 else all_strategies[0]

        request_data = {"strategy_id": new_strategy.strategy_id}

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/switch",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 403

    # ========================================================================
    # Edge Case Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_strategy_immediately_after_assign(
        self, client, test_users, test_accounts, strategy_manager, get_auth_headers
    ):
        """
        Test GET returns correct strategy immediately after POST /assign.

        **Feature: strategy-management**
        **Test ID: EDGE_08**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = test_accounts[1].id  # Account with no prior assignment

        strategies = await strategy_manager.get_available_strategies()
        request_data = {"strategy_id": strategies[0].strategy_id}

        # Assign strategy
        assign_response = await client.post(
            f"/api/v1/strategies/account/{account_id}/assign",
            json=request_data,
            headers=headers,
        )
        assert assign_response.status_code == 200

        # Immediately get the strategy
        get_response = await client.get(f"/api/v1/strategies/account/{account_id}", headers=headers)

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["strategy_id"] == strategies[0].strategy_id

    @pytest.mark.asyncio
    async def test_assignment_history_preserved(
        self, client, test_users, assigned_strategy, get_auth_headers, db_session
    ):
        """
        Test that assignment history is preserved after multiple switches.

        **Feature: strategy-management**
        **Test ID: EDGE_05**
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = assigned_strategy["account"].id
        all_strategies = assigned_strategy["all_strategies"]

        # Perform multiple switches if we have enough strategies
        if len(all_strategies) >= 2:
            # Switch to a different strategy
            new_strategy = next(
                (
                    s
                    for s in all_strategies
                    if s.strategy_id != assigned_strategy["strategy"].strategy_id
                ),
                None,
            )

            request_data = {
                "strategy_id": new_strategy.strategy_id,
                "switch_reason": "First switch for history test",
            }

            response = await client.post(
                f"/api/v1/strategies/account/{account_id}/switch",
                json=request_data,
                headers=headers,
            )
            assert response.status_code == 200

        # Query all assignments for this account (active and inactive)
        await db_session.commit()
        result = await db_session.execute(
            select(StrategyAssignmentModel).where(StrategyAssignmentModel.account_id == account_id)
        )
        all_assignments = result.scalars().all()

        # Should have at least 2 assignments (initial + switch)
        assert len(all_assignments) >= 2, "Assignment history should be preserved"

        # Exactly one should be active
        active_count = sum(1 for a in all_assignments if a.is_active)
        assert active_count == 1, "Exactly one assignment should be active"

    @pytest.mark.asyncio
    async def test_switch_records_previous_strategy_correctly(
        self, client, test_users, assigned_strategy, get_auth_headers
    ):
        """
        Test that switch correctly records previous_strategy_id as strategy identifier.

        **Feature: strategy-management**
        **Test ID: SWITCH_HP_03**
        Note: This test will fail until Bug #2 is fixed.
        """
        admin = test_users[2]
        headers = get_auth_headers(admin)
        account_id = assigned_strategy["account"].id
        current_strategy = assigned_strategy["strategy"]

        all_strategies = assigned_strategy["all_strategies"]
        new_strategy = next(
            (s for s in all_strategies if s.strategy_id != current_strategy.strategy_id),
            None,
        )
        assert new_strategy is not None

        request_data = {
            "strategy_id": new_strategy.strategy_id,
            "switch_reason": "Testing previous_strategy_id",
        }

        response = await client.post(
            f"/api/v1/strategies/account/{account_id}/switch",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        # BUG #2: previous_strategy_id should be the strategy identifier string,
        # not the database ID as a string
        assert data["previous_strategy_id"] == current_strategy.strategy_id, (
            f"Expected previous_strategy_id='{current_strategy.strategy_id}', "
            f"got '{data['previous_strategy_id']}'. "
            "This indicates Bug #2 - returning DB ID instead of strategy_id string."
        )
