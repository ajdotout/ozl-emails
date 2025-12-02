#!/usr/bin/env bash
# VM Setup Script for User Event Email Worker (shared scripts dir)
# Usage: ./scripts/user-event-email-setup-vm.sh

set -e

echo "=========================================="
echo "User Event Email Worker - VM Setup"
echo "=========================================="

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$REPO_ROOT/services/user-event-email"

cd "$SERVICE_DIR"

if [ "$EUID" -eq 0 ]; then
   echo "Please don't run this script as root. It will use sudo when needed."
   exit 1
fi

echo ""
echo "Step 1: Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y docker.io git

echo ""
echo "Step 2: Setting up Docker..."
sudo usermod -aG docker "$USER"
echo "✓ Docker installed. You may need to log out and back in for group changes to take effect."

echo ""
echo "Step 3: Setting timezone to Pacific Time..."
sudo timedatectl set-timezone America/Los_Angeles
echo "✓ Timezone set to America/Los_Angeles"

echo ""
echo "Step 4: Creating log file..."
sudo mkdir -p /var/log
sudo touch /var/log/user-event-email.log
sudo chown "$USER:$USER" /var/log/user-event-email.log
echo "✓ Log file created at /var/log/user-event-email.log"

echo ""
echo "Step 5: Building Docker image..."
if ! docker info > /dev/null 2>&1; then
    echo "⚠️  Docker daemon not accessible. You may need to:"
    echo "   1. Log out and back in (to pick up docker group)"
    echo "   2. Or run: newgrp docker"
    echo "   3. Then run this script again or manually: docker build -t ozl-user-event-email:prod ."
    exit 1
fi

docker build -t ozl-user-event-email:prod "$SERVICE_DIR"
echo "✓ Docker image built successfully"

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "Required .env file in: $SERVICE_DIR/.env"
echo "  - SUPABASE_URL"
echo "  - SUPABASE_SERVICE_ROLE_KEY"
echo "  - SPARKPOST_API_KEY (optional for now; sends are logged)"
echo "  - SPARKPOST_SENDER   (optional)"
echo "  - LOG_LEVEL          (optional, e.g. INFO)"
echo ""
echo "To start the worker:"
echo "  ./scripts/user-event-email-run.sh"
echo ""


