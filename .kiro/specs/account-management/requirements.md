# Requirements Document

## Introduction

This document specifies the requirements for trading account management in the AI Trading Agent API. The system supports multiple trading accounts per user, each with independent configuration for API credentials, LLM models, trading parameters, and risk management settings. This specification enables users to manage their trading accounts and allows the system to operate multiple accounts concurrently with proper isolation.

## Glossary

- **Account**: A trading account entity with its own API credentials, trading configuration, and state
- **User**: An authenticated entity (via Ethereum wallet) that owns one or more trading accounts
- **Admin User**: A User with elevated privileges for system-wide management
- **Account Status**: The operational state of an account:
  - **active**: Account is fully operational and executing trades
  - **paused**: Account temporarily stops trading but retains all data and can be resumed instantly
  - **stopped**: Account is permanently disabled; requires re-activation and may need credential re-validation
- **API Credentials**: AsterDEX API key and secret for exchange access
- **LLM Model**: The language model used for trading decisions (e.g., Grok-4, DeepSeek)
- **Paper Trading**: Simulated trading mode without real funds, using arbitrary balance values
- **Real Trading**: Live trading mode connected to AsterDEX exchange with real funds
- **Balance Sync**: Process of fetching current account balance from AsterDEX API

## Account Fields Reference

The Account entity contains the following fields:

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique account identifier |
| name | string | Account name (unique) |
| description | text | Optional account description |
| status | string | Account status: active, paused, stopped |
| user_id | integer | Owner user ID |
| api_key | string | AsterDEX API key (encrypted) |
| api_secret | string | AsterDEX API secret (encrypted) |
| api_passphrase | string | AsterDEX API passphrase (optional) |
| leverage | float | Trading leverage (1.0-20.0) |
| max_position_size_usd | float | Maximum position size in USD |
| risk_per_trade | float | Risk percentage per trade (0.01-0.10) |
| maker_fee_bps | float | Maker fee in basis points |
| taker_fee_bps | float | Taker fee in basis points |
| balance_usd | float | Current account balance in USD |
| is_paper_trading | boolean | True for paper trading, False for real trading |
| is_enabled | boolean | Whether account is enabled for trading |
| created_at | datetime | Account creation timestamp |
| updated_at | datetime | Last update timestamp |

## Requirements

### Requirement 1

**User Story:** As a user, I want to create trading accounts with custom configurations, so that I can manage multiple trading strategies independently.

#### Acceptance Criteria

1. WHEN a user creates an account with valid configuration THEN the System SHALL persist the account with all provided settings
2. WHEN a user creates an account with a duplicate name THEN the System SHALL return a 400 Bad Request error with a descriptive message
3. WHEN a user creates an account without required fields THEN the System SHALL return a 422 Validation Error
4. WHEN an account is created THEN the System SHALL associate the account with the authenticated user
5. WHEN an account is created THEN the System SHALL set the default status to "active" and is_enabled to true

### Requirement 2

**User Story:** As a user, I want to list and view my trading accounts, so that I can monitor their configurations and status.

#### Acceptance Criteria

1. WHEN a user requests their account list THEN the System SHALL return all accounts owned by that user
2. WHEN a user requests a specific account by ID THEN the System SHALL return the account details if the user owns the account
3. WHEN a user requests an account they do not own THEN the System SHALL return a 403 Forbidden error
4. WHEN an admin user requests any account THEN the System SHALL return the account details regardless of ownership
5. WHEN the account list is returned THEN the System SHALL include account ID, name, status, trading mode, and configuration for each account

### Requirement 3

**User Story:** As a user, I want to update my trading account configurations, so that I can adjust trading parameters and risk settings.

#### Acceptance Criteria

1. WHEN a user updates their own account THEN the System SHALL persist the updated configuration
2. WHEN a user attempts to update an account they do not own THEN the System SHALL return a 403 Forbidden error
3. WHEN an admin user updates any account THEN the System SHALL persist the updated configuration
4. WHEN an account is updated THEN the System SHALL update the updated_at timestamp
5. WHEN a user updates account status THEN the System SHALL validate the status is one of: active, paused, stopped

### Requirement 4

**User Story:** As a user, I want to delete my trading accounts, so that I can remove accounts I no longer need.

#### Acceptance Criteria

1. WHEN a user deletes their own account THEN the System SHALL remove the account and all associated data
2. WHEN a user attempts to delete an account they do not own THEN the System SHALL return a 403 Forbidden error
3. WHEN an admin user deletes any account THEN the System SHALL remove the account and all associated data
4. WHEN an account is deleted THEN the System SHALL cascade delete all related positions, orders, and trades
5. WHEN an account with active positions is deleted THEN the System SHALL warn the user and require confirmation

### Requirement 5

**User Story:** As a user, I want to configure per-account API credentials, so that each account can connect to different exchange accounts.

#### Acceptance Criteria

1. WHEN a user sets API credentials for an account THEN the System SHALL encrypt and store the credentials securely
2. WHEN API credentials are retrieved THEN the System SHALL mask sensitive values in the response
3. WHEN a user updates API credentials THEN the System SHALL validate the credential format before saving
4. WHEN API credentials are invalid THEN the System SHALL return a 400 Bad Request error with validation details
5. WHEN an account has no API credentials THEN the System SHALL require is_paper_trading to be true

### Requirement 6

**User Story:** As a user, I want to switch between paper trading and real trading modes, so that I can test strategies before using real funds.

#### Acceptance Criteria

1. WHEN a user sets is_paper_trading to true THEN the System SHALL allow arbitrary balance_usd values to be set manually
2. WHEN a user sets is_paper_trading to false THEN the System SHALL require valid API credentials to be configured
3. WHEN switching from paper to real trading THEN the System SHALL validate API credentials are present and valid
4. WHEN in paper trading mode THEN the System SHALL use the manually set balance_usd for all calculations
5. WHEN in real trading mode THEN the System SHALL use the synced balance from AsterDEX API

### Requirement 7

**User Story:** As a user, I want to sync my account balance from AsterDEX, so that I can see my real trading balance.

#### Acceptance Criteria

1. WHEN a user requests balance sync for a real trading account THEN the System SHALL fetch the current balance from AsterDEX API
2. WHEN balance sync succeeds THEN the System SHALL update the account's balance_usd field with the fetched value
3. WHEN balance sync fails due to invalid credentials THEN the System SHALL return a 401 Unauthorized error
4. WHEN balance sync fails due to API errors THEN the System SHALL return a 502 Bad Gateway error with details
5. WHEN balance sync is requested for a paper trading account THEN the System SHALL return a 400 Bad Request error

### Requirement 8

**User Story:** As a user, I want to manage account status, so that I can pause or stop trading without deleting the account.

#### Acceptance Criteria

1. WHEN a user sets status to "paused" THEN the System SHALL stop executing new trades but retain all account data
2. WHEN a user sets status to "active" from "paused" THEN the System SHALL resume trading immediately
3. WHEN a user sets status to "stopped" THEN the System SHALL disable the account and require explicit re-activation
4. WHEN a user sets status to "active" from "stopped" THEN the System SHALL validate API credentials before activating
5. WHEN an account status changes THEN the System SHALL log the status change with timestamp and reason

### Requirement 9

**User Story:** As a system operator, I want account isolation to prevent cross-account interference, so that each account operates independently.

#### Acceptance Criteria

1. WHEN trading decisions are made THEN the System SHALL execute decisions independently for each account
2. WHEN positions are tracked THEN the System SHALL maintain separate position tracking per account
3. WHEN performance metrics are calculated THEN the System SHALL calculate metrics independently per account
4. WHEN one account experiences API failures THEN the System SHALL continue operating other accounts normally
5. WHEN querying data with account_id filter THEN the System SHALL return only data for the specified account

### Requirement 10

**User Story:** As a developer, I want comprehensive API documentation for account management endpoints, so that I can integrate these features correctly.

#### Acceptance Criteria

1. WHEN the API documentation is accessed THEN the System SHALL include all account management endpoints with request/response schemas
2. WHEN the API documentation is accessed THEN the System SHALL specify authentication and authorization requirements for each endpoint
3. WHEN the API documentation is accessed THEN the System SHALL provide example requests and responses for each endpoint
4. WHEN the API documentation is accessed THEN the System SHALL document all possible error responses with status codes
5. WHEN the API documentation is accessed THEN the System SHALL include account ownership rules and admin override capabilities

### Requirement 11

**User Story:** As a quality assurance engineer, I want comprehensive test coverage for account management features, so that I can ensure the system behaves correctly under all conditions.

#### Acceptance Criteria

1. WHEN unit tests are executed THEN the System SHALL test account service functions with mocked database access
2. WHEN unit tests are executed THEN the System SHALL test account validation logic with valid and invalid inputs
3. WHEN integration tests are executed THEN the System SHALL test account relationships with other modules using mocked database access
4. WHEN integration tests are executed THEN the System SHALL test account-position, account-order, and account-trade relationships
5. WHEN e2e tests are executed THEN the System SHALL test HTTP API endpoints with real database access
6. WHEN e2e tests are executed THEN the System SHALL test account CRUD operations with owner authentication
7. WHEN e2e tests are executed THEN the System SHALL test account access control with non-owner authentication
8. WHEN property-based tests are executed THEN the System SHALL verify account isolation properties hold across random inputs

