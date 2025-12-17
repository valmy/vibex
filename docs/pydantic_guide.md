# SQLAlchemy 2.0+ Style Migration Guide

## The Problem

Your `base.py` was using the **old declarative style**:

```python
from sqlalchemy import Column, DateTime, Integer, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
```

This old style doesn't provide type information to MyPy. When you try to instantiate a model:

```python
account = Account(name="test", user_id=1, description="test")
```

MyPy can't verify that these keyword arguments are valid because the old `Column()` API doesn't expose proper type hints for `__init__`.

## The Solution: Modern Mapped Types

The new style uses `Mapped` type annotations:

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class BaseModel(DeclarativeBase):
    __abstract__ = True
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

## Key Changes

### 1. **BaseModel inheritance**
```python
# Old
from sqlalchemy.orm import declarative_base
Base = declarative_base()
class BaseModel(Base):

# New
from sqlalchemy.orm import DeclarativeBase
class BaseModel(DeclarativeBase):
```

### 2. **Column definitions with type hints**
```python
# Old
id = Column(Integer, primary_key=True, index=True)

# New
id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
```

### 3. **Datetime with timezone awareness**
```python
# Old
created_at = Column(DateTime, server_default=func.now())

# New
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    nullable=False,
)
```

### 4. **Optional fields**
```python
# Old
api_key = Column(String(255), nullable=True)

# New
api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

### 5. **Relationships with List types**
```python
# Old (in account.py)
accounts = relationship("Account", back_populates="user")

# New
accounts: Mapped[List["Account"]] = relationship(
    "Account", back_populates="user", cascade="all, delete-orphan"
)
```

## Why MyPy Now Works

With `Mapped` types and `DeclarativeBase`:

1. **SQLAlchemy plugin understands the schema** — The SQLAlchemy MyPy plugin now has proper type information
2. **`__init__` is auto-generated with types** — SQLAlchemy generates an `__init__` that accepts all mapped fields as keyword arguments
3. **Type checking catches errors** — MyPy can verify you're passing valid field names with correct types

Example:
```python
# ✅ This now type-checks correctly
account = Account(
    name="test",
    user_id=1,
    description="test",  # MyPy knows this is valid
    leverage=2.0,
)

# ❌ This will be caught by MyPy
account = Account(
    name="test",
    invalid_field="test",  # MyPy error: unexpected keyword argument
)
```

## Migration Checklist

- [x] Update `base.py` to use `DeclarativeBase`
- [x] Add `Mapped` type annotations to all models
- [x] Remove custom `__init__` methods (SQLAlchemy generates them now)
- [x] Use `mapped_column()` instead of `Column()`
- [x] Add timezone support to DateTime fields
- [x] Update relationships with `List[]` type hints
- [ ] Run `mypy .` to verify no errors
- [ ] Update all other model files to use `Mapped` style

## Running MyPy

```bash
mypy .
```

You should now see either:
- No errors (ideal!)
- Only legitimate type errors (not "unexpected keyword argument")

## Backwards Compatibility

The old-style models will still work at runtime, but:
- MyPy won't type-check them properly
- You lose IDE autocomplete for model instantiation
- Type safety is compromised

Update all models in your codebase to use the new style for consistency.

## Resources

- [SQLAlchemy 2.0 Migration Guide](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html)
- [SQLAlchemy ORM 2.0 Style](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [MyPy SQLAlchemy Plugin](https://docs.sqlalchemy.org/en/20/orm/extensions/mypy_plugin.html)
