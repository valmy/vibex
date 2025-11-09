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
    sed -i 's/ENVIRONMENT=development/ENVIRONMENT=testing/' backend/.env.testing
    echo "✓ Copied backend/.env.example to backend/.env.testing and updated DATABASE_URL"
    echo "✓ Updated ENVIRONMENT to 'testing' in backend/.env.testing"
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

# Setup Python virtual environment with uv
if [ -d "backend" ]; then
    echo "Setting up Python virtual environment..."
    cd backend && uv sync
    echo "✓ Python virtual environment set up successfully"

    echo "Installing development and test dependencies..."
    uv pip install -e .[dev,test]
    echo "✓ Development and test dependencies installed"

    # At this point we're in the backend directory
    # Pull and list Docker images
    if [ -f "podman-compose.yml" ]; then
        echo "Pulling Docker images..."
        docker compose -f podman-compose.yml pull postgres redis
        echo "✓ Docker images pulled successfully"

        echo "Listing Docker images..."
        docker images
        echo "✓ Docker images listed successfully"
    else
        echo "⚠ Warning: docker-compose.yml or compose.yml not found in backend, skipping Docker operations"
    fi

    # Go back to the project root
    cd ..
else
    echo "✗ Error: backend directory not found"
    exit 1
fi

# Install podman-compose using pipx
echo "Installing podman-compose..."
if command -v pipx &> /dev/null; then
    pipx install podman-compose
    echo "✓ podman-compose installed successfully"
else
    echo "✗ Error: pipx is not installed. Please install pipx first."
    exit 1
fi


# Return to project root directory
cd ..

echo "Setup completed successfully!"

# set +x; . /opt/environment_summary.sh
