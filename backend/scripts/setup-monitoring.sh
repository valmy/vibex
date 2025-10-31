#!/bin/bash

# LLM Decision Engine - Monitoring Setup Script
# This script sets up comprehensive monitoring and alerting for the system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MONITORING_DIR="$PROJECT_ROOT/monitoring"

echo -e "${GREEN}🚀 Setting up LLM Decision Engine Monitoring${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."

    # Check if podman-compose is available
    if ! command -v podman-compose &> /dev/null; then
        print_error "podman-compose is not installed"
        exit 1
    fi

    # Check if curl is available
    if ! command -v curl &> /dev/null; then
        print_error "curl is not installed"
        exit 1
    fi

    print_status "Prerequisites check passed"
}

# Create monitoring directories
create_directories() {
    echo "Creating monitoring directories..."

    mkdir -p "$MONITORING_DIR"/{prometheus,grafana/{dashboards,datasources},alertmanager}
    mkdir -p "$PROJECT_ROOT/logs"/{llm,decisions,strategies,monitoring}

    print_status "Monitoring directories created"
}

# Setup Prometheus configuration
setup_prometheus() {
    echo "Setting up Prometheus configuration..."

    # Prometheus main config is already created
    # Create alert rules if they don't exist
    if [ ! -f "$MONITORING_DIR/alert_rules.yml" ]; then
        print_warning "Alert rules not found, using default configuration"
    fi

    print_status "Prometheus configuration ready"
}

# Setup Grafana dashboards
setup_grafana() {
    echo "Setting up Grafana dashboards..."

    # Create LLM Decision Engine dashboard
    cat > "$MONITORING_DIR/grafana/dashboards/llm-decision-engine.json" << 'EOF'
{
  "dashboard": {
    "id": null,
    "title": "LLM Decision Engine",
    "tags": ["trading", "llm", "decisions"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Decision Generation Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(trading_decisions_total[5m])",
            "legendFormat": "Decisions/sec"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "Decision Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(trading_decision_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(trading_decision_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
      },
      {
        "id": 3,
        "title": "System Health",
        "type": "stat",
        "targets": [
          {
            "expr": "trading_agent_system_health",
            "legendFormat": "Health Status"
          }
        ],
        "gridPos": {"h": 4, "w": 6, "x": 0, "y": 8}
      },
      {
        "id": 4,
        "title": "Cache Hit Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "trading_agent_cache_hit_rate",
            "legendFormat": "Hit Rate %"
          }
        ],
        "gridPos": {"h": 4, "w": 6, "x": 6, "y": 8}
      },
      {
        "id": 5,
        "title": "Active Strategies",
        "type": "stat",
        "targets": [
          {
            "expr": "trading_active_strategies",
            "legendFormat": "Active Strategies"
          }
        ],
        "gridPos": {"h": 4, "w": 6, "x": 12, "y": 8}
      },
      {
        "id": 6,
        "title": "Error Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(trading_agent_errors_total[5m])",
            "legendFormat": "Errors/sec"
          }
        ],
        "gridPos": {"h": 4, "w": 6, "x": 18, "y": 8}
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
EOF

    print_status "Grafana dashboards configured"
}

# Setup log rotation
setup_log_rotation() {
    echo "Setting up log rotation..."

    # Create logrotate configuration
    sudo tee /etc/logrotate.d/trading-agent > /dev/null << EOF
$PROJECT_ROOT/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $(whoami) $(whoami)
    postrotate
        # Send HUP signal to application to reopen log files
        pkill -HUP -f "uvicorn.*trading-agent" || true
    endscript
}

$PROJECT_ROOT/logs/*/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $(whoami) $(whoami)
}
EOF

    print_status "Log rotation configured"
}

# Setup health check script
setup_health_checks() {
    echo "Setting up health check scripts..."

    # Create health check script
    cat > "$PROJECT_ROOT/scripts/health-check.sh" << 'EOF'
#!/bin/bash

# Health check script for LLM Decision Engine
API_URL="http://localhost:3000"
LOG_FILE="/tmp/health-check.log"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Check system health
check_system_health() {
    response=$(curl -s -w "%{http_code}" "$API_URL/api/v1/monitoring/health/system" -o /tmp/health_response.json)

    if [ "$response" = "200" ]; then
        overall_status=$(jq -r '.overall_status' /tmp/health_response.json 2>/dev/null)

        if [ "$overall_status" = "healthy" ]; then
            log "✅ System health: OK"
            return 0
        else
            issues=$(jq -r '.issues[]' /tmp/health_response.json 2>/dev/null | tr '\n' ', ')
            log "⚠️  System health: DEGRADED - Issues: $issues"
            return 1
        fi
    else
        log "❌ System health check failed: HTTP $response"
        return 2
    fi
}

# Check performance metrics
check_performance() {
    response=$(curl -s -w "%{http_code}" "$API_URL/api/v1/monitoring/performance" -o /tmp/perf_response.json)

    if [ "$response" = "200" ]; then
        avg_response_time=$(jq -r '.decision_engine.avg_response_time_ms' /tmp/perf_response.json 2>/dev/null)
        error_rate=$(jq -r '.decision_engine.error_rate' /tmp/perf_response.json 2>/dev/null)

        if (( $(echo "$avg_response_time > 5000" | bc -l) )); then
            log "⚠️  High response time: ${avg_response_time}ms"
        fi

        if (( $(echo "$error_rate > 5.0" | bc -l) )); then
            log "⚠️  High error rate: ${error_rate}%"
        fi

        log "📊 Performance - Response time: ${avg_response_time}ms, Error rate: ${error_rate}%"
        return 0
    else
        log "❌ Performance check failed: HTTP $response"
        return 1
    fi
}

# Main health check
main() {
    log "🔍 Starting health check"

    health_status=0

    if ! check_system_health; then
        health_status=1
    fi

    if ! check_performance; then
        health_status=1
    fi

    if [ $health_status -eq 0 ]; then
        log "✅ All checks passed"
    else
        log "⚠️  Some checks failed"
    fi

    # Cleanup
    rm -f /tmp/health_response.json /tmp/perf_response.json

    exit $health_status
}

main "$@"
EOF

    chmod +x "$PROJECT_ROOT/scripts/health-check.sh"

    print_status "Health check scripts created"
}

# Setup alerting
setup_alerting() {
    echo "Setting up alerting..."

    # Create alert script
    cat > "$PROJECT_ROOT/scripts/send-alert.sh" << 'EOF'
#!/bin/bash

# Alert sending script
ALERT_TYPE="$1"
ALERT_MESSAGE="$2"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Log alert
echo "[$TIMESTAMP] ALERT [$ALERT_TYPE]: $ALERT_MESSAGE" >> /tmp/alerts.log

# Send email alert if configured
if [ -n "$ALERT_EMAIL_TO" ] && [ -n "$SMTP_HOST" ]; then
    echo "Subject: [Trading Agent] $ALERT_TYPE Alert

$ALERT_MESSAGE

Timestamp: $TIMESTAMP
System: $(hostname)" | sendmail "$ALERT_EMAIL_TO"
fi

# Send Slack alert if configured
if [ -n "$SLACK_WEBHOOK_URL" ]; then
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"🚨 Trading Agent Alert: [$ALERT_TYPE] $ALERT_MESSAGE\"}" \
        "$SLACK_WEBHOOK_URL"
fi

# Send webhook alert if configured
if [ -n "$ALERT_WEBHOOK_URL" ]; then
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"type\":\"$ALERT_TYPE\",\"message\":\"$ALERT_MESSAGE\",\"timestamp\":\"$TIMESTAMP\"}" \
        "$ALERT_WEBHOOK_URL"
fi
EOF

    chmod +x "$PROJECT_ROOT/scripts/send-alert.sh"

    print_status "Alerting scripts created"
}

# Setup cron jobs
setup_cron_jobs() {
    echo "Setting up cron jobs..."

    # Create cron job for health checks
    (crontab -l 2>/dev/null; echo "*/5 * * * * $PROJECT_ROOT/scripts/health-check.sh") | crontab -

    # Create cron job for log cleanup
    (crontab -l 2>/dev/null; echo "0 2 * * * find $PROJECT_ROOT/logs -name '*.log' -mtime +30 -delete") | crontab -

    # Create cron job for cache cleanup
    (crontab -l 2>/dev/null; echo "0 */6 * * * curl -X POST http://localhost:3000/api/v1/decisions/cache/clear >/dev/null 2>&1") | crontab -

    print_status "Cron jobs configured"
}

# Start monitoring services
start_monitoring() {
    echo "Starting monitoring services..."

    cd "$PROJECT_ROOT"

    # Start with monitoring profile
    uv run podman-compose --profile monitoring up -d

    # Wait for services to start
    echo "Waiting for services to start..."
    sleep 30

    # Check if services are running
    if uv run podman-compose ps | grep -q "Up"; then
        print_status "Monitoring services started successfully"

        echo ""
        echo "📊 Monitoring URLs:"
        echo "   - Grafana: http://localhost:3001 (admin/admin)"
        echo "   - Prometheus: http://localhost:9090"
        echo "   - API Health: http://localhost:3000/api/v1/monitoring/health/system"
        echo ""
    else
        print_error "Failed to start monitoring services"
        exit 1
    fi
}

# Verify monitoring setup
verify_setup() {
    echo "Verifying monitoring setup..."

    # Check API health endpoint
    if curl -s "http://localhost:3000/api/v1/monitoring/health/system" > /dev/null; then
        print_status "API health endpoint accessible"
    else
        print_warning "API health endpoint not accessible (service may still be starting)"
    fi

    # Check Prometheus
    if curl -s "http://localhost:9090/-/healthy" > /dev/null; then
        print_status "Prometheus is healthy"
    else
        print_warning "Prometheus not accessible"
    fi

    # Check Grafana
    if curl -s "http://localhost:3001/api/health" > /dev/null; then
        print_status "Grafana is accessible"
    else
        print_warning "Grafana not accessible"
    fi
}

# Main execution
main() {
    echo "Starting monitoring setup..."

    check_prerequisites
    create_directories
    setup_prometheus
    setup_grafana
    setup_log_rotation
    setup_health_checks
    setup_alerting
    setup_cron_jobs
    start_monitoring
    verify_setup

    echo ""
    print_status "Monitoring setup completed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Configure alerting by setting environment variables:"
    echo "      - ALERT_EMAIL_TO=admin@example.com"
    echo "      - SMTP_HOST=smtp.example.com"
    echo "      - SLACK_WEBHOOK_URL=https://hooks.slack.com/..."
    echo "   2. Import Grafana dashboards from monitoring/grafana/dashboards/"
    echo "   3. Set up additional alert rules in monitoring/alert_rules.yml"
    echo "   4. Test alerting with: ./scripts/send-alert.sh TEST 'Test alert message'"
    echo ""
}

# Run main function
main "$@"