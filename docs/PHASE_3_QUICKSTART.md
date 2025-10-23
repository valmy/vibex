# Phase 3: FastAPI Skeleton - QUICKSTART GUIDE

**Phase**: 3 of 5  
**Duration**: 2-3 days  
**Status**: Ready to start  

---

## 🎯 Phase 3 Objectives

Build the FastAPI application skeleton with database models, schemas, and API routes.

### Deliverables:
1. SQLAlchemy ORM models for all entities
2. Pydantic schemas for request/response validation
3. REST API routes for core operations
4. Database migrations with Alembic
5. WebSocket support for real-time data
6. Comprehensive error handling

---

## 📋 Tasks Breakdown

### Task 1: Database Models (SQLAlchemy ORM)
**File**: `backend/src/app/models/`

Create models for:
- `Account` - Trading accounts
- `MarketData` - OHLCV data
- `Position` - Open positions
- `Order` - Trading orders
- `Trade` - Executed trades
- `DiaryEntry` - Trading journal
- `PerformanceMetric` - Performance tracking

**Key Features**:
- Relationships between models
- Timestamps (created_at, updated_at)
- Indexes for performance
- Constraints and validations

### Task 2: Pydantic Schemas
**File**: `backend/src/app/schemas/`

Create schemas for:
- Account (Create, Read, Update)
- MarketData (Create, Read)
- Position (Create, Read, Update)
- Order (Create, Read, Update)
- Trade (Create, Read)
- DiaryEntry (Create, Read)
- PerformanceMetric (Create, Read)

**Key Features**:
- Request validation
- Response serialization
- Nested schemas
- Field validation rules

### Task 3: Database Session Management
**File**: `backend/src/app/db/session.py`

Implement:
- SQLAlchemy engine creation
- Session factory
- Async session support
- Connection pooling
- Health checks

### Task 4: API Routes
**File**: `backend/src/app/api/routes/`

Create routes for:
- `/api/v1/accounts` - Account management
- `/api/v1/market-data` - Market data endpoints
- `/api/v1/positions` - Position management
- `/api/v1/orders` - Order management
- `/api/v1/trades` - Trade history
- `/api/v1/diary` - Trading journal
- `/api/v1/performance` - Performance metrics

**Key Features**:
- CRUD operations
- Pagination
- Filtering
- Sorting
- Error handling

### Task 5: Database Migrations
**File**: `backend/alembic/`

Setup:
- Alembic initialization
- Migration templates
- Auto-migration generation
- Migration versioning

### Task 6: WebSocket Support
**File**: `backend/src/app/api/websockets/`

Implement:
- Market data streaming
- Order updates
- Position updates
- Real-time notifications

### Task 7: Error Handling
**File**: `backend/src/app/core/exceptions.py`

Create:
- Custom exception classes
- Exception handlers
- Error response formatting
- Logging integration

---

## 🛠️ Development Workflow

### 1. Start Development Environment
```bash
# Terminal 1: Start PostgreSQL
cd backend && uv run podman-compose up -d postgres

# Terminal 2: Start FastAPI with auto-reload
cd backend && .venv/bin/python -m uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Create Models
```bash
# Edit backend/src/app/models/__init__.py
# Create individual model files
```

### 3. Create Schemas
```bash
# Edit backend/src/app/schemas/__init__.py
# Create individual schema files
```

### 4. Create Routes
```bash
# Edit backend/src/app/api/routes/__init__.py
# Create individual route files
```

### 5. Test Endpoints
```bash
# Use curl or Postman
curl http://localhost:8000/docs  # Swagger UI
curl http://localhost:8000/redoc  # ReDoc
```

---

## 📚 Key Files to Create

```
backend/src/app/
├── models/
│   ├── __init__.py
│   ├── account.py
│   ├── market_data.py
│   ├── position.py
│   ├── order.py
│   ├── trade.py
│   ├── diary_entry.py
│   └── performance_metric.py
├── schemas/
│   ├── __init__.py
│   ├── account.py
│   ├── market_data.py
│   ├── position.py
│   ├── order.py
│   ├── trade.py
│   ├── diary_entry.py
│   └── performance_metric.py
├── api/
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── accounts.py
│   │   ├── market_data.py
│   │   ├── positions.py
│   │   ├── orders.py
│   │   ├── trades.py
│   │   ├── diary.py
│   │   └── performance.py
│   └── websockets/
│       ├── __init__.py
│       └── market_data.py
├── db/
│   ├── __init__.py
│   └── session.py
└── core/
    └── exceptions.py
```

---

## 🧪 Testing Strategy

### Unit Tests
```bash
cd backend && .venv/bin/pytest tests/unit/ -v
```

### Integration Tests
```bash
cd backend && .venv/bin/pytest tests/integration/ -v
```

### API Tests
```bash
cd backend && .venv/bin/pytest tests/api/ -v
```

---

## 📖 Documentation

- **Database Schema**: See `backend/init-db.sql`
- **Configuration**: See `backend/src/app/core/config.py`
- **Logging**: See `backend/src/app/core/logging.py`
- **Constants**: See `backend/src/app/core/constants.py`

---

## ✅ Completion Criteria

- [ ] All models created and tested
- [ ] All schemas created and validated
- [ ] All routes implemented and tested
- [ ] Database migrations working
- [ ] WebSocket endpoints functional
- [ ] Error handling comprehensive
- [ ] API documentation complete
- [ ] All tests passing
- [ ] Code coverage > 80%

---

## 🚀 Ready to Start?

When ready to begin Phase 3, run:
```bash
cd backend && uv run podman-compose up -d postgres
cd backend && .venv/bin/python -m uvicorn src.app.main:app --reload
```

Then start implementing the models, schemas, and routes!

**Next**: Phase 3 - FastAPI Skeleton Implementation

