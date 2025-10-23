# AI Trading Agent - Requirements Document

## 1. Project Overview

### 1.1 Purpose
This document specifies the requirements for recreating and enhancing the AI-powered cryptocurrency trading agent that leverages Large Language Models (LLMs) to analyze real-time market data and execute trades on the AsterDEX decentralized exchange.

### 1.2 Scope
The system is designed to:
- Continuously monitor specified cryptocurrency assets at configurable intervals
- Make data-driven trading decisions using LLM analysis
- Execute trades with automated risk management (take-profit, stop-loss)
- Provide monitoring and debugging capabilities through API endpoints
- Maintain comprehensive audit trails and logging

### 1.3 Key Features
- Multi-asset trading support
- LLM-powered decision making with structured outputs
- Real-time market data integration
- Automated risk management
- State reconciliation and error recovery
- Comprehensive logging and monitoring

## 2. System Architecture

### 2.1 High-Level Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Market Data   │    │   Account State  │    │   Active Trades │
│   (TA-Lib)      │───▶│   (AsterDEX)     │───▶│   (Local State) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Context Builder                              │
│  • Market indicators (5m/4h)                                   │
│  • Account performance & positions                             │
│  • Recent trading history                                      │
│  • Active orders & fills                                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Decision Engine                              │
│  • LLM Analysis (OpenRouter)                                   │
│  • Technical Analysis (TA-Lib indicators)                      │
│  • Structured Output Generation                                │
│  • Sanitization & Validation                                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Execution Layer                              │
│  • Order Placement (Market/Limit)                              │
│  • Take-Profit & Stop-Loss                                     │
│  • Position Management                                         │
│  • Trade Logging & Diary                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Components

#### 2.2.1 Main Application Loop
- **Purpose**: Orchestrates the entire trading workflow
- **Responsibilities**:
  - Continuous loop execution at configurable intervals
  - Multi-asset processing coordination
  - State management and reconciliation
  - HTTP API server for monitoring

#### 2.2.2 Decision Engine
- **Purpose**: LLM-powered trading decision making
- **Responsibilities**:
  - Integration with OpenRouter API for multiple LLM models
  - Structured output generation with JSON schema validation
  - Dynamic technical analysis indicator calculation via TA-Lib
  - Output sanitization and fallback mechanisms

#### 2.2.3 Market Data Provider
- **Purpose**: Technical analysis data acquisition
- **Responsibilities**:
  - Integration with TA-Lib for technical analysis indicators
  - Multi-timeframe data (5m intraday, 4h long-term)
  - Retry logic with exponential backoff
  - Historical series data for trend analysis

#### 2.2.4 Trading Execution
- **Purpose**: Order execution and position management
- **Responsibilities**:
  - Direct integration with AsterDEX via Aster Connector Python Library
  - Market order, take-profit, and stop-loss execution
  - Real-time portfolio and PnL monitoring
  - Connection resilience and retry mechanisms

#### 2.2.5 Configuration Management
- **Purpose**: Centralized configuration and environment management
- **Responsibilities**:
  - Environment variable management
  - API key security
  - Runtime settings configuration

## 3. Functional Requirements

### 3.1 Trading Operations

#### 3.1.1 Asset Monitoring
- **FR-001**: The system SHALL monitor multiple cryptocurrency assets simultaneously
- **FR-002**: The system SHALL support configurable monitoring intervals (5m, 1h, 4h, 1d)
- **FR-003**: The system SHALL fetch real-time market data for each monitored asset
- **FR-004**: The system SHALL maintain price history for trend analysis

#### 3.1.2 Decision Making
- **FR-005**: The system SHALL use LLM models to analyze market conditions and make trading decisions
- **FR-006**: The system SHALL support multiple LLM models (GPT-5, Grok-4, DeepSeek R1)
- **FR-007**: The system SHALL generate structured trading decisions with the following fields:
  - Asset symbol
  - Action (buy/sell/hold)
  - Allocation amount in USD
  - Take-profit price (optional)
  - Stop-loss price (optional)
  - Exit plan description
  - Decision rationale
- **FR-008**: The system SHALL validate all trading decisions against JSON schema
- **FR-009**: The system SHALL implement fallback mechanisms for malformed LLM outputs

#### 3.1.3 Order Execution
- **FR-010**: The system SHALL execute market orders for buy/sell actions
- **FR-011**: The system SHALL automatically place take-profit orders when specified
- **FR-012**: The system SHALL automatically place stop-loss orders when specified
- **FR-013**: The system SHALL support leverage trading (2x-5x recommended)
- **FR-014**: The system SHALL handle order failures gracefully with retry logic

#### 3.1.4 Risk Management
- **FR-015**: The system SHALL implement position-aware logic respecting existing exit plans
- **FR-016**: The system SHALL enforce cooldown periods between trading decisions
- **FR-017**: The system SHALL monitor funding rates and consider them in decisions
- **FR-018**: The system SHALL implement hysteresis requiring stronger evidence for direction changes
- **FR-019**: The system SHALL validate allocation amounts against available capital

### 3.2 Data Management

#### 3.2.1 Market Data
- **FR-020**: The system SHALL calculate technical indicators using TA-Lib including:
  - EMA (Exponential Moving Average)
  - MACD (Moving Average Convergence Divergence)
  - RSI (Relative Strength Index)
  - ATR (Average True Range)
  - Bollinger Bands
  - And other standard technical analysis indicators
- **FR-021**: The system SHALL support both 5-minute and 4-hour timeframes
- **FR-022**: The system SHALL maintain historical indicator series for trend analysis
- **FR-023**: The system SHALL implement retry logic for API failures

#### 3.2.2 Account State
- **FR-024**: The system SHALL fetch real-time account balance from AsterDEX
- **FR-025**: The system SHALL track all open positions with PnL calculations
- **FR-026**: The system SHALL monitor open orders and their status
- **FR-027**: The system SHALL track recent fills and trade executions
- **FR-028**: The system SHALL calculate performance metrics (total return, Sharpe ratio)

#### 3.2.3 State Reconciliation
- **FR-029**: The system SHALL reconcile local state with exchange state continuously
- **FR-030**: The system SHALL remove stale active trades when no position or orders exist
- **FR-031**: The system SHALL log all reconciliation events
- **FR-032**: The system SHALL treat exchange state as authoritative source of truth

### 3.3 Logging and Monitoring

#### 3.3.1 Trading Diary
- **FR-033**: The system SHALL maintain a comprehensive trading diary in JSONL format
- **FR-034**: The system SHALL log all trading decisions with timestamps
- **FR-035**: The system SHALL log all order executions and their results
- **FR-036**: The system SHALL log reconciliation events and state changes
- **FR-037**: The system SHALL provide API access to diary entries

#### 3.3.2 LLM Interaction Logs
- **FR-038**: The system SHALL log all LLM requests and responses
- **FR-039**: The system SHALL log prompt context and market data sent to LLM
- **FR-040**: The system SHALL log any errors or failures in LLM communication
- **FR-041**: The system SHALL provide API access to log files

#### 3.3.3 Performance Monitoring
- **FR-042**: The system SHALL calculate and track total return percentage
- **FR-043**: The system SHALL calculate and track Sharpe ratio
- **FR-044**: The system SHALL calculate and track Sortino ratio (downside deviation-based risk metric)
- **FR-045**: The system SHALL track individual position performance
- **FR-046**: The system SHALL provide real-time performance metrics

### 3.3.4 Multi-Account Operations

The system supports running multiple independent trading accounts concurrently, each with isolated configuration and state management.

#### 3.3.4.1 Account Management
- **FR-047**: The system SHALL support running multiple trading accounts simultaneously
- **FR-048**: The system SHALL assign a unique account_id to each trading account
- **FR-049**: The system SHALL maintain isolated state for each account (positions, orders, performance metrics)
- **FR-050**: The system SHALL prevent cross-account interference or data leakage
- **FR-051**: The system SHALL support adding new accounts without restarting the entire system
- **FR-052**: The system SHALL support removing accounts without affecting other accounts
- **FR-053**: The system SHALL track account status (active, paused, stopped)

#### 3.3.4.2 Account Configuration
- **FR-054**: Each account SHALL have its own AsterDEX API key and credentials
- **FR-055**: Each account SHALL have its own OpenRouter API key
- **FR-056**: Each account SHALL support independent LLM model selection (e.g., Grok-4, DeepSeek, Claude, GPT-4)
- **FR-057**: Each account SHALL support independent asset monitoring configuration
- **FR-058**: Each account SHALL support independent trading interval configuration
- **FR-059**: Each account SHALL support independent risk management parameters (leverage, position size limits)

#### 3.3.4.3 Account Isolation
- **FR-060**: The system SHALL execute trading decisions independently for each account
- **FR-061**: The system SHALL maintain separate order books and position tracking per account
- **FR-062**: The system SHALL calculate performance metrics independently per account
- **FR-063**: The system SHALL prevent one account's API failures from affecting other accounts
- **FR-064**: The system SHALL implement per-account rate limiting and retry logic

### 3.4 API Interface

#### 3.4.1 HTTP Endpoints (FastAPI)
The system uses FastAPI as the web framework for all HTTP endpoints, providing automatic OpenAPI documentation and type validation.

- **FR-065**: The system SHALL provide `GET /diary` endpoint returning recent trading diary entries
- **FR-066**: The system SHALL provide `GET /logs` endpoint returning log file contents
- **FR-067**: The system SHALL support query parameters for limiting results
- **FR-068**: The system SHALL support file download functionality
- **FR-069**: The system SHALL return JSON responses for structured data
- **FR-070**: The system SHALL provide `GET /health` endpoint for health checks
- **FR-071**: The system SHALL provide `GET /status` endpoint returning current system status and metrics
- **FR-072**: The system SHALL provide `GET /positions` endpoint returning current open positions
- **FR-073**: The system SHALL provide `GET /performance` endpoint returning performance metrics including Sharpe ratio and Sortino ratio
- **FR-074**: The system SHALL provide `GET /accounts` endpoint returning list of all configured accounts
- **FR-075**: The system SHALL provide `GET /accounts/{account_id}` endpoint returning account details and status
- **FR-076**: The system SHALL provide `GET /accounts/{account_id}/status` endpoint returning account-specific status and metrics
- **FR-077**: The system SHALL support account_id query parameter for filtering endpoints (e.g., `GET /performance?account_id=1`)
- **FR-078**: The system SHALL support account_id query parameter for filtering positions and orders

#### 3.4.2 WebSocket Endpoints (Real-time Updates)
The system provides WebSocket endpoints for real-time data streaming to frontend clients, enabling live monitoring and updates.

- **FR-079**: The system SHALL provide `WS /ws/trading-events` endpoint for real-time trading decision and execution updates
- **FR-080**: The system SHALL provide `WS /ws/market-data` endpoint for real-time market data streams
- **FR-081**: The system SHALL provide `WS /ws/positions` endpoint for real-time position and order updates
- **FR-082**: The system SHALL broadcast trading decision events including asset, action, allocation, and rationale
- **FR-083**: The system SHALL broadcast order execution events including order ID, status, fill price, and timestamp
- **FR-084**: The system SHALL broadcast position update events including current PnL, entry price, and exit plan
- **FR-085**: The system SHALL broadcast market data events including price, indicators, and funding rate
- **FR-086**: The system SHALL support multiple concurrent WebSocket connections
- **FR-087**: The system SHALL implement automatic reconnection handling on the client side
- **FR-088**: The system SHALL send heartbeat/ping frames every 30 seconds to maintain connection health
- **FR-089**: The system SHALL support account_id filtering in WebSocket subscriptions
- **FR-090**: The system SHALL broadcast account-specific events to subscribed clients

#### 3.4.3 API Configuration
- **FR-091**: The system SHALL support configurable API host and port
- **FR-092**: The system SHALL bind to 0.0.0.0 by default for external access
- **FR-093**: The system SHALL use port 3000 by default
- **FR-094**: The system SHALL support CORS configuration for frontend integration
- **FR-095**: The system SHALL serve static frontend files from the `/static` directory
- **FR-096**: The system SHALL provide OpenAPI/Swagger documentation at `/docs` endpoint

## 4. Non-Functional Requirements

### 4.1 Performance
- **NFR-001**: The system SHALL make trading decisions within 30 seconds of market data availability
- **NFR-002**: The system SHALL handle up to 10 concurrent assets without performance degradation
- **NFR-003**: The system SHALL maintain 99%+ uptime with automatic reconnection
- **NFR-004**: The system SHALL process API responses within 5 seconds

### 4.2 Reliability
- **NFR-005**: The system SHALL implement exponential backoff retry logic for all external API calls
- **NFR-006**: The system SHALL gracefully handle network failures and API outages
- **NFR-007**: The system SHALL automatically reconnect to external services after failures
- **NFR-008**: The system SHALL maintain data consistency through state reconciliation

### 4.3 Security
- **NFR-009**: The system SHALL store private keys securely in environment variables
- **NFR-010**: The system SHALL support both private key and mnemonic phrase authentication
- **NFR-011**: The system SHALL never log sensitive information (private keys, API keys)
- **NFR-012**: The system SHALL validate all external inputs before processing

### 4.4 Scalability
- **NFR-013**: The system SHALL support configurable asset lists without code changes
- **NFR-014**: The system SHALL support configurable trading intervals
- **NFR-015**: The system SHALL handle increasing log file sizes efficiently
- **NFR-016**: The system SHALL support multiple LLM model configurations

### 4.5 Maintainability
- **NFR-017**: The system SHALL provide comprehensive logging for debugging
- **NFR-018**: The system SHALL use structured logging with timestamps
- **NFR-019**: The system SHALL provide clear error messages and stack traces
- **NFR-020**: The system SHALL support configuration through environment variables

### 4.6 Performance Metrics and Risk Management

#### 4.6.1 Sharpe Ratio Calculation
- **NFR-021**: The system SHALL calculate Sharpe ratio using daily returns
- **NFR-022**: The system SHALL use risk-free rate of 0% (or configurable value) for Sharpe ratio calculation
- **NFR-023**: The system SHALL calculate Sharpe ratio with annualization factor of 252 trading days

#### 4.6.2 Sortino Ratio Calculation
- **NFR-024**: The system SHALL calculate Sortino ratio as a downside risk-adjusted return metric
- **NFR-025**: The system SHALL use target return threshold of 0% (or configurable value) for Sortino ratio
- **NFR-026**: The system SHALL calculate downside deviation using only negative returns below target
- **NFR-027**: The system SHALL calculate Sortino ratio with annualization factor of 252 trading days
- **NFR-028**: The system SHALL implement Sortino ratio as custom calculation (TA-Lib does not provide this metric)
- **NFR-029**: The system SHALL provide both Sharpe and Sortino ratios for comprehensive risk assessment

#### 4.6.3 Additional Performance Metrics
- **NFR-030**: The system SHALL calculate and track win rate (percentage of profitable trades)
- **NFR-031**: The system SHALL calculate and track maximum drawdown (peak-to-trough decline)
- **NFR-032**: The system SHALL calculate and track total return percentage
- **NFR-033**: The system SHALL calculate and track daily/weekly/monthly returns

## 5. Data Formats and Schemas

### 5.1 Trading Decision Schema
```json
{
  "type": "object",
  "properties": {
    "trade_decisions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "asset": {"type": "string", "enum": ["BTC", "ETH", "SOL", ...]},
          "action": {"type": "string", "enum": ["buy", "sell", "hold"]},
          "allocation_usd": {"type": "number", "minimum": 0},
          "tp_price": {"type": ["number", "null"]},
          "sl_price": {"type": ["number", "null"]},
          "exit_plan": {"type": "string"},
          "rationale": {"type": "string"}
        },
        "required": ["asset", "action", "allocation_usd", "tp_price", "sl_price", "exit_plan", "rationale"],
        "additionalProperties": false
      },
      "minItems": 1
    }
  },
  "required": ["trade_decisions"],
  "additionalProperties": false
}
```

### 5.2 Trading Diary Entry Schema
```json
{
  "timestamp": "2025-01-19T10:30:00Z",
  "asset": "BTC",
  "action": "buy",
  "allocation_usd": 1000.0,
  "amount": 0.022,
  "entry_price": 45000.0,
  "tp_price": 46000.0,
  "tp_oid": "12345",
  "sl_price": 44000.0,
  "sl_oid": "12346",
  "exit_plan": "close if 4h close above EMA50",
  "rationale": "Bullish momentum with RSI oversold",
  "order_result": "success",
  "opened_at": "2025-01-19T10:30:00Z",
  "filled": true
}
```

### 5.3 Market Data Format

```json
{
  "asset": "BTC",
  "timestamp": "2025-01-19T10:30:00Z",
  "open_interest": {
    "latest": 25373.64,
    "average": 25393.68
  },
  "funding_rate": 1.25e-05,
  "intraday_series": {
    "mid_prices": [106545.0, 106519.5, 106577.5, 106612.5, 106634.5, 106660.5, 106648.0, 106618.0, 106580.5, 106587.5],
    "ema20": [106804.041, 106776.895, 106759.952, 106745.385, 106736.111, 106728.862, 106719.256, 106708.66, 106695.55, 106685.307],
    "macd": [-102.65, -112.265, -112.137, -110.12, -104.015, -97.089, -93.109, -90.525, -90.42, -87.952],
    "rsi7": [21.196, 22.349, 36.751, 38.091, 45.05, 47.081, 42.225, 39.272, 34.121, 38.448],
    "rsi14": [25.066, 25.73, 34.12, 34.912, 38.962, 40.135, 38.035, 36.74, 34.408, 36.406]
  },
  "long_term_context": {
    "ema20_4h": 108288.597,
    "ema50_4h": 111325.427,
    "atr3_4h": 579.866,
    "atr14_4h": 1492.654,
    "volume_current": 125.281,
    "volume_average": 5111.050,
    "macd_4h": [-1773.039, -1943.803, -1963.704, -1988.826, -1913.41, -1906.547, -1845.78, -1793.648, -1694.631, -1606.597],
    "rsi14_4h": [29.008, 29.431, 35.251, 34.194, 38.686, 35.983, 38.101, 37.446, 39.983, 39.578]
  }
}
```

## 6. External Dependencies

### 6.1 Required Services

#### 6.1.1 AsterDEX Exchange
- **Purpose**: Decentralized perpetual futures trading
- **Integration**: Aster Connector Python Library (see API-DOCS.md for detailed API specifications)
- **Required Operations**:
  - User state retrieval (account info, balances, positions)
  - Market and limit order placement
  - Take-profit/stop-loss order placement
  - Order cancellation and management
  - Position and order monitoring
  - Price data and market data retrieval
  - Kline/candlestick data for technical analysis

#### 6.1.2 TA-Lib
- **Purpose**: Technical analysis indicators calculation
- **Integration**: Python library for local indicator computation
- **Required Operations**:
  - EMA (Exponential Moving Average) calculation
  - MACD (Moving Average Convergence Divergence) calculation
  - RSI (Relative Strength Index) calculation
  - ATR (Average True Range) calculation
  - Bollinger Bands calculation
  - Other standard technical analysis indicators

#### 6.1.3 OpenRouter
- **Purpose**: LLM model access
- **Integration**: REST API
- **Required Operations**:
  - Chat completions
  - Structured output generation
  - Tool calling support
  - Multiple model support (GPT-5, Grok-4, DeepSeek R1)

### 6.2 Python Dependencies

The project uses `uv` for dependency management. Core dependencies include:

```
aster-connector-python>=1.0.0  # AsterDEX API integration
TA-Lib>=0.4.28                 # Technical analysis indicators
typer>=0.12.0                  # CLI framework
fastapi>=0.115.0               # Web framework for API and frontend
uvicorn>=0.32.0                # ASGI server for FastAPI
websockets>=13.0               # WebSocket support for real-time updates
python-dotenv>=1.1.1           # Environment variable management
web3>=7.14.0                   # Web3 utilities
aiohttp>=3.13.1                # Async HTTP client
openai>=2.5.0                  # OpenRouter API client
requests>=2.32.5               # HTTP client
rich>=14.2.0                   # Terminal formatting
```

### 6.3 System Requirements
- **Python**: 3.12 or higher
- **Operating System**: Linux, macOS, Windows
- **Memory**: Minimum 512MB RAM
- **Storage**: Minimum 1GB for logs and data
- **Network**: Stable internet connection for API access

## 7. Configuration Requirements

### 7.1 Environment Variables

#### 7.1.1 Required Configuration

```bash
# AsterDEX API Keys (Required)
ASTERDEX_API_KEY=your_asterdex_api_key
ASTERDEX_API_SECRET=your_asterdex_api_secret

# OpenRouter Configuration (Required)
OPENROUTER_API_KEY=your_openrouter_api_key

# Trading Configuration
LLM_MODEL=x-ai/grok-4  # or other supported model
ASSETS=BTC ETH SOL     # space or comma separated
INTERVAL=1h            # 5m, 1h, 4h, 1d
```

#### 7.1.2 Optional Configuration

```bash
# OpenRouter Configuration
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_REFERER=your_referer
OPENROUTER_APP_TITLE=trading-agent

# AsterDEX Configuration
ASTERDEX_BASE_URL=https://fapi.asterdex.com
ASTERDEX_NETWORK=mainnet  # or testnet

# API Server Configuration
API_HOST=0.0.0.0
API_PORT=3000  # or APP_PORT
```

### 7.2 Multi-Account Configuration

The system supports running multiple trading accounts simultaneously, each with independent configuration:

#### 7.2.1 Environment Variable Format

```bash
# Single Account (Default)
ASTERDEX_API_KEY=key1
ASTERDEX_API_SECRET=secret1
OPENROUTER_API_KEY=router_key1
LLM_MODEL=x-ai/grok-4

# Multi-Account Mode (Comma-separated or JSON)
MULTI_ACCOUNT_MODE=true

# Option 1: Comma-separated format
ACCOUNT_IDS=account1,account2,account3
ASTERDEX_API_KEY_account1=key1
ASTERDEX_API_SECRET_account1=secret1
OPENROUTER_API_KEY_account1=router_key1
LLM_MODEL_account1=x-ai/grok-4

ASTERDEX_API_KEY_account2=key2
ASTERDEX_API_SECRET_account2=secret2
OPENROUTER_API_KEY_account2=router_key2
LLM_MODEL_account2=deepseek/deepseek-chat

ASTERDEX_API_KEY_account3=key3
ASTERDEX_API_SECRET_account3=secret3
OPENROUTER_API_KEY_account3=router_key3
LLM_MODEL_account3=anthropic/claude-3-sonnet
```

#### 7.2.2 Configuration File Format (YAML/JSON)

```yaml
# accounts.yaml
accounts:
  - id: account1
    asterdex:
      api_key: ${ASTERDEX_KEY_1}
      api_secret: ${ASTERDEX_SECRET_1}
    openrouter:
      api_key: ${OPENROUTER_KEY_1}
    llm_model: x-ai/grok-4
    assets: [BTC, ETH]
    interval: 1h

  - id: account2
    asterdex:
      api_key: ${ASTERDEX_KEY_2}
      api_secret: ${ASTERDEX_SECRET_2}
    openrouter:
      api_key: ${OPENROUTER_KEY_2}
    llm_model: deepseek/deepseek-chat
    assets: [SOL, AVAX]
    interval: 4h

  - id: account3
    asterdex:
      api_key: ${ASTERDEX_KEY_3}
      api_secret: ${ASTERDEX_SECRET_3}
    openrouter:
      api_key: ${OPENROUTER_KEY_3}
    llm_model: anthropic/claude-3-sonnet
    assets: [BTC, ETH, SOL]
    interval: 5m
```

### 7.3 Command Line Interface
```bash
# Basic usage (single account)
python src/main.py --assets BTC ETH --interval 1h

# Multi-account mode
python src/main.py --multi-account --config accounts.yaml

# With environment variables
python src/main.py  # Uses ASSETS and INTERVAL from .env
```

## 8. Deployment Requirements

### 8.1 Local Development

- **uv**: For dependency management
- **Python 3.12+**: Runtime environment
- **Environment file**: `.env` with required configuration

### 8.2 Docker Deployment

- **Dockerfile**: Multi-stage build with Python 3.12-slim
- **ASGI Server**: FastAPI application served via uvicorn
- **Platform**: Linux/AMD64 support
- **Port**: 3000 exposed by default
- **Volume**: Persistent storage for logs and diary
- **Startup Command**: `uvicorn src.main:app --host 0.0.0.0 --port 3000`

### 8.3 Cloud Deployment

The FastAPI application can be deployed on standard cloud platforms using containerized Docker deployment:

- **Supported Platforms**: AWS (EC2, ECS, EKS), Google Cloud (Compute Engine, Cloud Run), Azure (Container Instances, AKS), DigitalOcean (App Platform, Kubernetes), Heroku, or similar cloud providers
- **Container Registry**: Docker images pushed to Docker Hub, AWS ECR, Google Container Registry, or Azure Container Registry
- **Deployment Method**: Docker containers running uvicorn ASGI server
- **Scaling**: Horizontal scaling via container orchestration (Kubernetes, Docker Swarm, or cloud-native services)
- **Environment Configuration**: Cloud-native environment variable management (AWS Secrets Manager, Google Secret Manager, Azure Key Vault)
- **Monitoring**: Cloud provider monitoring and logging services (CloudWatch, Stackdriver, Azure Monitor)
- **Networking**: Cloud load balancers for traffic distribution and SSL/TLS termination
- **Storage**: Cloud object storage for logs and persistent data (S3, Google Cloud Storage, Azure Blob Storage)

### 8.4 Multi-Account Deployment

#### 8.4.1 Single Container with Multiple Accounts

**Recommended for most deployments**:
- Single Docker container runs all trading accounts concurrently
- Each account operates in independent threads/async tasks
- Shared FastAPI server handles all accounts
- Reduced resource overhead compared to per-account containers
- Simpler management and monitoring

**Resource Requirements**:
- **CPU**: 1-2 cores per 5-10 accounts (depending on trading frequency)
- **Memory**: 512MB base + 100-200MB per account
- **Storage**: Shared database for all accounts

**Configuration**:
- Set `MULTI_ACCOUNT_MODE=true` in environment
- Provide account configuration via environment variables or config file
- All accounts share the same FastAPI server instance

#### 8.4.2 Separate Containers per Account

**Alternative for high-isolation requirements**:
- Each account runs in its own Docker container
- Independent resource allocation per account
- Easier to scale individual accounts
- Higher resource overhead

**Deployment Strategy**:
- Use container orchestration (Kubernetes, Docker Swarm)
- Each container has unique account_id
- Shared database for cross-account queries
- Load balancer routes requests to appropriate container

**Resource Requirements**:
- **CPU**: 0.5-1 core per account
- **Memory**: 512MB per account
- **Storage**: Shared database

#### 8.4.3 Hybrid Approach

**Balanced deployment**:
- Group related accounts in containers (e.g., 2-3 accounts per container)
- Balance between resource efficiency and isolation
- Flexible scaling based on account activity

## 9. Data Persistence and Storage

### 9.1 Data Persistence Requirements

The system must persist multiple types of data for audit trails, analysis, and recovery purposes:

#### 9.1.1 Market Data Storage
- **FR-097**: The system SHALL persist market data including prices, indicators, open interest, and funding rates
- **FR-098**: The system SHALL store intraday series data (mid prices, EMA, MACD, RSI) at 5-minute intervals
- **FR-099**: The system SHALL store long-term context data (4-hour timeframe indicators) for trend analysis
- **FR-100**: The system SHALL maintain historical market data for backtesting and analysis
- **FR-101**: The system SHALL support efficient time-series queries for market data retrieval
- **FR-102**: The system SHALL implement data retention policies (e.g., 1 year of market data)

#### 9.1.2 LLM Interaction Logging
- **FR-103**: The system SHALL persist all LLM prompts sent to OpenRouter API
- **FR-104**: The system SHALL persist all LLM responses and trading decisions received
- **FR-105**: The system SHALL store prompt context including market data, account state, and trading history
- **FR-106**: The system SHALL maintain complete audit trail of LLM interactions for analysis and debugging
- **FR-107**: The system SHALL support querying LLM interactions by timestamp, asset, or decision type
- **FR-108**: The system SHALL implement data retention policies for LLM logs (e.g., 2 years)

#### 9.1.3 Order and Trade History
- **FR-109**: The system SHALL persist all order submissions with timestamps and parameters
- **FR-110**: The system SHALL track order modifications and cancellations
- **FR-111**: The system SHALL store executed trades with fill prices, quantities, and timestamps
- **FR-112**: The system SHALL maintain complete order lifecycle from submission to execution or cancellation
- **FR-113**: The system SHALL support querying orders and trades by asset, date range, or status
- **FR-114**: The system SHALL implement data retention policies for order/trade history (e.g., 5 years for compliance)

#### 9.1.4 Performance Metrics and Analytics
- **FR-115**: The system SHALL persist calculated performance metrics (total return, Sharpe ratio, Sortino ratio, win rate, max drawdown)
- **FR-116**: The system SHALL store daily/weekly/monthly performance snapshots
- **FR-117**: The system SHALL maintain position-level performance tracking
- **FR-118**: The system SHALL support historical performance queries and trend analysis

#### 9.1.5 Multi-Account Data Persistence
- **FR-119**: All persisted data SHALL be tagged with account_id for isolation
- **FR-120**: The system SHALL support querying data by account_id
- **FR-121**: The system SHALL maintain separate performance metrics per account
- **FR-122**: The system SHALL support account-specific data retention policies
- **FR-123**: The system SHALL prevent cross-account data access or leakage

### 9.2 Recommended Data Store Technology

**Primary Recommendation: PostgreSQL with TimescaleDB Extension**

- **Rationale**: Combines relational database capabilities with time-series optimization
- **Market Data**: TimescaleDB hypertables for efficient time-series storage and querying
- **LLM Logs**: JSONB columns for flexible schema storage of prompts and responses
- **Orders/Trades**: Standard relational tables with indexes for fast queries
- **Performance Metrics**: Aggregated tables with materialized views for analytics
- **Advantages**:
  - Single database for all data types
  - Excellent time-series query performance
  - ACID compliance for data integrity
  - Full-text search capabilities for logs
  - Built-in backup and replication
  - Cost-effective open-source solution

**Alternative Options**:
- **InfluxDB**: Specialized time-series database (excellent for market data, but requires separate storage for other data types)
- **MongoDB**: Document database (flexible schema for LLM logs, but less optimal for time-series data)
- **Elasticsearch**: Log aggregation and search (excellent for LLM logs and audit trails)

### 9.3 Data Store Integration

- **FR-124**: The system SHALL support configurable database connection strings via environment variables
- **FR-125**: The system SHALL implement connection pooling for efficient database access
- **FR-126**: The system SHALL support database migrations for schema updates
- **FR-127**: The system SHALL implement transaction support for data consistency
- **FR-128**: The system SHALL support backup and recovery procedures
- **FR-129**: The system SHALL implement data archival for old records

## 10. Error Handling and Recovery

### 10.1 API Failure Handling
- **Retry Logic**: Exponential backoff with maximum retry limits
- **Circuit Breaker**: Temporary service disabling after repeated failures
- **Graceful Degradation**: Continue operation with reduced functionality
- **Error Logging**: Comprehensive error tracking and reporting

### 10.2 State Recovery
- **Exchange Reconciliation**: Regular sync with authoritative exchange state
- **Stale Data Cleanup**: Automatic removal of outdated local state
- **Restart Recovery**: Fresh state initialization on application restart
- **Data Validation**: Input validation and sanitization

### 10.3 Trading Safety
- **Position Limits**: Maximum position size validation
- **Leverage Controls**: Configurable leverage limits
- **Order Validation**: Pre-execution order validation
- **Emergency Stops**: Manual intervention capabilities

## 10. Monitoring and Observability

### 10.1 Logging Requirements
- **Structured Logging**: JSON format with timestamps
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Log Rotation**: Automatic log file rotation and cleanup
- **Log Aggregation**: Support for external log collection systems

### 10.2 Metrics and Alerts
- **Performance Metrics**: Response times, success rates, error rates
- **Trading Metrics**: PnL, Sharpe ratio, win/loss ratios
- **System Metrics**: CPU, memory, disk usage
- **Alert Thresholds**: Configurable alerting for critical conditions

### 10.3 Health Checks
- **API Endpoints**: Health check endpoints for external monitoring
- **Service Dependencies**: Monitoring of external service availability
- **Data Freshness**: Validation of data recency and accuracy
- **System Resources**: Monitoring of system resource utilization

## 11. Security Considerations

### 11.1 Key Management
- **Environment Variables**: Secure storage of sensitive configuration
- **Key Rotation**: Support for periodic key updates
- **Access Control**: Restricted access to sensitive operations
- **Audit Trails**: Comprehensive logging of all operations

### 11.2 Network Security
- **TLS/SSL**: Encrypted communication with external services
- **API Authentication**: Secure API key management
- **Rate Limiting**: Protection against API abuse
- **Input Validation**: Sanitization of all external inputs

### 11.3 Operational Security
- **Least Privilege**: Minimal required permissions
- **Secure Defaults**: Safe default configurations
- **Regular Updates**: Dependency and security patch management
- **Incident Response**: Procedures for security incident handling

## 12. Testing Requirements

### 12.1 Unit Testing
- **Component Testing**: Individual component functionality
- **Mock Services**: Simulated external service responses
- **Edge Cases**: Boundary condition testing
- **Error Scenarios**: Failure mode testing

### 12.2 Integration Testing
- **API Integration**: External service integration testing
- **End-to-End**: Complete workflow testing
- **Performance Testing**: Load and stress testing
- **Compatibility Testing**: Multi-platform compatibility

### 12.3 Trading Testing
- **Paper Trading**: Risk-free trading simulation
- **Backtesting**: Historical data validation
- **Stress Testing**: Extreme market condition testing
- **Recovery Testing**: Failure recovery validation

## 13. Documentation Requirements

### 13.1 User Documentation
- **Installation Guide**: Step-by-step setup instructions
- **Configuration Guide**: Detailed configuration options
- **API Documentation**: Endpoint specifications and examples
- **Troubleshooting Guide**: Common issues and solutions

### 13.2 Developer Documentation
- **Architecture Overview**: System design and components
- **Code Documentation**: Inline code comments and docstrings
- **API Specifications**: Detailed interface documentation
- **Deployment Guide**: Production deployment procedures

### 13.3 Operational Documentation
- **Monitoring Guide**: System monitoring and alerting
- **Maintenance Procedures**: Regular maintenance tasks
- **Backup and Recovery**: Data protection procedures
- **Security Procedures**: Security best practices

## 14. Future Requirements

### 14.1 Future Exchange Support

The following exchanges are planned for future integration to support multi-exchange trading:

#### 14.1.1 Hyperliquid Exchange
- **Status**: Planned for future implementation
- **Purpose**: Decentralized perpetual futures trading
- **Integration**: Hyperliquid Python SDK
- **Required Operations**:
  - User state retrieval
  - Market order placement
  - Take-profit/stop-loss order placement
  - Order cancellation
  - Position and order monitoring
  - Price data retrieval

#### 14.1.2 TAAPI.io Integration
- **Status**: Planned for future implementation as alternative data source
- **Purpose**: Extended technical analysis indicators (200+ indicators)
- **Integration**: REST API
- **Required Operations**:
  - Indicator value retrieval (EMA, MACD, RSI, ATR, etc.)
  - Historical series data
  - Multi-timeframe support (5m, 4h)
  - Advanced indicator combinations

### 14.2 Multi-Exchange Architecture
- **Exchange Abstraction Layer**: Unified interface for multiple exchanges
- **Exchange Router**: Intelligent routing of orders to optimal venues
- **Cross-Exchange Arbitrage**: Opportunities across multiple platforms
- **Liquidity Aggregation**: Combined order book analysis

### 14.3 Trusted Execution Environment (TEE) Deployment

The following TEE-based deployment option is planned for future implementation to provide enhanced security and privacy:

#### 14.3.1 EigenCloud Deployment
- **Status**: Planned for future implementation
- **Purpose**: Secure execution in Trusted Execution Environment (TEE)
- **Platform**: EigenCloud infrastructure with TEE support
- **Integration**: EigenX CLI for deployment and management
- **Requirements**:
  - Docker container deployment to EigenCloud
  - Sepolia ETH for testnet deployments
  - Docker Registry for container distribution
  - TEE-specific security configurations
- **Benefits**:
  - Enhanced privacy for trading strategies
  - Secure key management in isolated environment
  - Compliance with regulatory requirements
  - Protection against unauthorized access to trading logic

## 15. Future Enhancements

### 15.1 Frontend Service Architecture

The FastAPI backend provides comprehensive support for frontend service integration through both HTTP and WebSocket protocols:

#### 15.1.1 Backend-Frontend Communication

**HTTP REST API**:
- The FastAPI application serves as the primary REST API for frontend clients
- All endpoints are automatically documented via OpenAPI/Swagger at `/docs`
- Static frontend files are served from the `/static` directory
- CORS (Cross-Origin Resource Sharing) is configured to allow frontend requests from specified origins

**WebSocket Real-time Streaming**:
- Three dedicated WebSocket endpoints provide real-time data streams:
  - `/ws/trading-events`: Trading decisions and order executions
  - `/ws/market-data`: Live market prices and technical indicators
  - `/ws/positions`: Position updates and PnL changes
- WebSocket connections maintain persistent communication with automatic heartbeat/ping frames every 30 seconds
- Clients implement automatic reconnection logic to handle network interruptions

#### 15.1.2 Real-time Data Pushed via WebSockets

**Trading Events Stream** (`/ws/trading-events`):
- Trading decision events with asset, action, allocation, and rationale
- Order execution events with order ID, status, fill price, and timestamp
- Position update events with current PnL, entry price, and exit plan

**Market Data Stream** (`/ws/market-data`):
- Current price and technical indicators (EMA, MACD, RSI)
- Funding rate and open interest data
- Multi-timeframe context (5-minute and 4-hour data)

**Position Stream** (`/ws/positions`):
- Real-time position updates with PnL calculations
- Order status changes and fills
- Account balance and margin information

#### 15.1.3 CORS Configuration

- CORS is configured to allow requests from frontend origins
- Credentials (cookies, authorization headers) are supported for authenticated requests
- Allowed methods include GET, POST, PUT, DELETE, OPTIONS
- Allowed headers include Content-Type, Authorization, and custom headers
- Configuration is environment-based for flexibility across development, staging, and production

#### 15.1.4 Frontend Integration Points

- Frontend clients connect to the FastAPI backend at the configured API_HOST and API_PORT
- HTTP endpoints provide initial data loading and state queries
- WebSocket connections provide real-time updates for live monitoring
- Frontend can subscribe to specific data streams based on user preferences
- Error handling includes automatic reconnection and fallback to HTTP polling if WebSocket fails

### 15.2 Potential Improvements

- **Web Dashboard**: User interface for monitoring and control
- **Advanced Analytics**: Enhanced performance analysis and reporting
- **Machine Learning**: Enhanced decision-making algorithms
- **Mobile App**: Mobile monitoring and control interface

### 15.3 Scalability Enhancements

- **Microservices Architecture**: Component separation and scaling
- **Database Integration**: Persistent state management
- **Message Queues**: Asynchronous processing
- **Load Balancing**: High availability and performance

### 15.4 Feature Extensions

- **Portfolio Management**: Multi-strategy portfolio support
- **Risk Analytics**: Advanced risk assessment tools
- **Social Trading**: Community features and sharing
- **Custom Indicators**: User-defined technical indicators

---

**Document Version**: 2.3
**Last Updated**: October 23, 2025
**Author**: AI Trading Agent Development Team
**Status**: Updated with Multi-Account Trading Support and Enhanced Deployment Architecture

### Key Changes in Version 2.3

- Added comprehensive multi-account trading support (Section 3.3.4)
- Each account supports independent AsterDEX API keys and OpenRouter API keys
- Each account supports independent LLM model selection (Grok-4, DeepSeek, Claude, GPT-4, etc.)
- Implemented account isolation to prevent cross-account interference or data leakage
- Added account management endpoints: `GET /accounts`, `GET /accounts/{account_id}`, `GET /accounts/{account_id}/status`
- Added account_id filtering to existing endpoints (`GET /performance?account_id=1`, etc.)
- Added account_id filtering to WebSocket subscriptions for per-account event streaming
- Updated Configuration section (7.2) with multi-account environment variable and YAML/JSON configuration formats
- Added multi-account deployment strategies (Section 8.4):
  - Single container with multiple accounts (recommended)
  - Separate containers per account (high-isolation)
  - Hybrid approach (balanced)
- Added multi-account data persistence requirements (Section 9.1.5)
- All persisted data tagged with account_id for isolation and querying
- Support for account-specific data retention policies
- Added 18 new functional requirements (FR-047 through FR-064) for multi-account operations
- Added 8 new functional requirements (FR-074 through FR-078) for account-aware API endpoints
- Added 2 new functional requirements (FR-089 through FR-090) for account-aware WebSocket endpoints
- Added 5 new functional requirements (FR-119 through FR-123) for multi-account data persistence
- Total of 33 new functional requirements for multi-account support

### Key Changes in Version 2.2

- Moved EigenCloud/TEE deployment to Section 14 (Future Requirements)
- Replaced Section 8.3 with standard cloud deployment options (AWS, GCP, Azure, DigitalOcean, etc.)
- Added comprehensive Section 9 (Data Persistence and Storage) with requirements for:
  - Market data persistence (prices, indicators, open interest, funding rates)
  - LLM interaction logging (prompts, responses, context)
  - Order and trade history tracking
  - Performance metrics and analytics storage
- Recommended PostgreSQL with TimescaleDB extension as primary data store
- Added Sortino ratio calculation as performance metric (Section 4.6.2)
- Documented Sortino ratio parameters (target return, downside deviation, annualization)
- Updated `/performance` endpoint to include both Sharpe and Sortino ratios
- Added 28 new functional requirements (FR-072 through FR-099) for data persistence
- Added 13 new non-functional requirements (NFR-021 through NFR-033) for performance metrics

### Key Changes in Version 2.1

- Added FastAPI as the web framework for HTTP endpoints
- Added uvicorn as the ASGI server for FastAPI
- Added WebSocket support for real-time frontend data streaming
- Implemented three WebSocket endpoints: `/ws/trading-events`, `/ws/market-data`, `/ws/positions`
- Enhanced Section 3.4 (API Interface) with FastAPI and WebSocket specifications
- Updated Docker deployment to use uvicorn for serving FastAPI
- Added comprehensive frontend service architecture documentation
- Documented CORS configuration requirements for frontend integration
- Added real-time data streaming capabilities for trading events, market data, and positions

### Key Changes in Version 2.0

- Replaced Hyperliquid with AsterDEX as primary exchange
- Replaced TAAPI with TA-Lib for technical analysis indicators
- Replaced Poetry with `uv` for dependency management
- Added Typer library for CLI framework
- Moved Hyperliquid and TAAPI to Future Requirements section
- Updated all API references to use Aster Connector Python Library
- Added reference to API-DOCS.md for AsterDEX API specifications
