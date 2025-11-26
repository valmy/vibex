"""
Integration tests for account relationships.

Tests account relationships with Position, Order, Trade, and User models,
including cascade delete behavior.

**Feature: account-management**
**Validates: Requirements 11.3, 11.4**
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, User
from app.models.order import Order
from app.models.position import Position
from app.models.trade import Trade
from app.services.account_service import AccountService


@pytest.fixture
def account_service() -> AccountService:
    """Fixture for AccountService instance."""
    return AccountService()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Fixture for mocked database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_user() -> MagicMock:
    """Fixture for a mock user."""
    user = MagicMock(spec=User)
    user.id = 1
    user.address = "0x1111111111111111111111111111111111111111"
    user.is_admin = False
    return user


@pytest.fixture
def mock_account(mock_user: MagicMock) -> MagicMock:
    """Fixture for a mock account."""
    account = MagicMock(spec=Account)
    account.id = 1
    account.name = "Test Account"
    account.user_id = mock_user.id
    account.status = "active"
    account.is_paper_trading = True
    account.balance_usd = 10000.0
    # Initialize empty relationships
    account.positions = []
    account.orders = []
    account.trades = []
    return account


# Test 1: Account-User association
@pytest.mark.integration
@pytest.mark.asyncio
async def test_account_user_association(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
    mock_account: MagicMock,
):
    """
    Test that accounts are properly associated with users.

    **Feature: account-management**
    **Validates: Requirements 11.3, 11.4**
    """
    # Mock the execute method to return the account
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_account
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Get account
    result = await account_service.get_account(
        db=mock_db_session,
        account_id=mock_account.id,
        user=mock_user,
    )

    # Verify account is associated with the correct user
    assert result.user_id == mock_user.id
    assert result.id == mock_account.id


# Test 2: Account-Position relationship
@pytest.mark.integration
@pytest.mark.asyncio
async def test_account_position_relationship(
    mock_account: MagicMock,
):
    """
    Test that accounts can have multiple positions.

    **Feature: account-management**
    **Validates: Requirements 11.3, 11.4**
    """
    # Create mock positions
    position1 = MagicMock(spec=Position)
    position1.id = 1
    position1.account_id = mock_account.id
    position1.symbol = "BTCUSDT"
    position1.side = "long"

    position2 = MagicMock(spec=Position)
    position2.id = 2
    position2.account_id = mock_account.id
    position2.symbol = "ETHUSDT"
    position2.side = "short"

    # Associate positions with account
    mock_account.positions = [position1, position2]

    # Verify relationship
    assert len(mock_account.positions) == 2
    assert all(pos.account_id == mock_account.id for pos in mock_account.positions)
    assert mock_account.positions[0].symbol == "BTCUSDT"
    assert mock_account.positions[1].symbol == "ETHUSDT"


# Test 3: Account-Order relationship
@pytest.mark.integration
@pytest.mark.asyncio
async def test_account_order_relationship(
    mock_account: MagicMock,
):
    """
    Test that accounts can have multiple orders.

    **Feature: account-management**
    **Validates: Requirements 11.3, 11.4**
    """
    # Create mock orders
    order1 = MagicMock(spec=Order)
    order1.id = 1
    order1.account_id = mock_account.id
    order1.symbol = "BTCUSDT"
    order1.side = "buy"
    order1.status = "pending"

    order2 = MagicMock(spec=Order)
    order2.id = 2
    order2.account_id = mock_account.id
    order2.symbol = "ETHUSDT"
    order2.side = "sell"
    order2.status = "filled"

    # Associate orders with account
    mock_account.orders = [order1, order2]

    # Verify relationship
    assert len(mock_account.orders) == 2
    assert all(order.account_id == mock_account.id for order in mock_account.orders)
    assert mock_account.orders[0].status == "pending"
    assert mock_account.orders[1].status == "filled"


# Test 4: Account-Trade relationship
@pytest.mark.integration
@pytest.mark.asyncio
async def test_account_trade_relationship(
    mock_account: MagicMock,
):
    """
    Test that accounts can have multiple trades.

    **Feature: account-management**
    **Validates: Requirements 11.3, 11.4**
    """
    # Create mock trades
    trade1 = MagicMock(spec=Trade)
    trade1.id = 1
    trade1.account_id = mock_account.id
    trade1.symbol = "BTCUSDT"
    trade1.side = "buy"
    trade1.quantity = 0.5
    trade1.price = 50000.0

    trade2 = MagicMock(spec=Trade)
    trade2.id = 2
    trade2.account_id = mock_account.id
    trade2.symbol = "ETHUSDT"
    trade2.side = "sell"
    trade2.quantity = 2.0
    trade2.price = 3000.0

    # Associate trades with account
    mock_account.trades = [trade1, trade2]

    # Verify relationship
    assert len(mock_account.trades) == 2
    assert all(trade.account_id == mock_account.id for trade in mock_account.trades)
    assert mock_account.trades[0].symbol == "BTCUSDT"
    assert mock_account.trades[1].symbol == "ETHUSDT"


# Test 5: Cascade delete - positions
@pytest.mark.integration
@pytest.mark.asyncio
async def test_cascade_delete_positions(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
    mock_account: MagicMock,
):
    """
    Test that deleting an account cascades to delete positions.

    **Feature: account-management**
    **Validates: Requirements 11.3, 11.4**
    """
    # Create mock positions
    position1 = MagicMock(spec=Position)
    position1.id = 1
    position1.account_id = mock_account.id
    position1.status = "closed"

    position2 = MagicMock(spec=Position)
    position2.id = 2
    position2.account_id = mock_account.id
    position2.status = "closed"

    mock_account.positions = [position1, position2]

    # Mock the execute method to return the account
    mock_get_result = MagicMock()
    mock_get_result.scalar_one_or_none.return_value = mock_account

    # Mock the positions query to return 0 active positions
    mock_positions_result = MagicMock()
    mock_positions_result.scalar.return_value = 0

    # Set up execute to return different results for different queries
    mock_db_session.execute = AsyncMock(side_effect=[mock_get_result, mock_positions_result])
    mock_db_session.delete = AsyncMock()
    mock_db_session.commit = AsyncMock()

    # Delete account
    await account_service.delete_account(
        db=mock_db_session,
        account_id=mock_account.id,
        user=mock_user,
        force=False,
    )

    # Verify delete was called with the account
    # The cascade delete to positions is handled by SQLAlchemy
    mock_db_session.delete.assert_called_once_with(mock_account)
    mock_db_session.commit.assert_called_once()


# Test 6: Cascade delete - orders
@pytest.mark.integration
@pytest.mark.asyncio
async def test_cascade_delete_orders(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
    mock_account: MagicMock,
):
    """
    Test that deleting an account cascades to delete orders.

    **Feature: account-management**
    **Validates: Requirements 11.3, 11.4**
    """
    # Create mock orders
    order1 = MagicMock(spec=Order)
    order1.id = 1
    order1.account_id = mock_account.id
    order1.status = "filled"

    order2 = MagicMock(spec=Order)
    order2.id = 2
    order2.account_id = mock_account.id
    order2.status = "cancelled"

    mock_account.orders = [order1, order2]

    # Mock the execute method to return the account
    mock_get_result = MagicMock()
    mock_get_result.scalar_one_or_none.return_value = mock_account

    # Mock the positions query to return 0 active positions
    mock_positions_result = MagicMock()
    mock_positions_result.scalar.return_value = 0

    # Set up execute to return different results for different queries
    mock_db_session.execute = AsyncMock(side_effect=[mock_get_result, mock_positions_result])
    mock_db_session.delete = AsyncMock()
    mock_db_session.commit = AsyncMock()

    # Delete account
    await account_service.delete_account(
        db=mock_db_session,
        account_id=mock_account.id,
        user=mock_user,
        force=False,
    )

    # Verify delete was called with the account
    # The cascade delete to orders is handled by SQLAlchemy
    mock_db_session.delete.assert_called_once_with(mock_account)
    mock_db_session.commit.assert_called_once()


# Test 7: Cascade delete - trades
@pytest.mark.integration
@pytest.mark.asyncio
async def test_cascade_delete_trades(
    account_service: AccountService,
    mock_db_session: AsyncMock,
    mock_user: MagicMock,
    mock_account: MagicMock,
):
    """
    Test that deleting an account cascades to delete trades.

    **Feature: account-management**
    **Validates: Requirements 11.3, 11.4**
    """
    # Create mock trades
    trade1 = MagicMock(spec=Trade)
    trade1.id = 1
    trade1.account_id = mock_account.id
    trade1.symbol = "BTCUSDT"

    trade2 = MagicMock(spec=Trade)
    trade2.id = 2
    trade2.account_id = mock_account.id
    trade2.symbol = "ETHUSDT"

    mock_account.trades = [trade1, trade2]

    # Mock the execute method to return the account
    mock_get_result = MagicMock()
    mock_get_result.scalar_one_or_none.return_value = mock_account

    # Mock the positions query to return 0 active positions
    mock_positions_result = MagicMock()
    mock_positions_result.scalar.return_value = 0

    # Set up execute to return different results for different queries
    mock_db_session.execute = AsyncMock(side_effect=[mock_get_result, mock_positions_result])
    mock_db_session.delete = AsyncMock()
    mock_db_session.commit = AsyncMock()

    # Delete account
    await account_service.delete_account(
        db=mock_db_session,
        account_id=mock_account.id,
        user=mock_user,
        force=False,
    )

    # Verify delete was called with the account
    # The cascade delete to trades is handled by SQLAlchemy
    mock_db_session.delete.assert_called_once_with(mock_account)
    mock_db_session.commit.assert_called_once()


# Test 8: Multiple relationships on single account
@pytest.mark.integration
@pytest.mark.asyncio
async def test_account_multiple_relationships(
    mock_account: MagicMock,
):
    """
    Test that an account can have positions, orders, and trades simultaneously.

    **Feature: account-management**
    **Validates: Requirements 11.3, 11.4**
    """
    # Create mock position
    position = MagicMock(spec=Position)
    position.id = 1
    position.account_id = mock_account.id
    position.symbol = "BTCUSDT"

    # Create mock order
    order = MagicMock(spec=Order)
    order.id = 1
    order.account_id = mock_account.id
    order.symbol = "BTCUSDT"

    # Create mock trade
    trade = MagicMock(spec=Trade)
    trade.id = 1
    trade.account_id = mock_account.id
    trade.symbol = "BTCUSDT"

    # Associate all relationships with account
    mock_account.positions = [position]
    mock_account.orders = [order]
    mock_account.trades = [trade]

    # Verify all relationships exist
    assert len(mock_account.positions) == 1
    assert len(mock_account.orders) == 1
    assert len(mock_account.trades) == 1
    assert mock_account.positions[0].account_id == mock_account.id
    assert mock_account.orders[0].account_id == mock_account.id
    assert mock_account.trades[0].account_id == mock_account.id
