# Product Overview

**Vibex** is an LLM-powered cryptocurrency trading agent designed for AsterDEX futures trading.

## Core Features

- **AI-Driven Trading**: Uses large language models (LLMs) via OpenRouter API for market analysis and trading decisions
- **Real-time Market Data**: Integrates with AsterDEX API for live cryptocurrency market data
- **Technical Analysis**: Built-in technical indicators and analysis tools (TA-Lib integration)
- **Multi-Asset Support**: Trades multiple cryptocurrencies (BTC, ETH, SOL by default)
- **Risk Management**: Configurable leverage (2x-5x), position sizing, circuit breakers, and A/B testing
- **Performance Tracking**: Comprehensive trading metrics, diary entries, and income history
- **WebSocket Support**: Real-time data streaming and notifications
- **Multi-Account Mode**: Support for multiple trading accounts with separate configurations
- **Configuration Management**: Hot-reloadable configuration with validation and caching

## Architecture

- **Backend**: FastAPI-based REST API with WebSocket support
- **Database**: PostgreSQL 16 with TimescaleDB extension for time-series data optimization
- **LLM Integration**: OpenRouter API for multiple model access (Grok-4 default)
- **Trading Platform**: AsterDEX futures trading integration via aster-connector-python
- **Containerized**: Docker/Podman deployment ready with TimescaleDB image
- **Configuration**: Environment-based with hot-reload capabilities
- **Monitoring**: Structured JSON logging with separate log files by domain

## Development Philosophy

- **CRUSH Development**: Build/Lint/Test focused development workflow
- **Quality First**: Black formatting, Ruff linting, MyPy type checking, comprehensive testing
- **Async-First**: Built for high-performance async operations
- **Observability**: Comprehensive logging, metrics tracking, and error handling

## Target Users

Cryptocurrency traders seeking AI-powered trading automation with transparent decision-making, comprehensive performance tracking, and enterprise-grade reliability.