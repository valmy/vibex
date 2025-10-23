-- Initialize TimescaleDB extension (required for time-series optimization)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create schema for trading data
CREATE SCHEMA IF NOT EXISTS trading;

-- Accounts table
CREATE TABLE IF NOT EXISTS trading.accounts (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    balance DECIMAL(20, 8) DEFAULT 0,
    available_balance DECIMAL(20, 8) DEFAULT 0,
    total_equity DECIMAL(20, 8) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Market data table (time-series)
CREATE TABLE IF NOT EXISTS trading.market_data (
    time TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open DECIMAL(20, 8),
    high DECIMAL(20, 8),
    low DECIMAL(20, 8),
    close DECIMAL(20, 8),
    volume DECIMAL(20, 8),
    interval VARCHAR(10),
    PRIMARY KEY (time, symbol)
);

-- Convert market_data to hypertable for time-series optimization (TimescaleDB)
-- This must be done after the table is created
SELECT create_hypertable('trading.market_data', 'time', if_not_exists => TRUE);

-- Create index on symbol for faster queries
CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON trading.market_data (symbol, time DESC);

-- Positions table
CREATE TABLE IF NOT EXISTS trading.positions (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(255) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10),
    entry_price DECIMAL(20, 8),
    current_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8),
    leverage DECIMAL(5, 2),
    status VARCHAR(50) DEFAULT 'open',
    pnl DECIMAL(20, 8),
    pnl_percentage DECIMAL(10, 4),
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES trading.accounts(account_id)
);

-- Orders table
CREATE TABLE IF NOT EXISTS trading.orders (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(255) NOT NULL,
    order_id VARCHAR(255) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10),
    order_type VARCHAR(50),
    quantity DECIMAL(20, 8),
    price DECIMAL(20, 8),
    status VARCHAR(50) DEFAULT 'pending',
    filled_quantity DECIMAL(20, 8) DEFAULT 0,
    average_fill_price DECIMAL(20, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES trading.accounts(account_id)
);

-- Trades table (executed trades)
CREATE TABLE IF NOT EXISTS trading.trades (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(255) NOT NULL,
    trade_id VARCHAR(255) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10),
    quantity DECIMAL(20, 8),
    price DECIMAL(20, 8),
    commission DECIMAL(20, 8),
    pnl DECIMAL(20, 8),
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES trading.accounts(account_id)
);

-- Trading diary/events table
CREATE TABLE IF NOT EXISTS trading.diary_entries (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(255) NOT NULL,
    entry_type VARCHAR(50),
    title VARCHAR(255),
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES trading.accounts(account_id)
);

-- Performance metrics table
CREATE TABLE IF NOT EXISTS trading.performance_metrics (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    total_return DECIMAL(10, 4),
    daily_return DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    sortino_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    win_rate DECIMAL(10, 4),
    profit_factor DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, date),
    FOREIGN KEY (account_id) REFERENCES trading.accounts(account_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_positions_account ON trading.positions(account_id);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON trading.positions(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_account ON trading.orders(account_id);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON trading.orders(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_account ON trading.trades(account_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trading.trades(symbol);
CREATE INDEX IF NOT EXISTS idx_diary_account ON trading.diary_entries(account_id);
CREATE INDEX IF NOT EXISTS idx_performance_account ON trading.performance_metrics(account_id);

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA trading TO trading_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA trading TO trading_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA trading TO trading_user;

