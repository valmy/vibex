# LLM Decision Engine - Deployment Guide

## Overview

This guide covers deploying the LLM Decision Engine in various environments, from development to production, with comprehensive monitoring and alerting setup.

## Prerequisites

### System Requirements

**Minimum Requirements:**

- CPU: 2 cores
- RAM: 4GB
- Storage: 20GB SSD
- Network: Stable internet connection

**Recommended Requirements:**

- CPU: 4+ cores
- RAM: 8GB+
- Storage: 50GB+ SSD
- Network: High-speed internet with low latency

### Software Dependencies

- **Container Runtime**: Podman or Docker
- **Python**: 3.13+
- **Database**: PostgreSQL 17 with TimescaleDB
- **Cache**: Redis (optional but recommended)

## Environment Setup

### 1. Development Environment

**Quick Start:**

```bash
# Clone repository
git clone <repository-url>
cd vibex/backend

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env

# Start services
uv run podman-compose up -d

# Run migrations
uv run alembic upgrade head

# Verify deployment
curl http://localhost:3000/api/v1/monitoring/health/system
```

**Environment Variables:**

```bash
# Required variables
OPENROUTER_API_KEY=your_openrouter_key
ASTERDEX_API_KEY=your_asterdex_key
ASTERDEX_API_SECRET=your_asterdex_secret

# Optional optimizations
LLM_CACHE_ENABLED=true
DECISION_CACHE_TTL=300
CIRCUIT_BREAKER_ENABLED=true
```

### 2. Production Environment

**Production Configuration:**

```bash
# Production environment settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Security settings
SECRET_KEY=your_super_secure_random_string_here
CORS_ORIGINS=https://yourdomain.com

# Performance settings
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
UVICORN_WORKERS=4
```

**SSL/TLS Setup:**

```yaml
# Add to podman-compose.yml for production
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
```

## Container Deployment

### 1. Using Podman Compose

**Basic Deployment:**

```bash
# Start all services
cd backend && uv run podman-compose up -d

# Check service status
uv run podman-compose ps

# View logs
uv run podman-compose logs -f backend

# Stop services
uv run podman-compose down
```

**With Monitoring:**

```bash
# Start with monitoring stack
uv run podman-compose --profile monitoring up -d

# Access Grafana dashboard
open http://localhost:3001
# Login: admin/admin
```

### 2. Using Docker

**Docker Commands:**

```bash
# Build image
docker build -t trading-agent:latest .

# Run with environment file
docker run -d \
  --name trading-agent \
  --env-file .env \
  -p 3000:3000 \
  trading-agent:latest

# Check logs
docker logs -f trading-agent
```

### 3. Kubernetes Deployment

**Kubernetes Manifests:**

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-agent
spec:
  replicas: 2
  selector:
    matchLabels:
      app: trading-agent
  template:
    metadata:
      labels:
        app: trading-agent
    spec:
      containers:
      - name: trading-agent
        image: trading-agent:latest
        ports:
        - containerPort: 3000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: database-url
        - name: OPENROUTER_API_KEY
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: openrouter-key
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/v1/monitoring/health/system
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /api/v1/monitoring/health/system
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 10
```

## Database Setup

### 1. PostgreSQL with TimescaleDB

**Manual Setup:**

```bash
# Install PostgreSQL 17
sudo apt update
sudo apt install postgresql-17 postgresql-contrib-17

# Install TimescaleDB
sudo apt install timescaledb-2-postgresql-17

# Configure PostgreSQL
sudo -u postgres psql -c "CREATE USER trading_user WITH PASSWORD 'secure_password';"
sudo -u postgres psql -c "CREATE DATABASE trading_db OWNER trading_user;"
sudo -u postgres psql -d trading_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Run migrations
cd backend && uv run alembic upgrade head
```

**Container Setup:**

```bash
# Using official TimescaleDB image
podman run -d \
  --name postgres \
  -e POSTGRES_USER=trading_user \
  -e POSTGRES_PASSWORD=secure_password \
  -e POSTGRES_DB=trading_db \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  timescale/timescaledb:latest-pg17
```

### 2. Database Optimization

**Performance Tuning:**

```sql
-- PostgreSQL configuration for production
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;

-- Reload configuration
SELECT pg_reload_conf();
```

**Backup Strategy:**

```bash
#!/bin/bash
# backup.sh - Daily database backup script

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="trading_db"

# Create backup
pg_dump -h localhost -U trading_user -d $DB_NAME | gzip > "$BACKUP_DIR/backup_$DATE.sql.gz"

# Keep only last 7 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete

# Upload to cloud storage (optional)
# aws s3 cp "$BACKUP_DIR/backup_$DATE.sql.gz" s3://your-backup-bucket/
```

## Monitoring and Alerting

### 1. Health Check Endpoints

**System Health:**

```bash
# Check overall system health
curl http://localhost:3000/api/v1/monitoring/health/system

# Check performance metrics
curl http://localhost:3000/api/v1/monitoring/performance

# Check LLM service status
curl http://localhost:3000/api/v1/decisions/health
```

### 2. Prometheus Metrics

**Custom Metrics Endpoint:**

```python
# Add to main.py for Prometheus integration
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Metrics
decision_counter = Counter('trading_decisions_total', 'Total decisions generated')
decision_duration = Histogram('trading_decision_duration_seconds', 'Decision generation time')
active_strategies = Gauge('trading_active_strategies', 'Number of active strategies')

@app.get("/api/v1/monitoring/metrics/prometheus")
async def prometheus_metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### 3. Log Aggregation

**Structured Logging:**

```python
# Configure structured logging
import structlog

logger = structlog.get_logger()

# Log decision events
logger.info(
    "decision_generated",
    symbol="BTCUSDT",
    account_id=1,
    action="buy",
    confidence=85.5,
    processing_time_ms=2500
)
```

**Log Rotation:**

```bash
# /etc/logrotate.d/trading-agent
/app/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 trading trading
    postrotate
        systemctl reload trading-agent
    endscript
}
```

### 4. Alerting Setup

**Email Alerts:**

```python
# alerts.py
import smtplib
from email.mime.text import MIMEText

def send_alert(subject, message):
    msg = MIMEText(message)
    msg['Subject'] = f"[Trading Agent] {subject}"
    msg['From'] = "alerts@yourdomain.com"
    msg['To'] = "admin@yourdomain.com"

    server = smtplib.SMTP('smtp.yourdomain.com', 587)
    server.starttls()
    server.login("alerts@yourdomain.com", "password")
    server.send_message(msg)
    server.quit()

# Usage in monitoring
if system_health["overall_status"] != "healthy":
    send_alert("System Health Alert", f"Issues: {system_health['issues']}")
```

**Slack Integration:**

```python
# slack_alerts.py
import requests

def send_slack_alert(message):
    webhook_url = "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"

    payload = {
        "text": f"🚨 Trading Agent Alert: {message}",
        "channel": "#trading-alerts",
        "username": "Trading Agent"
    }

    requests.post(webhook_url, json=payload)
```

### Testing Deployment
Here is a summary of the deployment decisions, setup steps, and future update process for your `vibex-backend` project.

1.  **Environment:** We are using `podman` and `podman-compose` (versions 4.9.3 and 1.0.6) from the Ubuntu 24.04 `apt` repositories.
2.  **Build Process:** To keep the server clean and create a consistent, testable artifact, we are **building the container locally** and pushing it to a registry. We are **not** building on the server.
3.  **Container Registry:** We are using **GitHub Container Registry (GHCR)** to host the backend image (`ghcr.io/valmy/vibex-backend:latest`).
4.  **Secrets:** We are **not** committing the `.env` file. It is securely transferred to the server using `scp` and read by `podman-compose`.
5.  **Process Management:** We are using a **rootless `systemd` user service** for the `vibex` user. This is more secure than running as root and ensures the application starts on boot (via `loginctl enable-linger`).
6.  **SSL (Next Step):** We will use **Caddy** as a reverse proxy on the host to provide automatic SSL for your domain, forwarding traffic to the `backend` container.

#### How The Server is Set Up (The "How")

This is the final, working configuration after our troubleshooting.

1.  **Linger (Root Command):**
    We enabled lingering for the `vibex` user (one time, as root) to allow their services to start on boot:

    ```bash
    sudo loginctl enable-linger vibex
    ```

2.  **Project Location (As `vibex` user):**

      * The repository is cloned to `/home/vibex/vibex/`.
      * The working directory is `/home/vibex/vibex/backend/`.

3.  **Secrets File (As `vibex` user):**
    The secret `.env` file was securely copied to `/home/vibex/vibex/backend/.env`.

4.  **`podman-compose.yml` (Modified):**
    The `backend` service in `podman-compose.yml` was modified to use the pre-built image, not the `Dockerfile`:

    ```yaml
    backend:
      # build: ... (THIS SECTION WAS REMOVED)
      image: ghcr.io/valmy/vibex-backend:latest
      container_name: trading-agent-backend
      # ... rest of the service definition
    ```

5.  **The `systemd` Service (The Key Component):**
    After finding the `podman-compose systemd` command was unreliable, we created a manual service file.

      * **File Location:** `/home/vibex/.config/systemd/user/vibex-backend.service`
      * **File Content:**
        ```ini
        [Unit]
        Description=Vibex Backend (Podman Compose - Rootless)

        [Service]
        Type=simple
        WorkingDirectory=/home/vibex/vibex/backend
        ExecStart=/usr/bin/podman-compose up
        ExecStop=/usr/bin/podman-compose down
        Restart=always

        [Install]
        WantedBy=default.target
        ```

#### The Update Workflow (How to Deploy New Code)

This is your new end-to-end process for shipping an update.

##### 1\. On Your Local Machine

  * `cd` into your `vibex/backend` directory.
  * Make your code changes.
  * Build and push the new image:
    ```bash
    # Build and tag the image
    podman build -t ghcr.io/valmy/vibex-backend:latest .

    # Push the image to the registry
    podman push ghcr.io/valmy/vibex-backend:latest
    ```

##### 2\. On Your Ubuntu Server

  * Log in as the `vibex` user: `ssh vibex@your-server-ip`
  * Navigate to the project directory:
    ```bash
    cd /home/vibex/vibex/backend
    ```
  * Pull the new image:
    ```bash
    # This just downloads the new "latest" image from GHCR
    podman-compose pull
    ```
  * Restart the `systemd` service:
    ```bash
    # This will run ExecStop (podman-compose down)
    # and then ExecStart (podman-compose up -d)
    # The new service will automatically use the new image.
    systemctl --user restart vibex-backend.service
    ```

#### Important Notes from Our Troubleshooting

  * **`systemctl --user` vs. `sudo`:** We confirmed you must **never** use `sudo` with `systemctl --user` commands. It will fail with a "No medium found" error.
  * **`network-online.target`:** This target isn't available to rootless user services by default. We removed it from the `[Unit]` section to fix the "not found" error.
  * **Crash Loops (`container name... is already in use`):** If the service gets stuck, the fix is to stop the `systemd` service first, then manually clean up the environment.
    1.  `systemctl --user stop vibex-backend.service`
    2.  `podman-compose down` (or `podman rm -f <id>` for "zombie" containers)
    3.  `systemctl --user start vibex-backend.service`

## Security Configuration

### 1. API Security

**Authentication Setup:**

```python
# Enhanced security configuration
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

# Rate limiting
@app.on_event("startup")
async def startup():
    redis = aioredis.from_url("redis://localhost:6379")
    await FastAPILimiter.init(redis)

# Apply rate limiting to endpoints
@router.post("/decisions/generate")
@limiter(times=60, seconds=60)  # 60 requests per minute
async def generate_decision():
    pass
```

**CORS Configuration:**

```python
# Secure CORS setup for production
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domains only
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### 2. Secrets Management

**Environment Variables:**

```bash
# Use secrets management in production
export OPENROUTER_API_KEY=$(vault kv get -field=api_key secret/openrouter)
export ASTERDEX_API_KEY=$(vault kv get -field=api_key secret/asterdex)
```

**Docker Secrets:**

```yaml
# docker-compose.yml with secrets
services:
  backend:
    secrets:
      - openrouter_key
      - asterdx_key
    environment:
      OPENROUTER_API_KEY_FILE: /run/secrets/openrouter_key
      ASTERDX_API_KEY_FILE: /run/secrets/asterdx_key

secrets:
  openrouter_key:
    file: ./secrets/openrouter_key.txt
  asterdx_key:
    file: ./secrets/asterdx_key.txt
```

## Performance Optimization

### 1. Application Tuning

**Uvicorn Configuration:**

```bash
# Production server settings
uvicorn src.app.main:app \
  --host 0.0.0.0 \
  --port 3000 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --loop asyncio \
  --http httptools \
  --access-log \
  --log-level info
```

**Memory Optimization:**

```python
# Memory management settings
import gc

# Tune garbage collection
gc.set_threshold(700, 10, 10)

# Periodic cleanup
async def cleanup_task():
    while True:
        await asyncio.sleep(1800)  # 30 minutes
        gc.collect()
        clear_expired_caches()
```

### 2. Database Optimization

**Connection Pooling:**

```python
# Optimized database configuration
DATABASE_CONFIG = {
    "pool_size": 20,
    "max_overflow": 10,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
    "echo": False
}
```

**Query Optimization:**

```sql
-- Add indexes for common queries
CREATE INDEX CONCURRENTLY idx_decisions_account_timestamp
ON decisions(account_id, timestamp DESC);

CREATE INDEX CONCURRENTLY idx_decisions_symbol_timestamp
ON decisions(symbol, timestamp DESC);

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM decisions
WHERE account_id = 1 AND timestamp > NOW() - INTERVAL '24 hours';
```

## Troubleshooting

### 1. Common Issues

**Service Won't Start:**

```bash
# Check logs
uv run podman-compose logs backend

# Check configuration
uv run python -c "from app.core.config import get_settings; print(get_settings())"

# Test database connection
uv run python -c "from app.db.session import engine; print(engine.execute('SELECT 1'))"
```

**High Memory Usage:**

```bash
# Monitor memory usage
docker stats trading-agent

# Check for memory leaks
curl http://localhost:3000/api/v1/decisions/cache/stats

# Clear caches if needed
curl -X POST http://localhost:3000/api/v1/decisions/cache/clear
```

### 2. Performance Issues

**Slow Response Times:**

```bash
# Check system performance
curl http://localhost:3000/api/v1/monitoring/performance

# Monitor database queries
sudo -u postgres psql -d trading_db -c "SELECT query, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Check LLM service latency
curl http://localhost:3000/api/v1/decisions/health
```

## Maintenance

### 1. Regular Tasks

**Daily:**

- Check system health
- Review error logs
- Monitor performance metrics
- Verify backup completion

**Weekly:**

- Update dependencies
- Clean old logs
- Review strategy performance
- Database maintenance

**Monthly:**

- Security updates
- Capacity planning
- Performance optimization
- Disaster recovery testing

### 2. Update Procedures

**Application Updates:**

```bash
# Pull latest changes
git pull origin main

# Update dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Restart services
uv run podman-compose restart backend
```

**Database Migrations:**

```bash
# Create migration
uv run alembic revision --autogenerate -m "Description"

# Review migration
cat alembic/versions/latest_migration.py

# Apply migration
uv run alembic upgrade head
```

This deployment guide provides comprehensive instructions for deploying the LLM Decision Engine in various environments with proper monitoring, security, and maintenance procedures.
