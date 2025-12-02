#!/usr/bin/env bash
# Deployment script for User Event Email Worker (shared scripts dir)
# Usage: ./scripts/user-event-email-deploy.sh

set -e

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPTS_DIR/.." && pwd)"
SERVICE_DIR="$REPO_ROOT/services/user-event-email"

echo "=========================================="
echo "User Event Email Worker - Deployment"
echo "=========================================="

GIT_ROOT="$REPO_ROOT"
while [ "$GIT_ROOT" != "/" ] && [ ! -d "$GIT_ROOT/.git" ]; do
    GIT_ROOT="$(dirname "$GIT_ROOT")"
done

if [ -d "$GIT_ROOT/.git" ]; then
    echo ""
    echo "Step 1: Pulling latest code from $GIT_ROOT..."
    cd "$GIT_ROOT"
    git pull
    echo "✓ Code updated"
else
    echo ""
    echo "⚠️  Not a git repository, skipping git pull"
fi

echo ""
echo "Step 2: Rebuilding Docker image..."
docker build -t ozl-user-event-email:prod "$SERVICE_DIR"
echo "✓ Docker image rebuilt"

echo ""
echo "Step 3: Verifying .env file exists..."
if [ ! -f "$SERVICE_DIR/.env" ]; then
    echo "⚠️  WARNING: .env file not found at $SERVICE_DIR/.env!"
    echo "   Make sure your environment variables are set before running the worker."
else
    echo "✓ .env file found"
fi

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "To run the worker:"
echo "  ./scripts/user-event-email-run.sh"
echo ""


