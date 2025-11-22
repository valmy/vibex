# Implementation Plan

- [x] 1. Set up user management service layer
  - Create `backend/src/app/services/user_management_service.py` with core business logic
  - Implement `list_users` method with pagination support
  - Implement `get_user_by_id` method for retrieving specific users
  - Implement `promote_user_to_admin` method for granting admin privileges
  - Implement `revoke_admin_status` method for removing admin privileges
  - Add comprehensive docstrings with type hints
  - _Requirements: 1.1, 2.1, 3.1, 4.1_

- [x] 1.1 Write property test for list users pagination
  - **Property 3: Pagination returns correct subset**
  - **Validates: Requirements 1.5**

- [x] 1.2 Write property test for admin status updates
  - **Property 4: Promotion updates admin status**
  - **Property 5: Revocation updates admin status**
  - **Validates: Requirements 2.1, 2.5, 3.1, 3.5**

- [x] 2. Enhance security middleware
  - Add `require_admin` dependency function to `backend/src/app/core/security.py`
  - Implement admin privilege checking with proper error handling
  - Return 403 Forbidden for non-admin users
  - Add docstrings and type hints
  - _Requirements: 1.2, 2.3, 3.3, 4.3_

- [x] 2.1 Write property test for admin authorization
  - **Property 2: Regular users cannot access admin endpoints**
  - **Validates: Requirements 1.2, 2.3, 3.3, 4.3**

- [x] 3. Create user management schemas
  - Create `backend/src/app/schemas/user.py` with Pydantic models
  - Implement `UserBase` schema with address field
  - Implement `UserRead` schema with all fields (id, address, is_admin, timestamps)
  - Implement `UserList` schema for paginated responses
  - Add field validation and examples
  - _Requirements: 1.4, 4.5_

- [x] 4. Implement user management API routes
  - Create `backend/src/app/api/routes/users.py` router module
  - Implement `GET /api/v1/users` endpoint for listing users with pagination
  - Implement `GET /api/v1/users/{user_id}` endpoint for getting user details
  - Implement `PUT /api/v1/users/{user_id}/promote` endpoint for promoting users
  - Implement `PUT /api/v1/users/{user_id}/revoke` endpoint for revoking admin status
  - Add OpenAPI documentation with descriptions and examples
  - Wire up dependencies (require_admin, get_db)
  - _Requirements: 1.1, 2.1, 3.1, 4.1_

- [x] 4.1 Write property test for complete user information
  - **Property 1: Admin list returns all users**
  - **Property 6: Get user returns complete information**
  - **Validates: Requirements 1.1, 1.4, 4.1, 4.5**

- [x] 5. Integrate user management routes into main application
  - Update `backend/src/app/main.py` to include users router
  - Add router with `/api/v1` prefix and `users` tag
  - Verify OpenAPI documentation includes new endpoints
  - Test Swagger UI at `/docs` shows user management endpoints
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 6. Implement audit logging for user management operations
  - Add logging calls to all service methods in `user_management_service.py`
  - Log successful operations with admin address, target user, action, timestamp
  - Log failed operations with error details and context
  - Use structured logging format (JSON) for easy parsing
  - Include correlation IDs for request tracking
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6.1 Write property tests for audit logging
  - **Property 7: Promotion actions are logged**
  - **Property 8: Revocation actions are logged**
  - **Property 9: List actions are logged**
  - **Property 10: Get user actions are logged**
  - **Property 11: Failed operations are logged**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

- [x] 7. Write unit tests for user management service
  - Create `backend/tests/unit/test_user_management_service.py`
  - Test `list_users` with various database states
  - Test `list_users` pagination with different skip/limit values
  - Test `get_user_by_id` with valid and invalid IDs
  - Test `promote_user_to_admin` updates is_admin field
  - Test `revoke_admin_status` updates is_admin field
  - Mock database session for isolated testing
  - _Requirements: 7.1, 7.2_

- [x] 8. Write e2e tests for user management API
  - Create `backend/tests/e2e/test_users_api_e2e.py`
  - Test list users endpoint as admin user (200 OK)
  - Test list users endpoint as regular user (403 Forbidden)
  - Test list users endpoint without authentication (401 Unauthorized)
  - Test get user endpoint as admin user (200 OK)
  - Test get user endpoint as regular user (403 Forbidden)
  - Test get user endpoint with non-existent ID (404 Not Found)
  - Test promote user endpoint as admin user (200 OK)
  - Test promote user endpoint as regular user (403 Forbidden)
  - Test promote user endpoint with non-existent ID (404 Not Found)
  - Test revoke admin endpoint as admin user (200 OK)
  - Test revoke admin endpoint as regular user (403 Forbidden)
  - Test revoke admin endpoint with non-existent ID (404 Not Found)
  - Test pagination returns correct subsets
  - Use real database with test fixtures
  - _Requirements: 7.3, 7.4, 7.5_

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Update API documentation
  - Update `docs/API_AUTH.md` with new user management endpoints
  - Document list users endpoint with request/response examples
  - Document get user endpoint with request/response examples
  - Document promote user endpoint with request/response examples
  - Document revoke admin endpoint with request/response examples
  - Add section on admin-only endpoints
  - Include curl examples for each endpoint
  - Document error responses (401, 403, 404)
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 11. Final checkpoint - Verify complete implementation
  - Run all unit tests and verify 100% pass rate
  - Run all integration tests and verify 100% pass rate
  - Run all property-based tests and verify properties hold
  - Verify OpenAPI documentation is complete and accurate
  - Test all endpoints manually via Swagger UI
  - Verify audit logs are generated correctly
  - Check code coverage meets 90%+ target
  - Ensure all tests pass, ask the user if questions arise.
