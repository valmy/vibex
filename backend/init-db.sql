-- Initialize TimescaleDB extension (required for time-series optimization)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create schema for trading data
CREATE SCHEMA IF NOT EXISTS trading;

-- Users table
CREATE TABLE IF NOT EXISTS trading.users (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    address VARCHAR(42) NOT NULL UNIQUE,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_trading_users_address ON trading.users (address);

-- Accounts table
CREATE TABLE IF NOT EXISTS trading.accounts (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    user_id INTEGER NOT NULL REFERENCES trading.users(id),
    api_key VARCHAR(255),
    api_secret VARCHAR(255),
    api_passphrase VARCHAR(255),
    leverage DOUBLE PRECISION NOT NULL DEFAULT 2.0,
    max_position_size_usd DOUBLE PRECISION NOT NULL DEFAULT 10000.0,
    risk_per_trade DOUBLE PRECISION NOT NULL DEFAULT 0.02,
    maker_fee_bps DOUBLE PRECISION NOT NULL DEFAULT 5.0,
    taker_fee_bps DOUBLE PRECISION NOT NULL DEFAULT 20.0,
    balance_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    is_paper_trading BOOLEAN NOT NULL DEFAULT FALSE,
    is_multi_account BOOLEAN NOT NULL DEFAULT FALSE,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS ix_trading_accounts_name ON trading.accounts (name);

-- Challenges table
CREATE TABLE IF NOT EXISTS trading.challenges (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    address VARCHAR(42) NOT NULL,
    challenge VARCHAR(64) NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_trading_challenges_address ON trading.challenges (address);

-- Strategies table
CREATE TABLE IF NOT EXISTS trading.strategies (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    strategy_id VARCHAR(100) NOT NULL UNIQUE,
    strategy_name VARCHAR(255) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    description TEXT,
    prompt_template TEXT NOT NULL,
    timeframe_preference JSON NOT NULL,
    max_positions INTEGER NOT NULL DEFAULT 3,
    position_sizing VARCHAR(50) NOT NULL DEFAULT 'percentage',
    order_preference VARCHAR(50) NOT NULL DEFAULT 'any',
    funding_rate_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    risk_parameters JSON NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_by VARCHAR(100),
    version VARCHAR(20) NOT NULL DEFAULT '1.0'
);
CREATE INDEX IF NOT EXISTS idx_strategy_type ON trading.strategies (strategy_type);
CREATE INDEX IF NOT EXISTS idx_strategy_active ON trading.strategies (is_active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_id_unique ON trading.strategies (strategy_id);

-- Strategy Assignments table
CREATE TABLE IF NOT EXISTS trading.strategy_assignments (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    account_id INTEGER NOT NULL REFERENCES trading.accounts(id),
    strategy_id INTEGER NOT NULL REFERENCES trading.strategies(id),
    assigned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    assigned_by VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    previous_strategy_id INTEGER REFERENCES trading.strategies(id),
    switch_reason TEXT,
    total_trades INTEGER NOT NULL DEFAULT 0,
    total_pnl DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    win_rate DOUBLE PRECISION,
    deactivated_at TIMESTAMP WITHOUT TIME ZONE,
    deactivated_by VARCHAR(100),
    deactivation_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_strategy_assignment_account ON trading.strategy_assignments (account_id);
CREATE INDEX IF NOT EXISTS idx_strategy_assignment_strategy ON trading.strategy_assignments (strategy_id);
CREATE INDEX IF NOT EXISTS idx_strategy_assignment_active ON trading.strategy_assignments (is_active);

-- Strategy Performances table
CREATE TABLE IF NOT EXISTS trading.strategy_performances (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    strategy_id INTEGER NOT NULL REFERENCES trading.strategies(id),
    account_id INTEGER REFERENCES trading.accounts(id),
    period_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    period_end TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    period_days INTEGER NOT NULL,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    win_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_pnl DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_win DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_loss DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    max_win DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    max_loss DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    max_drawdown DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    sharpe_ratio DOUBLE PRECISION,
    sortino_ratio DOUBLE PRECISION,
    profit_factor DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_trade_duration_hours DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_volume_traded DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_fees_paid DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_funding_paid DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_liquidations INTEGER NOT NULL DEFAULT 0,
    var_95 DOUBLE PRECISION,
    max_consecutive_losses INTEGER NOT NULL DEFAULT 0,
    max_consecutive_wins INTEGER NOT NULL DEFAULT 0,
    additional_metrics JSON
);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_strategy ON trading.strategy_performances (strategy_id);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_account ON trading.strategy_performances (account_id);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_period ON trading.strategy_performances (period_start, period_end);

-- Positions table
CREATE TABLE IF NOT EXISTS trading.positions (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    account_id INTEGER NOT NULL REFERENCES trading.accounts(id),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    entry_price DOUBLE PRECISION NOT NULL,
    current_price DOUBLE PRECISION NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    leverage DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    entry_value DOUBLE PRECISION NOT NULL,
    current_value DOUBLE PRECISION NOT NULL,
    unrealized_pnl DOUBLE PRECISION NOT NULL,
    unrealized_pnl_percent DOUBLE PRECISION NOT NULL,
    stop_loss DOUBLE PRECISION,
    take_profit DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_position_account_id ON trading.positions (account_id);
CREATE INDEX IF NOT EXISTS idx_position_symbol ON trading.positions (symbol);
CREATE INDEX IF NOT EXISTS idx_position_status ON trading.positions (status);

-- Orders table
CREATE TABLE IF NOT EXISTS trading.orders (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    account_id INTEGER NOT NULL REFERENCES trading.accounts(id),
    position_id INTEGER REFERENCES trading.positions(id),
    exchange_order_id VARCHAR(255) UNIQUE,
    symbol VARCHAR(50) NOT NULL,
    order_type VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION,
    stop_price DOUBLE PRECISION,
    time_in_force VARCHAR(20) NOT NULL DEFAULT 'GTC',
    filled_quantity DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    average_price DOUBLE PRECISION,
    total_cost DOUBLE PRECISION,
    commission DOUBLE PRECISION NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_order_account_id ON trading.orders (account_id);
CREATE INDEX IF NOT EXISTS idx_order_position_id ON trading.orders (position_id);
CREATE INDEX IF NOT EXISTS idx_order_symbol ON trading.orders (symbol);
CREATE INDEX IF NOT EXISTS idx_order_status ON trading.orders (status);

-- Trades table
CREATE TABLE IF NOT EXISTS trading.trades (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    account_id INTEGER NOT NULL REFERENCES trading.accounts(id),
    position_id INTEGER REFERENCES trading.positions(id),
    order_id INTEGER REFERENCES trading.orders(id),
    exchange_trade_id VARCHAR(255) UNIQUE,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    total_cost DOUBLE PRECISION NOT NULL,
    commission DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    commission_asset VARCHAR(50),
    pnl DOUBLE PRECISION,
    pnl_percent DOUBLE PRECISION,
    roi DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_trade_account_id ON trading.trades (account_id);
CREATE INDEX IF NOT EXISTS idx_trade_position_id ON trading.trades (position_id);
CREATE INDEX IF NOT EXISTS idx_trade_order_id ON trading.trades (order_id);
CREATE INDEX IF NOT EXISTS idx_trade_symbol ON trading.trades (symbol);

-- Diary Entries table
CREATE TABLE IF NOT EXISTS trading.diary_entries (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    account_id INTEGER NOT NULL REFERENCES trading.accounts(id),
    entry_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    tags VARCHAR(255),
    sentiment VARCHAR(20),
    confidence VARCHAR(20)
);
CREATE INDEX IF NOT EXISTS idx_diary_account_id ON trading.diary_entries (account_id);
CREATE INDEX IF NOT EXISTS idx_diary_entry_type ON trading.diary_entries (entry_type);

-- Performance Metrics table
CREATE TABLE IF NOT EXISTS trading.performance_metrics (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    account_id INTEGER NOT NULL REFERENCES trading.accounts(id),
    period VARCHAR(50) NOT NULL,
    period_start VARCHAR(50) NOT NULL,
    period_end VARCHAR(50) NOT NULL,
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    win_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_pnl DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_pnl_percent DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    average_win DOUBLE PRECISION,
    average_loss DOUBLE PRECISION,
    profit_factor DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    max_drawdown_percent DOUBLE PRECISION,
    sharpe_ratio DOUBLE PRECISION,
    sortino_ratio DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_performance_account_id ON trading.performance_metrics (account_id);
CREATE INDEX IF NOT EXISTS idx_performance_period ON trading.performance_metrics (period);

-- Decisions table (supports both single-asset and multi-asset decisions)
CREATE TABLE IF NOT EXISTS trading.decisions (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    account_id INTEGER NOT NULL REFERENCES trading.accounts(id),
    strategy_id VARCHAR(100) NOT NULL,
    -- Multi-asset decision fields
    asset_decisions JSON,
    portfolio_rationale TEXT,
    total_allocation_usd DOUBLE PRECISION,
    portfolio_risk_level VARCHAR(10),
    -- Legacy single-asset decision fields (nullable for multi-asset decisions)
    symbol VARCHAR(20),
    action VARCHAR(20),
    allocation_usd DOUBLE PRECISION DEFAULT 0.0,
    tp_price DOUBLE PRECISION,
    sl_price DOUBLE PRECISION,
    exit_plan TEXT,
    rationale TEXT,
    confidence DOUBLE PRECISION,
    risk_level VARCHAR(10),
    "timestamp" TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    position_adjustment JSON,
    order_adjustment JSON,
    model_used VARCHAR(100) NOT NULL,
    api_cost DOUBLE PRECISION,
    processing_time_ms DOUBLE PRECISION NOT NULL,
    validation_passed BOOLEAN NOT NULL DEFAULT FALSE,
    validation_errors JSON,
    validation_warnings JSON,
    market_context JSON NOT NULL,
    account_context JSON NOT NULL,
    risk_metrics JSON,
    executed BOOLEAN NOT NULL DEFAULT FALSE,
    executed_at TIMESTAMP WITHOUT TIME ZONE,
    execution_price DOUBLE PRECISION,
    execution_errors JSON
);
CREATE INDEX IF NOT EXISTS idx_decision_account_symbol ON trading.decisions (account_id, symbol);
CREATE INDEX IF NOT EXISTS idx_decision_timestamp ON trading.decisions ("timestamp");
CREATE INDEX IF NOT EXISTS idx_decision_action ON trading.decisions (action);
CREATE INDEX IF NOT EXISTS idx_decision_strategy ON trading.decisions (strategy_id);

-- Decision Results table
CREATE TABLE IF NOT EXISTS trading.decision_results (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    decision_id INTEGER NOT NULL REFERENCES trading.decisions(id),
    outcome VARCHAR(20),
    realized_pnl DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION,
    percentage_return DOUBLE PRECISION,
    entry_price DOUBLE PRECISION,
    exit_price DOUBLE PRECISION,
    position_size DOUBLE PRECISION,
    opened_at TIMESTAMP WITHOUT TIME ZONE,
    closed_at TIMESTAMP WITHOUT TIME ZONE,
    duration_hours DOUBLE PRECISION,
    max_favorable_excursion DOUBLE PRECISION,
    max_adverse_excursion DOUBLE PRECISION,
    slippage DOUBLE PRECISION,
    fees_paid DOUBLE PRECISION,
    hit_tp BOOLEAN,
    hit_sl BOOLEAN,
    manual_close BOOLEAN NOT NULL DEFAULT FALSE,
    market_conditions JSON,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_decision_result_decision ON trading.decision_results (decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_result_outcome ON trading.decision_results (outcome);
CREATE INDEX IF NOT EXISTS idx_decision_result_closed_at ON trading.decision_results (closed_at);

-- Market Data table
-- Note: Using DOUBLE PRECISION for all numeric columns for consistency and precision.
-- This is a high-volume TimescaleDB hypertable; if storage becomes a concern,
-- consider using REAL for non-financial metrics like number_of_trades.
CREATE TABLE IF NOT EXISTS trading.market_data (
    time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    id SERIAL,
    symbol VARCHAR(50) NOT NULL,
    interval VARCHAR(20) NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    quote_asset_volume DOUBLE PRECISION,
    number_of_trades DOUBLE PRECISION,
    taker_buy_base_asset_volume DOUBLE PRECISION,
    taker_buy_quote_asset_volume DOUBLE PRECISION,
    funding_rate DOUBLE PRECISION,
    PRIMARY KEY (time, id)
);
CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON trading.market_data (symbol);
CREATE INDEX IF NOT EXISTS idx_market_data_id ON trading.market_data (id);

-- Convert market_data to hypertable for time-series optimization (TimescaleDB)
SELECT create_hypertable('trading.market_data', 'time', if_not_exists => TRUE);

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA trading TO trading_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA trading TO trading_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA trading TO trading_user;