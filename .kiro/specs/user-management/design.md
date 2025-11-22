# Design Document

## Overview

This design document specifies the implementation of user management features for the AI Trading Agent API. The system extends the existing wallet-based authentication to provide admin users with capabilities to manage other users' admin status and view all registered users. The design follows RESTful API principles and integrates seamlessly with the existing FastAPI application structure.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              API Layer (Routes)                        │ │
│  │  - GET /api/v1/users (list users)                     │ │
│  │  - GET /api/v1/users/{id} (get user)                  │ │
│  │  - PUT /api/v1/users/{id}/promote (promote to admin)  │ │
│  │  - PUT /api/v1/users/{id}/revoke (revoke admin)       │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Middleware & Security                        │ │
│  │  - JWT Authentication (get_current_user)               │ │
│  │  - Admin Authorization (require_admin)                 │ │
│  │  - Request Validation (Pydantic)                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Service Layer (Business Logic)               │ │
│  │  - UserManagementService                               │ │
│  │    - list_users(skip, limit)                           │ │
│  │    - get_user_by_id(user_id)                           │ │
│  │    - promote_user_to_admin(user_id, admin_user)        │ │
│  │    - revoke_admin_status(user_id, admin_user)          │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Data Access Layer (ORM)                   │ │
│  │  - SQLAlchemy AsyncSession                             │ │
│  │  - User Model (existing)                               │ │
│  │  - Database Queries                                    │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL Database (trading schema)            │
│  - users table (id, address, is_admin, created_at, ...)    │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. API Routes (`backend/src/app/api/routes/users.py`)

New router module for user management endpoints:

```python
router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=UserList)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=1000),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> UserList:
    """List all users (admin only)"""

@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> UserRead:
    """Get user by ID (admin only)"""

@router.put("/{user_id}/promote", response_model=UserRead)
async def promote_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> UserRead:
    """Promote user to admin (admin only)"""

@router.put("/{user_id}/revoke", response_model=UserRead)
async def revoke_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> UserRead:
    """Revoke admin status (admin only)"""
```

### 2. Service Layer (`backend/src/app/services/user_management_service.py`)

Business logic for user management operations:

```python
class UserManagementService:
    """Service for managing users and admin privileges"""

    async def list_users(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """List all users with pagination"""

    async def get_user_by_id(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Optional[User]:
        """Get user by ID"""

    async def promote_user_to_admin(
        self,
        db: AsyncSession,
        user_id: int,
        admin_user: User
    ) -> User:
        """Promote user to admin status"""

    async def revoke_admin_status(
        self,
        db: AsyncSession,
        user_id: int,
        admin_user: User
    ) -> User:
        """Revoke admin status from user"""
```

### 3. Security Middleware (`backend/src/app/core/security.py`)

Enhanced security utilities:

```python
async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency that requires the current user to be an admin.
    Raises HTTPException(403) if user is not admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    return current_user
```

### 4. Schemas (`backend/src/app/schemas/user.py`)

Pydantic models for request/response validation:

```python
class UserBase(BaseModel):
    """Base user schema"""
    address: str

class UserRead(UserBase):
    """User read schema with all fields"""
    id: int
    address: str
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserList(BaseModel):
    """Paginated user list response"""
    users: List[UserRead]
    total: int
    skip: int
    limit: int
```

## Data Models

The existing User model in `backend/src/app/models/account.py` already contains all necessary fields:

```python
class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = ({"schema": "trading", "extend_existing": True},)

    id: int (primary key, auto-increment)
    address: str (unique, indexed, 42 characters)
    is_admin: bool (default: False)
    created_at: datetime (auto-generated)
    updated_at: datetime (auto-updated)

    # Relationships
    accounts: List[Account] (one-to-many)
```

No database schema changes are required.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Acceptence Criteria Testing Prework:

1.1 WHEN an admin user requests the user list THEN the System SHALL return all registered users with their addresses and admin status
Thoughts: This is a property that should hold for any admin user and any database state. We can create a random set of users in the database, authenticate as an admin, call the list endpoint, and verify that all users are returned with correct information.
Testable: yes - property

1.2 WHEN a regular user requests the user list THEN the System SHALL return a 403 Forbidden error
Thoughts: This is a property about access control that should hold for any regular user. We can create a regular user, authenticate as that user, call the list endpoint, and verify we get a 403 error.
Testable: yes - property

1.3 WHEN an unauthenticated user requests the user list THEN the System SHALL return a 401 Unauthorized error
Thoughts: This is testing authentication requirement. We can call the endpoint without authentication and verify we get a 401 error.
Testable: yes - example

1.4 WHEN the user list is returned THEN the System SHALL include user ID, wallet address, admin status, and creation timestamp for each user
Thoughts: This is a property about the structure of the response. For any valid response, each user object should contain these fields.
Testable: yes - property

1.5 WHEN the user list is requested THEN the System SHALL support pagination with configurable skip and limit parameters
Thoughts: This is a property about pagination behavior. We can create a known number of users, request with different skip/limit values, and verify the correct subset is returned.
Testable: yes - property

2.1 WHEN an admin user promotes a regular user THEN the System SHALL update the target user's is_admin field to true
Thoughts: This is a property that should hold for any admin promoting any regular user. We can create random users, promote one, and verify the is_admin field is updated.
Testable: yes - property

2.2 WHEN an admin user attempts to promote a non-existent user THEN the System SHALL return a 404 Not Found error
Thoughts: This is testing error handling for invalid input. We can use a non-existent user ID and verify we get a 404.
Testable: yes - example

2.3 WHEN a regular user attempts to promote another user THEN the System SHALL return a 403 Forbidden error
Thoughts: This is a property about access control. For any regular user attempting to promote any other user, we should get a 403.
Testable: yes - property

2.4 WHEN an unauthenticated user attempts to promote a user THEN the System SHALL return a 401 Unauthorized error
Thoughts: This is testing authentication requirement. We can call the endpoint without authentication and verify we get a 401.
Testable: yes - example

2.5 WHEN a user is promoted to admin THEN the System SHALL return the updated user information with is_admin set to true
Thoughts: This is a property about the response structure after promotion. For any successful promotion, the response should reflect the updated state.
Testable: yes - property

3.1 WHEN an admin user revokes admin status from another admin user THEN the System SHALL update the target user's is_admin field to false
Thoughts: This is a property that should hold for any admin revoking any other admin's status. We can create random admin users, revoke one, and verify the is_admin field is updated.
Testable: yes - property

3.2 WHEN an admin user attempts to revoke admin status from a non-existent user THEN the System SHALL return a 404 Not Found error
Thoughts: This is testing error handling for invalid input. We can use a non-existent user ID and verify we get a 404.
Testable: yes - example

3.3 WHEN a regular user attempts to revoke admin status THEN the System SHALL return a 403 Forbidden error
Thoughts: This is a property about access control. For any regular user attempting to revoke admin status, we should get a 403.
Testable: yes - property

3.4 WHEN an unauthenticated user attempts to revoke admin status THEN the System SHALL return a 401 Unauthorized error
Thoughts: This is testing authentication requirement. We can call the endpoint without authentication and verify we get a 401.
Testable: yes - example

3.5 WHEN admin status is revoked THEN the System SHALL return the updated user information with is_admin set to false
Thoughts: This is a property about the response structure after revocation. For any successful revocation, the response should reflect the updated state.
Testable: yes - property

4.1 WHEN an admin user requests a specific user by ID THEN the System SHALL return the user's complete information
Thoughts: This is a property that should hold for any admin requesting any valid user. We can create random users, request one by ID, and verify complete information is returned.
Testable: yes - property

4.2 WHEN an admin user requests a non-existent user THEN the System SHALL return a 404 Not Found error
Thoughts: This is testing error handling for invalid input. We can use a non-existent user ID and verify we get a 404.
Testable: yes - example

4.3 WHEN a regular user requests another user's information THEN the System SHALL return a 403 Forbidden error
Thoughts: This is a property about access control. For any regular user attempting to view another user, we should get a 403.
Testable: yes - property

4.4 WHEN an unauthenticated user requests user information THEN the System SHALL return a 401 Unauthorized error
Thoughts: This is testing authentication requirement. We can call the endpoint without authentication and verify we get a 401.
Testable: yes - example

4.5 WHEN user information is returned THEN the System SHALL include user ID, wallet address, admin status, creation timestamp, and update timestamp
Thoughts: This is a property about the structure of the response. For any valid response, the user object should contain all these fields.
Testable: yes - property

6.1 WHEN an admin promotes a user THEN the System SHALL log the action with admin address, target user address, and timestamp
Thoughts: This is a property about audit logging. For any promotion action, we should be able to verify a log entry exists with the correct information.
Testable: yes - property

6.2 WHEN an admin revokes admin status THEN the System SHALL log the action with admin address, target user address, and timestamp
Thoughts: This is a property about audit logging. For any revocation action, we should be able to verify a log entry exists with the correct information.
Testable: yes - property

6.3 WHEN an admin lists users THEN the System SHALL log the action with admin address and timestamp
Thoughts: This is a property about audit logging. For any list action, we should be able to verify a log entry exists.
Testable: yes - property

6.4 WHEN an admin views a specific user THEN the System SHALL log the action with admin address, target user address, and timestamp
Thoughts: This is a property about audit logging. For any view action, we should be able to verify a log entry exists with the correct information.
Testable: yes - property

6.5 WHEN any user management operation fails THEN the System SHALL log the failure with error details and context
Thoughts: This is a property about error logging. For any failed operation, we should be able to verify an error log entry exists.
Testable: yes - property

### Property Reflection

Reviewing all properties for redundancy:

- Properties 1.2, 2.3, 3.3, 4.3 all test 403 Forbidden for regular users - these can be combined into a single comprehensive property
- Properties 1.3, 2.4, 3.4, 4.4 all test 401 Unauthorized for unauthenticated users - these are examples and can be kept as edge cases
- Properties 2.2, 3.2, 4.2 all test 404 Not Found for non-existent users - these are examples and can be kept as edge cases
- Audit logging properties (6.1-6.5) are distinct and should be kept separate

After reflection, we'll combine the 403 Forbidden properties into one comprehensive property.

### Correctness Properties

Property 1: Admin list returns all users
*For any* database state with N users, when an admin user requests the user list, the response should contain exactly N users with complete information (ID, address, admin status, timestamps).
**Validates: Requirements 1.1, 1.4**

Property 2: Regular users cannot access admin endpoints
*For any* regular (non-admin) user, attempting to access any user management endpoint (list, get, promote, revoke) should return a 403 Forbidden error.
**Validates: Requirements 1.2, 2.3, 3.3, 4.3**

Property 3: Pagination returns correct subset
*For any* database state with N users and pagination parameters (skip=S, limit=L), the response should contain exactly min(L, N-S) users starting from position S.
**Validates: Requirements 1.5**

Property 4: Promotion updates admin status
*For any* regular user, when an admin promotes that user, the user's is_admin field should be true in both the database and the response.
**Validates: Requirements 2.1, 2.5**

Property 5: Revocation updates admin status
*For any* admin user, when another admin revokes their status, the user's is_admin field should be false in both the database and the response.
**Validates: Requirements 3.1, 3.5**

Property 6: Get user returns complete information
*For any* valid user ID, when an admin requests that user, the response should include all required fields (ID, address, admin status, created_at, updated_at).
**Validates: Requirements 4.1, 4.5**

Property 7: Promotion actions are logged
*For any* successful user promotion, an audit log entry should exist containing the admin's address, target user's address, action type, and timestamp.
**Validates: Requirements 6.1**

Property 8: Revocation actions are logged
*For any* successful admin status revocation, an audit log entry should exist containing the admin's address, target user's address, action type, and timestamp.
**Validates: Requirements 6.2**

Property 9: List actions are logged
*For any* successful user list request, an audit log entry should exist containing the admin's address, action type, and timestamp.
**Validates: Requirements 6.3**

Property 10: Get user actions are logged
*For any* successful get user request, an audit log entry should exist containing the admin's address, target user's address, action type, and timestamp.
**Validates: Requirements 6.4**

Property 11: Failed operations are logged
*For any* failed user management operation, an error log entry should exist containing the error type, error message, and context information.
**Validates: Requirements 6.5**

## Error Handling

### HTTP Status Codes

- **200 OK**: Successful GET requests
- **401 Unauthorized**: Missing or invalid JWT token
- **403 Forbidden**: Valid token but insufficient privileges (not admin)
- **404 Not Found**: Requested user does not exist
- **422 Unprocessable Entity**: Invalid request parameters (e.g., negative skip/limit)
- **500 Internal Server Error**: Unexpected server errors

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Error Handling Strategy

1. **Authentication Errors**: Handled by `get_current_user` dependency
2. **Authorization Errors**: Handled by `require_admin` dependency
3. **Not Found Errors**: Raised when user_id doesn't exist in database
4. **Validation Errors**: Handled automatically by FastAPI/Pydantic
5. **Database Errors**: Caught and logged, return 500 with generic message

## Testing Strategy

### Unit Testing

Unit tests will verify individual service functions with mocked database sessions:

- `test_list_users_success`: Verify list_users returns all users
- `test_list_users_pagination`: Verify pagination works correctly
- `test_get_user_by_id_success`: Verify get_user_by_id returns correct user
- `test_get_user_by_id_not_found`: Verify None returned for non-existent user
- `test_promote_user_success`: Verify is_admin updated to True
- `test_revoke_admin_success`: Verify is_admin updated to False
- `test_audit_logging`: Verify all operations are logged correctly

### Integration Testing (E2E)

Integration tests will verify complete API workflows with real database:

- `test_list_users_as_admin`: Admin can list all users
- `test_list_users_as_regular_user`: Regular user gets 403
- `test_list_users_unauthenticated`: Unauthenticated request gets 401
- `test_get_user_as_admin`: Admin can get user details
- `test_get_user_as_regular_user`: Regular user gets 403
- `test_get_user_not_found`: Non-existent user returns 404
- `test_promote_user_as_admin`: Admin can promote user
- `test_promote_user_as_regular_user`: Regular user gets 403
- `test_promote_nonexistent_user`: Non-existent user returns 404
- `test_revoke_admin_as_admin`: Admin can revoke admin status
- `test_revoke_admin_as_regular_user`: Regular user gets 403
- `test_revoke_nonexistent_user`: Non-existent user returns 404
- `test_pagination_correctness`: Verify pagination returns correct subsets

### Property-Based Testing

We will use `pytest` with `hypothesis` for property-based testing:

- Generate random sets of users with varying admin status
- Generate random pagination parameters
- Verify properties hold across all generated inputs
- Test edge cases (empty database, single user, all admins, etc.)

### Testing Framework

- **Framework**: pytest with async support
- **Property Testing**: hypothesis for generating test data
- **Database**: In-memory SQLite for fast test execution
- **Fixtures**: Reusable fixtures for creating test users and admin users
- **Coverage Target**: 90%+ code coverage for new code

## API Documentation

All endpoints will be automatically documented via FastAPI's OpenAPI integration:

- Swagger UI available at `/docs`
- ReDoc available at `/redoc`
- OpenAPI JSON schema at `/openapi.json`

Each endpoint will include:
- Description of functionality
- Request parameters and body schemas
- Response schemas for success and error cases
- Authentication requirements
- Authorization requirements (admin-only)
- Example requests and responses

## Security Considerations

### Authentication

- All endpoints require valid JWT token
- Token must contain valid user address
- Token expiration enforced (default: 240 minutes)

### Authorization

- Admin-only endpoints protected by `require_admin` dependency
- Regular users cannot access user management endpoints
- Users cannot modify their own admin status (requires another admin)

### Audit Logging

- All user management operations logged with:
  - Timestamp
  - Admin user address
  - Target user address (if applicable)
  - Action performed
  - Result (success/failure)
- Logs stored in structured format for analysis
- Sensitive information (private keys) never logged

### Input Validation

- Wallet addresses validated as 42-character hex strings
- User IDs validated as positive integers
- Pagination parameters validated (skip >= 0, limit > 0)
- All inputs sanitized to prevent injection attacks

## Deployment Considerations

### Database Migrations

No database migrations required - User model already exists with all necessary fields.

### Backward Compatibility

- New endpoints do not affect existing functionality
- Existing authentication flow unchanged
- Existing User model unchanged

### Performance

- List users endpoint supports pagination to handle large user bases
- Database queries use indexes on user.id and user.address
- No N+1 query problems - single query per endpoint

### Monitoring

- Log all user management operations for audit trail
- Monitor 403/401 errors for potential security issues
- Track endpoint usage for capacity planning

---

**Document Version**: 1.0
**Last Updated**: November 22, 2025
**Status**: Ready for Implementation
