#!/bin/bash

# AI Trading Agent - Test Database Setup Script
# This script starts PostgreSQL for testing on the host or via container

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🗄️  Test Database Setup${NC}"
echo "========================"

# Configuration
DB_USER="trading_user"
DB_PASSWORD="trading_password"
DB_NAME="trading_db"
DB_HOST="localhost"
DB_PORT="5432"

echo -e "${BLUE}Database Configuration:${NC}"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""

# Function to check if PostgreSQL is available via Docker/Podman
check_container_db() {
    echo -e "${YELLOW}🔍 Checking for PostgreSQL container...${NC}"
    
    if command -v podman &> /dev/null; then
        CONTAINER_CMD="podman"
    elif command -v docker &> /dev/null; then
        CONTAINER_CMD="docker"
    else
        echo -e "${RED}❌ Neither Podman nor Docker found${NC}"
        return 1
    fi
    
    echo -e "${BLUE}Using container command: $CONTAINER_CMD${NC}"
    
    # Check if container is already running
    if $CONTAINER_CMD ps --format "table {{.Names}}" | grep -q "trading-agent-postgres"; then
        echo -e "${GREEN}✅ PostgreSQL container is already running${NC}"
        
        # Check if port is exposed
        if $CONTAINER_CMD port trading-agent-postgres | grep -q "5432"; then
            echo -e "${GREEN}✅ Port 5432 is exposed${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Container is running but port 5432 is not exposed to host${NC}"
            echo "You may need to restart the container with port mapping."
            return 1
        fi
    else
        echo -e "${YELLOW}🐳 Starting PostgreSQL container for testing...${NC}"
        
        # Start a PostgreSQL container with port mapping
        $CONTAINER_CMD run -d \
            --name trading-agent-postgres-test \
            -e POSTGRES_USER="$DB_USER" \
            -e POSTGRES_PASSWORD="$DB_PASSWORD" \
            -e POSTGRES_DB="$DB_NAME" \
            -p "$DB_PORT:5432" \
            --rm \
            timescale/timescaledb:latest-pg17
            
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ PostgreSQL container started with port mapping${NC}"
            echo "Container name: trading-agent-postgres-test"
            
            # Wait for database to be ready
            echo -e "${YELLOW}⏳ Waiting for database to be ready...${NC}"
            sleep 10
            
            # Check if database is ready
            for i in {1..30}; do
                if $CONTAINER_CMD exec trading-agent-postgres-test pg_isready -U "$DB_USER" -d "$DB_NAME" &> /dev/null; then
                    echo -e "${GREEN}✅ Database is ready!${NC}"
                    return 0
                fi
                echo -n "."
                sleep 1
            done
            
            echo -e "${RED}❌ Database failed to become ready${NC}"
            $CONTAINER_CMD stop trading-agent-postgres-test &> /dev/null || true
            return 1
        else
            echo -e "${RED}❌ Failed to start PostgreSQL container${NC}"
            return 1
        fi
    fi
}

# Function to check if PostgreSQL is available locally
check_local_db() {
    echo -e "${YELLOW}🔍 Checking for local PostgreSQL installation...${NC}"
    
    if command -v psql &> /dev/null; then
        echo -e "${GREEN}✅ PostgreSQL client found${NC}"
        
        # Try to connect
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
            echo -e "${GREEN}✅ Local PostgreSQL is accessible${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Local PostgreSQL found but connection failed${NC}"
            echo "Please ensure:"
            echo "1. PostgreSQL server is running"
            echo "2. Database '$DB_NAME' exists"
            echo "3. User '$DB_USER' has access"
            echo ""
            
            # Offer to create database
            echo -e "${BLUE}Would you like to create the database? (y/N)${NC}"
            read -r response
            if [[ "$response" =~ ^[Yy]$ ]]; then
                create_local_db
            fi
            return 1
        fi
    else
        echo -e "${YELLOW}❌ Local PostgreSQL not found${NC}"
        return 1
    fi
}

# Function to create local database
create_local_db() {
    echo -e "${BLUE}🏗️  Creating local database...${NC}"
    
    # Create user (if not exists)
    if PGPASSWORD="$DB_PASSWORD" createuser -h "$DB_HOST" -p "$DB_PORT" -U postgres "$DB_USER" 2>/dev/null || true; then
        echo -e "${GREEN}✅ User '$DB_USER' created/verified${NC}"
    fi
    
    # Create database
    if createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" 2>/dev/null; then
        echo -e "${GREEN}✅ Database '$DB_NAME' created${NC}"
        
        # Enable TimescaleDB extension (if available)
        echo -e "${BLUE}Installing TimescaleDB extension...${NC}"
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" &> /dev/null || echo -e "${YELLOW}⚠️  TimescaleDB extension not available (using regular PostgreSQL)${NC}"
        
        return 0
    else
        echo -e "${RED}❌ Failed to create database${NC}"
        return 1
    fi
}

# Main logic
echo -e "${BLUE}How would you like to run the test database?${NC}"
echo "1) Use container (Podman/Docker) - recommended"
echo "2) Use local PostgreSQL installation"
echo "3) Auto-detect"
echo ""
echo -n "Choice [1-3]: "
read -r choice

case "$choice" in
    1)
        check_container_db || exit 1
        ;;
    2)
        check_local_db || exit 1
        ;;
    3)
        echo -e "${BLUE}🔍 Auto-detecting database availability...${NC}"
        if check_container_db; then
            DB_TYPE="container"
        elif check_local_db; then
            DB_TYPE="local"
        else
            echo -e "${YELLOW}⚠️  No database found. Starting with container...${NC}"
            check_container_db || exit 1
            DB_TYPE="container"
        fi
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Database setup complete!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Run tests with: ./scripts/run-tests.sh"
echo "2. Integration tests will connect to: postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo -e "${YELLOW}To stop database (container):${NC}"
if [ "$CONTAINER_CMD" ]; then
    echo "$CONTAINER_CMD stop trading-agent-postgres-test"
fi
