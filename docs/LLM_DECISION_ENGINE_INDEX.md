# LLM Decision Engine - Documentation Index

## Overview

The LLM Decision Engine is a comprehensive AI-powered trading system for perpetual futures trading across multiple assets. This index provides quick access to all documentation resources.

## Quick Start

1. **[API Documentation](LLM_DECISION_ENGINE_API.md)** - Start here for API usage and integration
2. **[Deployment Guide](LLM_DECISION_ENGINE_DEPLOYMENT.md)** - Deploy and configure the system
3. **[Design Document](.kiro/specs/llm-decision-engine/design.md)** - Understand the architecture
4. **[Requirements](.kiro/specs/llm-decision-engine/requirements.md)** - Review system requirements

## Documentation Structure

### For Developers

- **[API Documentation](LLM_DECISION_ENGINE_API.md)**
  - Complete API reference with examples
  - Multi-asset decision structure
  - Common usage scenarios
  - Integration guide
  - Best practices

- **[Design Document](../.kiro/specs/llm-decision-engine/design.md)**
  - System architecture
  - Component interfaces
  - Data models and schemas
  - Error handling patterns
  - Testing strategy

### For Operations

- **[Deployment Guide](LLM_DECISION_ENGINE_DEPLOYMENT.md)**
  - Environment configuration
  - Database setup and migration
  - Multi-asset configuration
  - Deployment options
  - Monitoring and observability
  - Performance tuning
  - Troubleshooting
  - Migration from single-asset

- **[Requirements Document](../.kiro/specs/llm-decision-engine/requirements.md)**
  - Functional requirements
  - Acceptance criteria
  - System constraints

### For Planning

- **[Implementation Tasks](../.kiro/specs/llm-decision-engine/tasks.md)**
  - Complete task breakdown
  - Implementation status
  - Dependencies and notes
  - Success criteria

## Key Features

### Multi-Asset Trading
- Analyze multiple perpetual futures contracts simultaneously
- Portfolio-level decision making
- Optimized capital allocation across assets
- Concentration risk management

### AI-Powered Decisions
- Multiple LLM model support (Grok-4, GPT-4, DeepSeek R1)
- Structured decision generation
- Comprehensive market analysis
- Technical indicator integration

### Trading Strategies
- Conservative, aggressive, scalping, swing, and DCA strategies
- Per-account strategy assignment
- Strategy performance tracking
- Custom strategy support

### Risk Management
- Portfolio-wide validation
- Position size limits
- Leverage constraints
- Concentration risk checks

### Monitoring & Analytics
- Decision generation metrics
- Trading performance tracking
- API usage and cost monitoring
- Strategy effectiveness analysis

## Common Tasks

### Generate Multi-Asset Decision

```bash
curl -X POST "http://localhost:3000/api/v1/decisions/generate" \
  -H "Content-Type: application/json" \
  -d '{"account_id": 1}'
```

See: [API Documentation - Generate Decision](LLM_DECISION_ENGINE_API.md#1-generate-trading-decision)

### Configure Assets

```bash
export ASSETS="BTCUSDT,ETHUSDT,SOLUSDT"
```

See: [Deployment Guide - Multi-Asset Configuration](LLM_DECISION_ENGINE_DEPLOYMENT.md#multi-asset-configuration)

### Run Database Migration

```bash
cd backend
uv run alembic upgrade head
```

See: [Deployment Guide - Database Migration](LLM_DECISION_ENGINE_DEPLOYMENT.md#multi-asset-schema-migration)

### Monitor Performance

```bash
curl "http://localhost:3000/api/v1/decisions/metrics?timeframe=24h"
```

See: [API Documentation - Decision Metrics](LLM_DECISION_ENGINE_API.md#7-get-decision-metrics)

### Switch Trading Strategy

```bash
curl -X POST "http://localhost:3000/api/v1/strategies/account/1/switch" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id": "aggressive_scalping"}'
```

See: [API Documentation - Switch Strategy](LLM_DECISION_ENGINE_API.md#6-switch-account-strategy)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Decision Engine                              │
│  • Multi-Asset Analysis                                         │
│  • Portfolio-Level Decisions                                    │
│  • Strategy Management                                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼              ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Context Builder │  │   LLM Service    │  │    Validator     │
│  • Market Data   │  │  • OpenRouter    │  │  • Schema Check  │
│  • Indicators    │  │  • Multi-Model   │  │  • Risk Check    │
│  • Account State │  │  • Prompts       │  │  • Business Rules│
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

See: [Design Document - Architecture](../.kiro/specs/llm-decision-engine/design.md#architecture)

## Multi-Asset Decision Structure

```json
{
  "decisions": [
    {
      "asset": "BTCUSDT",
      "action": "buy",
      "allocation_usd": 5000.0,
      "tp_price": 52000.0,
      "sl_price": 48000.0,
      "rationale": "Strong bullish momentum",
      "confidence": 85.0,
      "risk_level": "medium"
    }
  ],
  "portfolio_rationale": "Focus on BTC strength",
  "total_allocation_usd": 5000.0,
  "portfolio_risk_level": "medium"
}
```

See: [API Documentation - Decision Structure](LLM_DECISION_ENGINE_API.md#multi-asset-decision-structure)

## Environment Variables

### Required
```bash
ASTERDEX_API_KEY=your_key
ASTERDEX_API_SECRET=your_secret
OPENROUTER_API_KEY=your_key
DATABASE_URL=postgresql+asyncpg://...
ASSETS=BTCUSDT,ETHUSDT,SOLUSDT
```

### Optional
```bash
LLM_MODEL=x-ai/grok-4
INTERVAL=1h
LONG_INTERVAL=4h
LEVERAGE=2.0
MAX_POSITION_SIZE_USD=10000.0
```

See: [Deployment Guide - Environment Configuration](LLM_DECISION_ENGINE_DEPLOYMENT.md#environment-configuration)

## Troubleshooting

### Common Issues

1. **Insufficient market data** → [Solution](LLM_DECISION_ENGINE_DEPLOYMENT.md#issue-1-insufficient-market-data-error)
2. **High validation failure rate** → [Solution](LLM_DECISION_ENGINE_DEPLOYMENT.md#issue-2-high-validation-failure-rate)
3. **Slow decision generation** → [Solution](LLM_DECISION_ENGINE_DEPLOYMENT.md#issue-3-slow-decision-generation)
4. **LLM API errors** → [Solution](LLM_DECISION_ENGINE_DEPLOYMENT.md#issue-4-llm-api-errors)
5. **Database migration failures** → [Solution](LLM_DECISION_ENGINE_DEPLOYMENT.md#issue-5-database-migration-failures)

See: [Deployment Guide - Troubleshooting](LLM_DECISION_ENGINE_DEPLOYMENT.md#troubleshooting)

## Migration Guide

Migrating from single-asset to multi-asset system:

1. Backup existing data
2. Update configuration (SYMBOL → ASSETS)
3. Run database migration
4. Verify migration
5. Update application code
6. Test functionality

See: [Deployment Guide - Migration from Single-Asset](LLM_DECISION_ENGINE_DEPLOYMENT.md#migration-from-single-asset)

## Performance Tuning

### Optimal Configuration

- **Assets**: 3-5 for best performance
- **LLM Model**: x-ai/grok-4 (default, balanced)
- **Cache TTL**: 300 seconds (decisions)
- **Rate Limits**: 60 req/min (decisions)

See: [Deployment Guide - Performance Tuning](LLM_DECISION_ENGINE_DEPLOYMENT.md#performance-tuning)

## Monitoring

### Key Metrics

- Decision generation time (target: < 5s)
- Validation success rate (target: > 95%)
- Win rate by asset
- Total P&L
- API costs

### Log Files

```
backend/logs/
├── llm.log          # LLM decisions and API calls
├── trading.log      # Trading execution
├── market_data.log  # Market data collection
└── errors.log       # Error-only logs
```

See: [Deployment Guide - Monitoring](LLM_DECISION_ENGINE_DEPLOYMENT.md#monitoring-and-observability)

## Support Resources

- **API Examples**: [API Documentation](LLM_DECISION_ENGINE_API.md#common-usage-scenarios)
- **Deployment Steps**: [Deployment Guide](LLM_DECISION_ENGINE_DEPLOYMENT.md#deployment-options)
- **Troubleshooting**: [Deployment Guide - Troubleshooting](LLM_DECISION_ENGINE_DEPLOYMENT.md#troubleshooting)
- **System Logs**: `backend/logs/`
- **Configuration**: `backend/.env.example`

## Version History

- **v1.0** - Initial multi-asset implementation
  - Multi-asset decision generation
  - Portfolio-level analysis
  - Strategy management
  - Comprehensive validation

## Next Steps

1. **For New Users**: Start with [API Documentation](LLM_DECISION_ENGINE_API.md)
2. **For Deployment**: Follow [Deployment Guide](LLM_DECISION_ENGINE_DEPLOYMENT.md)
3. **For Development**: Review [Design Document](../.kiro/specs/llm-decision-engine/design.md)
4. **For Migration**: See [Migration Guide](LLM_DECISION_ENGINE_DEPLOYMENT.md#migration-from-single-asset)

---

**Last Updated**: 2025-01-15
**Status**: Production Ready
**Version**: 1.0
