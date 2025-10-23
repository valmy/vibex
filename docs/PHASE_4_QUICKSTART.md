# Phase 4: Core Services - QUICKSTART GUIDE

**Estimated Duration**: 3-5 days  
**Complexity**: High  
**Dependencies**: Phase 1, 2, 3 (Complete)  

---

## 🎯 Phase 4 Objectives

### 1. Trading Service (2-3 days)
Implement core trading logic for position and order management.

**Files to Create**:
```
backend/src/app/services/
├── trading_service.py       # Main trading logic
├── position_manager.py      # Position management
├── order_manager.py         # Order execution
├── risk_manager.py          # Risk calculations
└── __init__.py              # Exports
```

**Key Functions**:
- `open_position()` - Open new trading position
- `close_position()` - Close existing position
- `place_order()` - Place new order
- `cancel_order()` - Cancel pending order
- `calculate_position_size()` - Risk-based sizing
- `check_risk_limits()` - Validate risk parameters

### 2. Market Data Service (1-2 days)
Implement real-time market data fetching and storage.

**Files to Create**:
```
backend/src/app/services/
├── market_data_service.py   # Market data fetching
├── data_aggregator.py       # Data aggregation
└── technical_analysis.py    # TA calculations
```

**Key Functions**:
- `fetch_market_data()` - Get OHLCV data
- `store_market_data()` - Save to database
- `calculate_indicators()` - Technical analysis
- `get_latest_price()` - Current price

### 3. LLM Service (1-2 days)
Integrate OpenAI for AI-powered trading decisions.

**Files to Create**:
```
backend/src/app/services/
├── llm_service.py           # OpenAI integration
├── prompt_manager.py        # Prompt templates
└── response_parser.py       # Parse LLM responses
```

**Key Functions**:
- `analyze_market()` - Get market analysis
- `generate_signal()` - Generate trading signal
- `explain_decision()` - Get decision explanation
- `parse_trading_action()` - Parse LLM response

### 4. Notification Service (1 day)
Implement notifications for trading events.

**Files to Create**:
```
backend/src/app/services/
├── notification_service.py  # Notification logic
├── email_notifier.py        # Email notifications
└── webhook_notifier.py      # Webhook support
```

**Key Functions**:
- `send_notification()` - Send notification
- `send_email()` - Email notification
- `send_webhook()` - Webhook notification
- `log_event()` - Event logging

---

## 📋 Implementation Checklist

### Trading Service
- [ ] Create trading_service.py with main logic
- [ ] Implement position_manager.py
- [ ] Implement order_manager.py
- [ ] Implement risk_manager.py
- [ ] Add service endpoints to API
- [ ] Write unit tests
- [ ] Test with mock data

### Market Data Service
- [ ] Create market_data_service.py
- [ ] Implement data_aggregator.py
- [ ] Implement technical_analysis.py
- [ ] Add WebSocket endpoint for real-time data
- [ ] Write unit tests
- [ ] Test with real market data

### LLM Service
- [ ] Create llm_service.py with OpenAI integration
- [ ] Implement prompt_manager.py
- [ ] Implement response_parser.py
- [ ] Add LLM endpoints to API
- [ ] Write unit tests
- [ ] Test with sample prompts

### Notification Service
- [ ] Create notification_service.py
- [ ] Implement email_notifier.py
- [ ] Implement webhook_notifier.py
- [ ] Add notification endpoints to API
- [ ] Write unit tests
- [ ] Test notifications

---

## 🔧 Key Technologies

### Trading Logic
- **Position Sizing**: Kelly Criterion, Fixed Fractional
- **Risk Management**: Stop Loss, Take Profit, Max Drawdown
- **Order Types**: Market, Limit, Stop Loss, Take Profit

### Market Data
- **Data Sources**: Binance API, CoinGecko, AsterDEX
- **Storage**: PostgreSQL TimeSeries
- **Indicators**: SMA, EMA, RSI, MACD, Bollinger Bands

### LLM Integration
- **Model**: GPT-4 or GPT-3.5-turbo
- **Prompts**: Few-shot learning, Chain-of-thought
- **Parsing**: Structured output, JSON parsing

### Notifications
- **Email**: SMTP with templates
- **Webhooks**: HTTP POST with signatures
- **Logging**: Structured JSON logs

---

## 📚 API Endpoints to Add

### Trading Endpoints
```
POST   /api/v1/trading/positions/open
POST   /api/v1/trading/positions/close
POST   /api/v1/trading/orders/place
POST   /api/v1/trading/orders/cancel
GET    /api/v1/trading/positions/active
GET    /api/v1/trading/orders/pending
```

### Market Data Endpoints
```
GET    /api/v1/market/price/{symbol}
GET    /api/v1/market/ohlcv/{symbol}
GET    /api/v1/market/indicators/{symbol}
WS     /ws/market/{symbol}
```

### LLM Endpoints
```
POST   /api/v1/llm/analyze
POST   /api/v1/llm/signal
POST   /api/v1/llm/explain
```

### Notification Endpoints
```
POST   /api/v1/notifications/send
GET    /api/v1/notifications/history
POST   /api/v1/notifications/subscribe
```

---

## 🧪 Testing Strategy

### Unit Tests
- Test each service independently
- Mock external dependencies (OpenAI, Binance)
- Test error handling and edge cases

### Integration Tests
- Test service interactions
- Test database operations
- Test API endpoints

### End-to-End Tests
- Test complete trading workflow
- Test with real market data (paper trading)
- Test notifications

---

## 📊 Database Considerations

### New Tables (Optional)
```sql
-- Market data aggregation
CREATE TABLE market_data_aggregated (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50),
    timeframe VARCHAR(10),
    open DECIMAL,
    high DECIMAL,
    low DECIMAL,
    close DECIMAL,
    volume DECIMAL,
    timestamp TIMESTAMP
);

-- Trading signals
CREATE TABLE trading_signals (
    id SERIAL PRIMARY KEY,
    account_id INTEGER,
    symbol VARCHAR(50),
    signal VARCHAR(20),
    confidence DECIMAL,
    timestamp TIMESTAMP
);

-- Notifications
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    account_id INTEGER,
    type VARCHAR(50),
    message TEXT,
    status VARCHAR(20),
    timestamp TIMESTAMP
);
```

---

## 🚀 Getting Started

### 1. Setup Environment
```bash
# Add new environment variables to .env
OPENAI_API_KEY=sk-...
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
```

### 2. Create Services Directory
```bash
mkdir -p backend/src/app/services
touch backend/src/app/services/__init__.py
```

### 3. Start with Trading Service
```bash
# Create trading_service.py
# Implement basic position opening/closing
# Add API endpoints
# Write tests
```

### 4. Add Market Data Service
```bash
# Create market_data_service.py
# Implement data fetching
# Add WebSocket endpoint
# Write tests
```

### 5. Integrate LLM
```bash
# Create llm_service.py
# Setup OpenAI integration
# Create prompt templates
# Write tests
```

### 6. Add Notifications
```bash
# Create notification_service.py
# Implement email/webhook
# Add notification endpoints
# Write tests
```

---

## 📖 Reference Documentation

- **Trading Logic**: See `docs/TRADING_LOGIC.md` (to be created)
- **Market Data**: See `docs/MARKET_DATA.md` (to be created)
- **LLM Integration**: See `docs/LLM_INTEGRATION.md` (to be created)
- **API Reference**: See `/docs` endpoint (Swagger UI)

---

## ⚠️ Important Considerations

1. **Risk Management**: Always validate risk parameters before executing trades
2. **Error Handling**: Implement comprehensive error handling for all services
3. **Logging**: Log all trading decisions and market data for audit trail
4. **Testing**: Test thoroughly with paper trading before live trading
5. **Rate Limiting**: Implement rate limiting for API calls
6. **Security**: Secure API keys and sensitive data

---

## 🎯 Success Criteria

- ✅ All services implemented and tested
- ✅ All API endpoints working
- ✅ Market data flowing correctly
- ✅ LLM integration working
- ✅ Notifications sending
- ✅ Error handling comprehensive
- ✅ Logging complete
- ✅ Ready for Phase 5 (Testing & Deployment)

---

**Next**: Begin Phase 4 implementation with Trading Service

