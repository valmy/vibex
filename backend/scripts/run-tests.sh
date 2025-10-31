#!/bin/bash

# AI Trading Agent - Test Runner Script
# This script sets up the environment and runs tests with the correct database configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 AI Trading Agent Test Runner${NC}"
echo "=================================="

# Check if we're in the backend directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}Error: pyproject.toml not found. Please run this script from the backend directory.${NC}"
    exit 1
fi

# Check if .env.testing exists
if [ ! -f ".env.testing" ]; then
    echo -e "${YELLOW}Warning: .env.testing not found. Tests will use default configurations.${NC}"
fi

# Check if PostgreSQL is accessible on localhost
echo -e "${YELLOW}🔍 Checking PostgreSQL connection...${NC}"
if command -v pg_isready &> /dev/null; then
    if pg_isready -h localhost -p 5432 -U trading_user -d trading_db &> /dev/null; then
        echo -e "${GREEN}✅ PostgreSQL is accessible on localhost:5432${NC}"
        DB_READY=true
    else
        echo -e "${RED}❌ PostgreSQL is not accessible on localhost:5432${NC}"
        echo "Please ensure:"
        echo "1. PostgreSQL container is running"
        echo "2. Port 5432 is exposed to localhost"
        echo "3. Database 'trading_db' with user 'trading_user' exists"
        echo ""
        echo "You can start the database with: ./scripts/start-test-db.sh"
        DB_READY=false
    fi
else
    echo -e "${YELLOW}⚠️  PostgreSQL client tools not installed, skipping connection check${NC}"
    DB_READY=false
fi

# Parse command line arguments
RUN_INTEGRATION=false
RUN_UNIT=false
RUN_PERFORMANCE=false
COVERAGE=false

if [ $# -eq 0 ]; then
    # Default: run all tests
    RUN_INTEGRATION=true
    RUN_UNIT=true
    COVERAGE=true
else
    case "$1" in
        "unit")
            RUN_UNIT=true
            ;;
        "integration")
            RUN_INTEGRATION=true
            ;;
        "performance")
            RUN_PERFORMANCE=true
            ;;
        "all")
            RUN_INTEGRATION=true
            RUN_UNIT=true
            RUN_PERFORMANCE=true
            COVERAGE=true
            ;;
        "coverage")
            COVERAGE=true
            RUN_INTEGRATION=true
            RUN_UNIT=true
            ;;
        *)
            echo -e "${RED}Unknown test type: $1${NC}"
            echo "Usage: $0 [unit|integration|performance|all|coverage]"
            exit 1
            ;;
    esac
fi

# Check if we should proceed with database tests
if [ "$RUN_INTEGRATION" = true ] && [ "$DB_READY" = false ]; then
    echo -e "${YELLOW}⚠️  Integration tests require database access. Continue anyway? (y/N)${NC}"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Skipping integration tests."
        RUN_INTEGRATION=false
    fi
fi

# Build test command
TEST_CMD="python -m pytest"

if [ "$COVERAGE" = true ]; then
    TEST_CMD="$TEST_CMD --cov=src --cov-report=html --cov-report=term"
fi

# Test paths
TEST_PATHS=""

if [ "$RUN_UNIT" = true ]; then
    TEST_PATHS="$TEST_PATHS tests/unit/"
fi

if [ "$RUN_INTEGRATION" = true ]; then
    TEST_PATHS="$TEST_PATHS tests/integration/"
fi

if [ "$RUN_PERFORMANCE" = true ]; then
    TEST_PATHS="$TEST_PATHS tests/performance/"
fi

# Additional pytest options
PYTEST_OPTS="-v --tb=short"

# Run the tests
echo ""
echo -e "${GREEN}🧪 Running tests...${NC}"
echo "Command: $TEST_CMD $PYTEST_OPTS $TEST_PATHS"
echo ""

# Set environment for testing
export ENVIRONMENT=testing

# Run the test command
if eval "$TEST_CMD $PYTEST_OPTS $TEST_PATHS"; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
    if [ "$COVERAGE" = true ]; then
        echo -e "${GREEN}📊 Coverage report generated in htmlcov/index.html${NC}"
    fi
else
    echo ""
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✨ Test run completed successfully!${NC}"
