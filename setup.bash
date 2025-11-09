#!/bin/bash

# Setup script for Vibex project
# This script performs the required setup tasks

set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting Vibex setup..."

# Task 1: Copy backend/.env.example to backend/.env
if [ -f "backend/.env.example" ]; then
    cp backend/.env.example backend/.env
    echo "✓ Copied backend/.env.example to backend/.env"
else
    echo "✗ Error: backend/.env.example not found"
    exit 1
fi

# Task 2: Copy backend/.env.example to backend/.env.testing and update DATABASE_URL
if [ -f "backend/.env.example" ]; then
    cp backend/.env.example backend/.env.testing
    sed -i 's/DATABASE_URL=postgresql:\/\/trading_user:trading_password@postgres:5432\/trading_db/DATABASE_URL=postgresql:\/\/trading_user:trading_password@localhost:5432\/trading_db/' backend/.env.testing
    echo "✓ Copied backend/.env.example to backend/.env.testing and updated DATABASE_URL"
else
    echo "✗ Error: backend/.env.example not found"
    exit 1
fi

# Task 3: Copy backend/compose.override.yml.example to backend/compose.override.yml
if [ -f "backend/compose.override.yml.example" ]; then
    cp backend/compose.override.yml.example backend/compose.override.yml
    echo "✓ Copied backend/compose.override.yml.example to backend/compose.override.yml"
else
    echo "✗ Error: backend/compose.override.yml.example not found"
    exit 1
fi

echo "Setup completed successfully!"

set +x; . /opt/environment_summary.sh
