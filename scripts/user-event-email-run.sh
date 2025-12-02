#!/usr/bin/env bash
# Run script for User Event Email Worker (shared scripts dir)
# Usage: ./scripts/user-event-email-run.sh

set -e

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPTS_DIR/.." && pwd)"
SERVICE_DIR="$REPO_ROOT/services/user-event-email"

LOG_FILE="/var/log/user-event-email.log"

if [ ! -f "$SERVICE_DIR/.env" ]; then
  echo "ERROR: .env file not found in $SERVICE_DIR"
  exit 1
fi

echo "Starting user-event-email worker..."
docker run --rm \
  --env-file "$SERVICE_DIR/.env" \
  --name ozl-user-event-email \
  -v "$LOG_FILE":"$LOG_FILE" \
  ozl-user-event-email:prod \
  >> "$LOG_FILE" 2>&1


