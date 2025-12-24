#!/bin/bash

# Setup script for api Docker container deployment on GCP VM
# This script builds and runs the Docker container with proper configuration

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="api-service"
CONTAINER_NAME="api-service"
ENV_FILE=".env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_info "Docker is installed: $(docker --version)"
}

# Check if .env file exists
check_env_file() {
    if [ ! -f "$SCRIPT_DIR/$ENV_FILE" ]; then
        print_warn ".env file not found at $SCRIPT_DIR/$ENV_FILE"
        print_warn "The container will need environment variables passed directly or via GCP Secret Manager"
        return 1
    else
        print_info ".env file found"
        return 0
    fi
}

# Stop and remove existing container if it exists
cleanup_existing_container() {
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_info "Stopping existing container: $CONTAINER_NAME"
        docker stop "$CONTAINER_NAME" || true
        print_info "Removing existing container: $CONTAINER_NAME"
        docker rm "$CONTAINER_NAME" || true
    fi
}

# Build Docker image
build_image() {
    print_info "Building Docker image: $IMAGE_NAME"
    cd "$SCRIPT_DIR"
    docker build -t "$IMAGE_NAME:latest" .
    print_info "Docker image built successfully"
}

# Run Docker container
run_container() {
    print_info "Starting Docker container: $CONTAINER_NAME"

    cd "$SCRIPT_DIR"

    # Base docker run command
    DOCKER_RUN_CMD="docker run -d \
        --name $CONTAINER_NAME \
        --restart unless-stopped \
        --log-driver json-file \
        --log-opt max-size=10m \
        --log-opt max-file=3 \
        -p 8000:8000"

    # Add environment file if it exists
    if [ -f "$SCRIPT_DIR/$ENV_FILE" ]; then
        DOCKER_RUN_CMD="$DOCKER_RUN_CMD --env-file $SCRIPT_DIR/$ENV_FILE"
        print_info "Using .env file for environment variables"
    else
        print_warn "No .env file found. Make sure environment variables are set via GCP Secret Manager or passed directly."
    fi

    # Add the image name
    DOCKER_RUN_CMD="$DOCKER_RUN_CMD $IMAGE_NAME:latest"

    # Execute the command
    eval $DOCKER_RUN_CMD

    print_info "Container started successfully"
}

# Show container status
show_status() {
    echo ""
    print_info "Container status:"
    docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    echo ""
    print_info "API will be available at: http://localhost:8000"
    print_info "Health check endpoint: http://localhost:8000/health"

    echo ""
    print_info "To view logs, run:"
    echo "  docker logs -f $CONTAINER_NAME"

    echo ""
    print_info "To stop the container, run:"
    echo "  docker stop $CONTAINER_NAME"

    echo ""
    print_info "To restart the container, run:"
    echo "  docker restart $CONTAINER_NAME"
}

# Main execution
main() {
    print_info "Starting api-service setup..."

    check_docker
    check_env_file

    # Ask for confirmation if container exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_warn "Container $CONTAINER_NAME already exists"
        read -p "Do you want to rebuild and restart it? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Aborted by user"
            exit 0
        fi
        cleanup_existing_container
    fi

    build_image
    run_container
    show_status

    print_info "Setup completed successfully!"
}

# Run main function
main
