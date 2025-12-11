#!/bin/bash

# Production setup script for campaign-runner Docker container on GCP VM
# This version supports GCP Secret Manager for environment variables

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="campaign-runner"
CONTAINER_NAME="campaign-runner"
ENV_FILE=".env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRET_MANAGER_ENABLED=false
GCP_PROJECT_ID=""
SECRET_NAME="campaign-runner-env"

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

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --use-secret-manager)
            SECRET_MANAGER_ENABLED=true
            shift
            ;;
        --project-id)
            GCP_PROJECT_ID="$2"
            shift 2
            ;;
        --secret-name)
            SECRET_NAME="$2"
            shift 2
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --use-secret-manager    Use GCP Secret Manager for environment variables"
            echo "  --project-id ID         GCP Project ID (required with --use-secret-manager)"
            echo "  --secret-name NAME      Secret name in Secret Manager (default: campaign-runner-env)"
            echo "  --env-file FILE         Path to .env file (default: .env)"
            echo "  --help                  Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_info "Docker is installed: $(docker --version)"
}

# Check if gcloud CLI is installed (for Secret Manager)
check_gcloud() {
    if [ "$SECRET_MANAGER_ENABLED" = true ]; then
        if ! command -v gcloud &> /dev/null; then
            print_error "gcloud CLI is not installed. Required for Secret Manager."
            exit 1
        fi
        
        if [ -z "$GCP_PROJECT_ID" ]; then
            print_error "GCP Project ID is required when using Secret Manager. Use --project-id"
            exit 1
        fi
        
        print_info "gcloud CLI is installed: $(gcloud --version | head -n 1)"
        print_info "Using GCP Project: $GCP_PROJECT_ID"
        print_info "Using Secret: $SECRET_NAME"
    fi
}

# Fetch secrets from GCP Secret Manager
fetch_secrets() {
    if [ "$SECRET_MANAGER_ENABLED" = true ]; then
        print_step "Fetching secrets from GCP Secret Manager..."
        
        # Create temporary env file from secret
        TEMP_ENV_FILE=$(mktemp)
        
        if gcloud secrets versions access latest --secret="$SECRET_NAME" --project="$GCP_PROJECT_ID" > "$TEMP_ENV_FILE" 2>/dev/null; then
            print_info "Secrets fetched successfully from Secret Manager"
            echo "$TEMP_ENV_FILE"
        else
            print_error "Failed to fetch secrets from Secret Manager"
            rm -f "$TEMP_ENV_FILE"
            exit 1
        fi
    else
        echo ""
    fi
}

# Check if .env file exists
check_env_file() {
    if [ "$SECRET_MANAGER_ENABLED" = false ]; then
        if [ ! -f "$SCRIPT_DIR/$ENV_FILE" ]; then
            print_error ".env file not found at $SCRIPT_DIR/$ENV_FILE"
            print_error "Either create a .env file or use --use-secret-manager"
            exit 1
        else
            print_info ".env file found: $SCRIPT_DIR/$ENV_FILE"
        fi
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
    print_step "Building Docker image: $IMAGE_NAME"
    cd "$SCRIPT_DIR"
    docker build -t "$IMAGE_NAME:latest" .
    print_info "Docker image built successfully"
}

# Run Docker container
run_container() {
    print_step "Starting Docker container: $CONTAINER_NAME"
    
    cd "$SCRIPT_DIR"
    
    # Base docker run command
    DOCKER_RUN_CMD="docker run -d \
        --name $CONTAINER_NAME \
        --restart unless-stopped \
        --log-driver json-file \
        --log-opt max-size=10m \
        --log-opt max-file=3"
    
    # Handle environment variables
    if [ "$SECRET_MANAGER_ENABLED" = true ]; then
        TEMP_ENV_FILE=$(fetch_secrets)
        if [ -n "$TEMP_ENV_FILE" ]; then
            DOCKER_RUN_CMD="$DOCKER_RUN_CMD --env-file $TEMP_ENV_FILE"
            print_info "Using GCP Secret Manager for environment variables"
        fi
    elif [ -f "$SCRIPT_DIR/$ENV_FILE" ]; then
        DOCKER_RUN_CMD="$DOCKER_RUN_CMD --env-file $SCRIPT_DIR/$ENV_FILE"
        print_info "Using .env file for environment variables"
    fi
    
    # Add the image name
    DOCKER_RUN_CMD="$DOCKER_RUN_CMD $IMAGE_NAME:latest"
    
    # Execute the command
    eval $DOCKER_RUN_CMD
    
    # Clean up temporary env file if created
    if [ -n "$TEMP_ENV_FILE" ] && [ -f "$TEMP_ENV_FILE" ]; then
        rm -f "$TEMP_ENV_FILE"
    fi
    
    print_info "Container started successfully"
}

# Show container status
show_status() {
    echo ""
    print_step "Container status:"
    docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    print_info "Useful commands:"
    echo "  View logs:        docker logs -f $CONTAINER_NAME"
    echo "  Stop container:   docker stop $CONTAINER_NAME"
    echo "  Start container:  docker start $CONTAINER_NAME"
    echo "  Restart container: docker restart $CONTAINER_NAME"
    echo "  View status:      docker ps --filter name=$CONTAINER_NAME"
}

# Main execution
main() {
    print_info "Starting campaign-runner setup for GCP VM..."
    echo ""
    
    check_docker
    
    if [ "$SECRET_MANAGER_ENABLED" = true ]; then
        check_gcloud
    else
        check_env_file
    fi
    
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
    
    echo ""
    print_info "Setup completed successfully!"
    print_info "The container is configured to restart automatically unless stopped manually."
}

# Run main function
main
