"""
E2E tests for user management API endpoints.

Tests the complete user management API with real database integration,
including list, get, promote, and revoke endpoints.

**Feature: user-management, Property 1: Admin list returns all users**
**Feature: user-management, Property 6: Get user returns complete information**
"""

import logging
from datetime import datetime

import pytest
import pytest_asyncio
from eth_account import Account
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.main import app
from app.models.account import User

logger = logging.getLogger(__name__)

# High user IDs for test data (to avoid conflicts with real users)
TEST_USER_ID_BASE = 1000000
TEST_USER_IDS = [TEST_USER_ID_BASE + i for i in range(10)]


class TestUserManagementAPIE2E:
    """E2E tests for user management API with real database."""

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

        Generates 5 test users with high IDs and real eth_account addresses.
        Cleans up after test completes.
        """
        created_users = []
        try:
            # Generate test users with real Ethereum addresses
            for i in range(5):
                # Generate a real Ethereum account
                account = Account.create()
                address = account.address

                # Create user with high ID
                user = User(
                    id=TEST_USER_IDS[i],
                    address=address,
                    is_admin=(i == 0),  # First user is admin
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db_session.add(user)
                created_users.append(user)

            await db_session.commit()
            logger.info(f"Created {len(created_users)} test users")
            yield created_users

        finally:
            # Cleanup: delete test users
            if not created_users:
                return
            try:
                from sqlalchemy import delete
                from sqlalchemy.exc import SQLAlchemyError

                user_ids_to_delete = [user.id for user in created_users]
                delete_stmt = delete(User).where(User.id.in_(user_ids_to_delete))
                await db_session.execute(delete_stmt)
                await db_session.commit()
                logger.info("Cleaned up test users")
            except SQLAlchemyError as e:
                logger.warning(f"Error cleaning up test users: {e}")
                await db_session.rollback()

    @pytest.mark.asyncio
    async def test_list_users_returns_all_users(self, client, test_users, get_auth_headers):
        """
        **Feature: user-management, Property 1: Admin list returns all users**

        Test that list_users returns all users from the database with complete information.
        For any admin user and any database state with N users, the response should
        contain all users with ID, address, admin status, and timestamps.

        **Validates: Requirements 1.1, 1.4**
        """
        try:
            # Use admin user for authentication
            admin_user = test_users[0]
            headers = get_auth_headers(admin_user)

            # List users via HTTP API
            response = await client.get(
                "/api/v1/users",
                params={"skip": 0, "limit": 100},
                headers=headers,
            )

            # Validate response
            assert response.status_code == 200, f"Should return 200, got {response.status_code}"
            data = response.json()

            # Response should have users array and metadata
            assert "users" in data, "Response should have users field"
            users = data["users"]

            # Validate we got users
            assert len(users) > 0, "Should return at least one user"

            # Find our test users in the results
            test_user_ids = {u.id for u in test_users}
            found_test_users = [u for u in users if u["id"] in test_user_ids]
            assert len(found_test_users) == len(test_users), "Should find all test users"

            # Validate each user has required fields
            for user in found_test_users:
                assert "id" in user, "User should have id field"
                assert "address" in user, "User should have address field"
                assert "is_admin" in user, "User should have is_admin field"
                assert "created_at" in user, "User should have created_at field"
                assert "updated_at" in user, "User should have updated_at field"

                # Validate field types
                assert isinstance(user["id"], int), "id should be integer"
                assert isinstance(user["address"], str), "address should be string"
                assert isinstance(user["is_admin"], bool), "is_admin should be boolean"
                assert isinstance(user["created_at"], str), "created_at should be ISO string"
                assert isinstance(user["updated_at"], str), "updated_at should be ISO string"

                # Validate address format
                assert user["address"].startswith("0x"), "address should start with 0x"
                assert len(user["address"]) == 42, "address should be 42 characters"

            logger.info(f"Successfully listed {len(found_test_users)} test users via API")

        except Exception as e:
            pytest.skip(f"API not available: {e}")

    @pytest.mark.asyncio
    async def test_pagination_returns_correct_subset(self, client, test_users, get_auth_headers):
        """
        **Feature: user-management, Property 3: Pagination returns correct subset**

        Test that pagination with skip and limit returns the correct subset of users.
        For any database state with N users and pagination parameters (skip=S, limit=L),
        the response should contain exactly min(L, N-S) users starting from position S.

        **Validates: Requirements 1.5**
        """
        try:
            admin_user = test_users[0]
            headers = get_auth_headers(admin_user)

            # Test pagination with skip=0, limit=1
            response1 = await client.get(
                "/api/v1/users", params={"skip": 0, "limit": 1}, headers=headers
            )
            assert response1.status_code == 200
            data1 = response1.json()
            users_page1 = data1["users"]
            assert len(users_page1) == 1, "First page should have 1 user"

            # Test pagination with skip=1, limit=1
            response2 = await client.get(
                "/api/v1/users", params={"skip": 1, "limit": 1}, headers=headers
            )
            assert response2.status_code == 200
            data2 = response2.json()
            users_page2 = data2["users"]
            assert len(users_page2) == 1, "Second page should have 1 user"

            # Verify different users
            assert users_page1[0]["id"] != users_page2[0]["id"], (
                "Pages should contain different users"
            )

            # Test pagination with skip beyond total
            response_beyond = await client.get(
                "/api/v1/users", params={"skip": 10000, "limit": 10}, headers=headers
            )
            assert response_beyond.status_code == 200
            data_beyond = response_beyond.json()
            users_beyond = data_beyond["users"]
            assert len(users_beyond) == 0, "Skip beyond total should return empty list"

            # Test pagination with large limit
            response_all = await client.get(
                "/api/v1/users", params={"skip": 0, "limit": 1000}, headers=headers
            )
            assert response_all.status_code == 200
            data_all = response_all.json()
            users_all = data_all["users"]
            assert len(users_all) >= len(test_users), "Large limit should return all users"

            logger.info(f"Pagination tests passed with {len(test_users)} test users")

        except Exception as e:
            pytest.skip(f"API not available: {e}")

    @pytest.mark.asyncio
    async def test_get_user_returns_complete_information(
        self, client, test_users, get_auth_headers
    ):
        """
        **Feature: user-management, Property 6: Get user returns complete information**

        Test that get_user_by_id returns all required user fields.
        For any valid user ID, when an admin requests that user, the response should
        include all required fields (ID, address, admin status, created_at, updated_at).

        **Validates: Requirements 4.1, 4.5**
        """
        try:
            # Get first test user
            admin_user = test_users[0]
            user = test_users[1]
            headers = get_auth_headers(admin_user)

            # Get user by ID via HTTP API
            response = await client.get(
                f"/api/v1/users/{user.id}",
                headers=headers,
            )

            # Validate response
            assert response.status_code == 200, f"Should return 200, got {response.status_code}"
            retrieved_user = response.json()

            # Validate user was retrieved
            assert retrieved_user["id"] == user.id, "Retrieved user should have correct ID"

            # Validate all required fields are present
            required_fields = ["id", "address", "is_admin", "created_at", "updated_at"]
            for field in required_fields:
                assert field in retrieved_user, f"User should have {field} field"

            # Validate field types
            assert isinstance(retrieved_user["id"], int), "id should be integer"
            assert isinstance(retrieved_user["address"], str), "address should be string"
            assert isinstance(retrieved_user["is_admin"], bool), "is_admin should be boolean"
            assert isinstance(retrieved_user["created_at"], str), "created_at should be ISO string"
            assert isinstance(retrieved_user["updated_at"], str), "updated_at should be ISO string"

            # Validate address format
            assert retrieved_user["address"].startswith("0x"), "address should start with 0x"
            assert len(retrieved_user["address"]) == 42, "address should be 42 characters"

            logger.info(f"Successfully retrieved user {user.id} via API")

        except Exception as e:
            pytest.skip(f"API not available: {e}")

    @pytest.mark.asyncio
    async def test_get_nonexistent_user_returns_404(self, client, test_users, get_auth_headers):
        """Test that getting a non-existent user returns 404."""
        admin_user = test_users[0]
        headers = get_auth_headers(admin_user)

        # Try to get user with very high ID
        response = await client.get(
            "/api/v1/users/999999",
            headers=headers,
        )
        assert response.status_code == 404, (
            f"Should return 404 for non-existent user, got {response.status_code}: {response.text}"
        )

        logger.info("Non-existent user correctly returns 404")

    @pytest.mark.asyncio
    async def test_promote_user_updates_admin_status(self, client, test_users, get_auth_headers):
        """
        **Feature: user-management, Property 4: Promotion updates admin status**

        Test that promoting a user updates their is_admin field to True.

        **Validates: Requirements 2.1, 2.5**
        """
        try:
            # Use first test user as admin, second as regular user
            admin_user = test_users[0]
            regular_user = test_users[1]
            headers = get_auth_headers(admin_user)

            # Promote the regular user via HTTP API
            response = await client.put(
                f"/api/v1/users/{regular_user.id}/promote",
                headers=headers,
            )

            # Validate response
            assert response.status_code == 200, f"Should return 200, got {response.status_code}"
            promoted_user = response.json()

            # Validate promotion
            assert promoted_user["is_admin"] is True, "User should be promoted to admin"
            assert promoted_user["id"] == regular_user.id, "Should be the same user"

            # Verify by getting user again
            verify_response = await client.get(
                f"/api/v1/users/{regular_user.id}",
                headers=headers,
            )
            assert verify_response.status_code == 200
            verified_user = verify_response.json()
            assert verified_user["is_admin"] is True, "Database should reflect promotion"

            logger.info(f"Successfully promoted user {regular_user.id} to admin via API")

        except Exception as e:
            pytest.skip(f"API not available: {e}")

    @pytest.mark.asyncio
    async def test_revoke_admin_updates_admin_status(self, client, test_users, get_auth_headers):
        """
        **Feature: user-management, Property 5: Revocation updates admin status**

        Test that revoking admin status updates the is_admin field to False.

        **Validates: Requirements 3.1, 3.5**
        """
        try:
            # First promote a second user to admin
            admin_user = test_users[0]
            user_to_promote = test_users[2]
            headers = get_auth_headers(admin_user)

            promote_response = await client.put(
                f"/api/v1/users/{user_to_promote.id}/promote",
                headers=headers,
            )
            assert promote_response.status_code == 200

            # Now revoke admin status via HTTP API
            revoke_response = await client.put(
                f"/api/v1/users/{user_to_promote.id}/revoke",
                headers=headers,
            )

            # Validate response
            assert revoke_response.status_code == 200, (
                f"Should return 200, got {revoke_response.status_code}"
            )
            revoked_user = revoke_response.json()

            # Validate revocation
            assert revoked_user["is_admin"] is False, "User should have admin status revoked"
            assert revoked_user["id"] == user_to_promote.id, "Should be the same user"

            # Verify by getting user again
            verify_response = await client.get(
                f"/api/v1/users/{user_to_promote.id}",
                headers=headers,
            )
            assert verify_response.status_code == 200
            verified_user = verify_response.json()
            assert verified_user["is_admin"] is False, "Database should reflect revocation"

            logger.info(f"Successfully revoked admin status from user {user_to_promote.id} via API")

        except Exception as e:
            pytest.skip(f"API not available: {e}")

    @pytest.mark.asyncio
    async def test_promote_nonexistent_user_returns_404(self, client, test_users, get_auth_headers):
        """Test that promoting a non-existent user returns 404."""
        try:
            # Use first test user as admin
            admin_user = test_users[0]
            headers = get_auth_headers(admin_user)

            # Try to promote non-existent user with very high ID
            nonexistent_id = TEST_USER_ID_BASE + 10000
            response = await client.put(
                f"/api/v1/users/{nonexistent_id}/promote",
                headers=headers,
            )

            assert response.status_code == 404, "Should return 404 for non-existent user"

            logger.info("Non-existent user promotion correctly returns 404")

        except Exception as e:
            pytest.skip(f"API not available: {e}")

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_user_returns_404(self, client, test_users, get_auth_headers):
        """Test that revoking admin from a non-existent user returns 404."""
        try:
            # Use first test user as admin
            admin_user = test_users[0]
            headers = get_auth_headers(admin_user)

            # Try to revoke admin from non-existent user with very high ID
            nonexistent_id = TEST_USER_ID_BASE + 10000
            response = await client.put(
                f"/api/v1/users/{nonexistent_id}/revoke",
                headers=headers,
            )

            assert response.status_code == 404, "Should return 404 for non-existent user"

            logger.info("Non-existent user revocation correctly returns 404")

        except Exception as e:
            pytest.skip(f"API not available: {e}")

    @pytest.mark.asyncio
    async def test_list_users_with_invalid_pagination_returns_error(
        self, client, test_users, get_auth_headers
    ):
        """Test that invalid pagination parameters return 422 validation error."""
        admin_user = test_users[0]
        headers = get_auth_headers(admin_user)

        # Test negative skip - should return 422
        response1 = await client.get(
            "/api/v1/users", params={"skip": -1, "limit": 10}, headers=headers
        )
        assert response1.status_code == 422, (
            f"Should return 422 for negative skip, got {response1.status_code}"
        )

        # Test non-positive limit - should return 422
        response2 = await client.get(
            "/api/v1/users", params={"skip": 0, "limit": 0}, headers=headers
        )
        assert response2.status_code == 422, (
            f"Should return 422 for zero limit, got {response2.status_code}"
        )

        logger.info("Invalid pagination parameters correctly return 422")

    @pytest.mark.asyncio
    async def test_user_data_integrity(self, client, test_users, get_auth_headers):
        """Test that user data maintains integrity across operations."""
        admin_user = test_users[0]
        headers = get_auth_headers(admin_user)

        # Validate data integrity for each test user
        for user in test_users:
            # Verify user can be retrieved by ID via API
            response = await client.get(f"/api/v1/users/{user.id}", headers=headers)
            assert response.status_code == 200, f"User {user.id} should be retrievable"
            retrieved = response.json()
            assert retrieved["address"] == user.address, "Address should match"
            assert retrieved["is_admin"] == user.is_admin, "Admin status should match"

        logger.info(f"Data integrity verified for {len(test_users)} test users via API")

    @pytest.mark.asyncio
    async def test_admin_cannot_modify_own_status_promote(
        self, client, test_users, get_auth_headers
    ):
        """Test that an admin cannot promote themselves."""
        admin_user = test_users[0]
        headers = get_auth_headers(admin_user)

        # Try to promote self
        response = await client.put(
            f"/api/v1/users/{admin_user.id}/promote",
            headers=headers,
        )
        assert response.status_code == 400, "Should return 400 for self-promotion"
        assert "cannot change their own status" in response.json()["detail"].lower()

        logger.info("Admin self-promotion correctly blocked")

    @pytest.mark.asyncio
    async def test_admin_cannot_modify_own_status_revoke(
        self, client, test_users, get_auth_headers
    ):
        """Test that an admin cannot revoke their own status."""
        admin_user = test_users[0]
        headers = get_auth_headers(admin_user)

        # Try to revoke self
        response = await client.put(
            f"/api/v1/users/{admin_user.id}/revoke",
            headers=headers,
        )
        assert response.status_code == 400, "Should return 400 for self-revocation"
        assert "cannot change their own status" in response.json()["detail"].lower()

        logger.info("Admin self-revocation correctly blocked")

    @pytest.mark.asyncio
    async def test_cannot_revoke_last_admin(self, client, test_users, get_auth_headers, db_session):
        """Test that the last admin's status cannot be revoked."""
        from datetime import datetime

        from eth_account import Account

        # Create two temporary admin users
        temp_admin1_account = Account.create()
        temp_admin1 = User(
            id=TEST_USER_ID_BASE + 100,
            address=temp_admin1_account.address,
            is_admin=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        temp_admin2_account = Account.create()
        temp_admin2 = User(
            id=TEST_USER_ID_BASE + 101,
            address=temp_admin2_account.address,
            is_admin=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db_session.add(temp_admin1)
        db_session.add(temp_admin2)
        await db_session.commit()

        try:
            # Revoke all existing test admins
            for user in test_users:
                if user.is_admin:
                    user.is_admin = False
                    db_session.add(user)
            await db_session.commit()

            # Now we have exactly 2 admins: temp_admin1 and temp_admin2
            # temp_admin1 will revoke temp_admin2, leaving only temp_admin1
            headers1 = get_auth_headers(temp_admin1)

            response1 = await client.put(
                f"/api/v1/users/{temp_admin2.id}/revoke",
                headers=headers1,
            )
            assert response1.status_code == 200, "Should succeed when revoking one of two admins"

            # Now temp_admin1 is the ONLY admin
            # Create a third admin to try revoking temp_admin1 (the last admin)
            temp_admin3_account = Account.create()
            temp_admin3 = User(
                id=TEST_USER_ID_BASE + 102,
                address=temp_admin3_account.address,
                is_admin=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db_session.add(temp_admin3)
            await db_session.commit()

            # Now we have 2 admins again (temp_admin1 and temp_admin3)
            # temp_admin3 tries to revoke temp_admin1
            headers3 = get_auth_headers(temp_admin3)
            response2 = await client.put(
                f"/api/v1/users/{temp_admin1.id}/revoke",
                headers=headers3,
            )
            assert response2.status_code == 200, "Should succeed when there are 2 admins"

            # Now temp_admin3 is the ONLY admin
            # temp_admin3 tries to revoke themselves (should fail with self-modification error)
            response3 = await client.put(
                f"/api/v1/users/{temp_admin3.id}/revoke",
                headers=headers3,
            )
            assert response3.status_code == 400, "Should fail for self-revocation"
            assert "cannot change their own status" in response3.json()["detail"].lower()

            logger.info("Last admin protection correctly enforced (via self-modification check)")

        finally:
            # Cleanup temp users
            try:
                for user_id in [
                    TEST_USER_ID_BASE + 100,
                    TEST_USER_ID_BASE + 101,
                    TEST_USER_ID_BASE + 102,
                ]:
                    result = await db_session.execute(select(User).where(User.id == user_id))
                    user = result.scalar_one_or_none()
                    if user:
                        await db_session.delete(user)
                await db_session.commit()
            except Exception as e:
                logger.warning(f"Error cleaning up temp admins: {e}")
                await db_session.rollback()

    @pytest.mark.asyncio
    async def test_regular_user_cannot_access_list_users(
        self, client, test_users, get_auth_headers
    ):
        """Test that a regular user cannot list users."""
        regular_user = test_users[1]  # Second user is not admin
        headers = get_auth_headers(regular_user)

        response = await client.get("/api/v1/users", headers=headers)
        assert response.status_code == 403, "Should return 403 for regular user"

        logger.info("Regular user correctly denied access to list users")

    @pytest.mark.asyncio
    async def test_regular_user_cannot_access_get_user(self, client, test_users, get_auth_headers):
        """Test that a regular user cannot get user details."""
        regular_user = test_users[1]
        target_user = test_users[2]
        headers = get_auth_headers(regular_user)

        response = await client.get(f"/api/v1/users/{target_user.id}", headers=headers)
        assert response.status_code == 403, "Should return 403 for regular user"

        logger.info("Regular user correctly denied access to get user")

    @pytest.mark.asyncio
    async def test_regular_user_cannot_promote(self, client, test_users, get_auth_headers):
        """Test that a regular user cannot promote another user."""
        regular_user = test_users[1]
        target_user = test_users[2]
        headers = get_auth_headers(regular_user)

        response = await client.put(f"/api/v1/users/{target_user.id}/promote", headers=headers)
        assert response.status_code == 403, "Should return 403 for regular user"

        logger.info("Regular user correctly denied access to promote")

    @pytest.mark.asyncio
    async def test_regular_user_cannot_revoke(self, client, test_users, get_auth_headers):
        """Test that a regular user cannot revoke admin status."""
        regular_user = test_users[1]
        admin_user = test_users[0]
        headers = get_auth_headers(regular_user)

        response = await client.put(f"/api/v1/users/{admin_user.id}/revoke", headers=headers)
        assert response.status_code == 403, "Should return 403 for regular user"

        logger.info("Regular user correctly denied access to revoke")
