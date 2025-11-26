# Implementation Plan

- [x] 1. Create account service layer with ownership control
  - Create `backend/src/app/services/account_service.py` with core business logic
  - Implement `create_account` method that associates account with authenticated user
  - Implement `list_user_accounts` method with ownership filtering
  - Implement `get_account` method with ownership/admin check
  - Implement `update_account` method with ownership/admin check
  - Implement `delete_account` method with cascade deletion
  - Implement `validate_trading_mode` method for paper/real trading validation
  - Add comprehensive docstrings with type hints
  - _Requirements: 1.1, 1.4, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 6.2_

- [x] 1.1 Write property test for account creation persistence
  - **Property 1: Account creation persists all settings**
  - **Validates: Requirements 1.1, 1.4**

- [x] 1.2 Write property test for ownership filtering
  - **Property 2: Account ownership filtering**
  - **Validates: Requirements 2.1**

- [x] 1.3 Write property test for non-owner access denied
  - **Property 3: Non-owner access denied**
  - **Validates: Requirements 2.3, 3.2, 4.2**

- [x] 1.4 Write property test for admin access granted
  - **Property 4: Admin access granted**
  - **Validates: Requirements 2.4, 3.3, 4.3**

- [x] 2. Enhance security middleware for account ownership
  - Add `require_account_owner` dependency function to `backend/src/app/core/security.py`
  - Add `require_admin_or_owner` dependency function for admin override
  - Implement ownership checking with proper error handling
  - Return 403 Forbidden for non-owners (unless admin)
  - Add docstrings and type hints
  - _Requirements: 2.3, 3.2, 4.2, 2.4, 3.3, 4.3_

- [x] 3. Update account schemas for credential masking
  - Update `backend/src/app/schemas/account.py` with enhanced schemas
  - Add `has_api_credentials` field to `AccountRead` (masks actual credentials)
  - Add `status` validation pattern for valid status values
  - Add `balance_usd` field to `AccountCreate` for paper trading initial balance
  - Update field validation and examples
  - _Requirements: 5.2, 6.1_

- [x] 3.1 Write property test for credential masking
  - **Property 7: Credential masking**
  - **Validates: Requirements 5.2**

- [x] 4. Update account API routes with ownership control
  - Update `backend/src/app/api/routes/accounts.py` with ownership checks
  - Update `POST /api/v1/accounts` to associate with authenticated user
  - Update `GET /api/v1/accounts` to filter by user ownership
  - Update `GET /api/v1/accounts/{id}` with ownership/admin check
  - Update `PUT /api/v1/accounts/{id}` with ownership/admin check
  - Update `DELETE /api/v1/accounts/{id}` with ownership/admin check and cascade
  - Add OpenAPI documentation with descriptions and examples
  - _Requirements: 1.1, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3_

- [x] 4.1 Write property test for update persistence
  - **Property 5: Update persistence**
  - **Validates: Requirements 3.1, 3.4**

- [x] 4.2 Write property test for cascade deletion
  - **Property 6: Cascade deletion**
  - **Validates: Requirements 4.1, 4.4**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement trading mode validation
  - Add trading mode validation to account service
  - Validate paper trading allows arbitrary balance
  - Validate real trading requires API credentials
  - Add validation when switching from paper to real trading
  - _Requirements: 5.5, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6.1 Write property test for paper trading mode
  - **Property 8: Paper trading mode allows arbitrary balance**
  - **Validates: Requirements 6.1, 6.4**

- [x] 6.2 Write property test for real trading requirements
  - **Property 9: Real trading requires credentials**
  - **Validates: Requirements 5.5, 6.2**

- [x] 7. Implement balance sync endpoint
  - Add `sync_balance` method to account service
  - Create AsterDEX API client integration for balance fetching
  - Add `POST /api/v1/accounts/{id}/sync-balance` endpoint
  - Handle API errors with appropriate status codes (401, 502)
  - Validate sync only allowed for real trading accounts
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 7.1 Write property test for balance sync
  - **Property 10: Balance sync updates balance**
  - **Validates: Requirements 7.2**

- [x] 8. Implement account status management
  - Add status transition validation to account service
  - Implement paused status behavior (stop trading, retain data)
  - Implement stopped status behavior (disable, require reactivation)
  - Add credential validation when reactivating from stopped
  - Add audit logging for status changes
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 8.1 Write property test for status change logging
  - **Property 11: Status change logging**
  - **Validates: Requirements 8.5**

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Write unit tests for account service
  - Create `backend/tests/unit/test_account_service.py`
  - Test `create_account` with valid data and user association
  - Test `create_account` with duplicate name error
  - Test `list_user_accounts` with ownership filtering
  - Test `get_account` with owner, non-owner, and admin scenarios
  - Test `update_account` with owner, non-owner, and admin scenarios
  - Test `delete_account` with cascade verification
  - Test `validate_trading_mode` with paper and real trading
  - **IMPORTANT: Use mocked database session (AsyncMock) for isolated testing**
  - _Requirements: 11.1, 11.2_

- [ ] 11. Write integration tests for account relationships
  - Create `backend/tests/integration/test_account_relationships.py`
  - Test account-position relationship and cascade delete
  - Test account-order relationship and cascade delete
  - Test account-trade relationship and cascade delete
  - Test account-user association
  - **IMPORTANT: Use mocked database access (AsyncMock) to test module relationships**
  - _Requirements: 11.3, 11.4_

- [ ] 11.1 Write property test for account isolation - positions
  - **Property 12: Account isolation - positions**
  - **Validates: Requirements 9.2, 9.5**

- [ ] 11.2 Write property test for account isolation - metrics
  - **Property 13: Account isolation - metrics**
  - **Validates: Requirements 9.3**

- [ ] 12. Write e2e tests for account API
  - Create `backend/tests/e2e/test_accounts_api_e2e.py`
  - Test `POST /api/v1/accounts` creates account for authenticated user
  - Test `GET /api/v1/accounts` returns only user's accounts
  - Test `GET /api/v1/accounts/{id}` as owner (200 OK)
  - Test `GET /api/v1/accounts/{id}` as non-owner (403 Forbidden)
  - Test `GET /api/v1/accounts/{id}` as admin (200 OK)
  - Test `PUT /api/v1/accounts/{id}` as owner (200 OK)
  - Test `PUT /api/v1/accounts/{id}` as non-owner (403 Forbidden)
  - Test `DELETE /api/v1/accounts/{id}` as owner (204 No Content)
  - Test `DELETE /api/v1/accounts/{id}` as non-owner (403 Forbidden)
  - Test `POST /api/v1/accounts/{id}/sync-balance` for real trading
  - Test `POST /api/v1/accounts/{id}/sync-balance` for paper trading (400 error)
  - **IMPORTANT: Use real database with test fixtures (NOT mocked)**
  - _Requirements: 11.5, 11.6, 11.7_

- [ ] 13. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Update API documentation
  - Update `docs/API_AUTH.md` with account management endpoints
  - Document account ownership rules and admin override
  - Document trading mode (paper vs real) requirements
  - Document balance sync endpoint
  - Document status management (active, paused, stopped)
  - Include curl examples for each endpoint
  - Document error responses (400, 401, 403, 404, 502)
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 15. Final checkpoint - Verify complete implementation
  - Run all unit tests and verify 100% pass rate
  - Run all integration tests and verify 100% pass rate
  - Run all e2e tests and verify 100% pass rate
  - Run all property-based tests and verify properties hold
  - Verify OpenAPI documentation is complete and accurate
  - Test all endpoints manually via Swagger UI
  - Verify audit logs are generated correctly
  - Check code coverage meets 90%+ target
  - Ensure all tests pass, ask the user if questions arise.

