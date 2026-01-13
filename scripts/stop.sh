#!/bin/bash
# =============================================================================
# GitHub Runner - Stop Script
# =============================================================================
# Stop the GitHub runner stack
# Usage: ./scripts/stop.sh
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${BLUE}"
echo "============================================================================="
echo "  GitHub Runner - Stopping"
echo "============================================================================="
echo -e "${NC}"

# Check if any containers are running
if ! docker compose ps --quiet 2>/dev/null | grep -q .; then
    echo -e "${YELLOW}No containers running.${NC}"
    exit 0
fi

# Show what will be stopped
echo -e "${BLUE}Stopping containers:${NC}"
docker compose ps --format "table {{.Name}}\t{{.Status}}"

echo ""

# Stop services
docker compose down

echo ""
echo -e "${GREEN}Stopped successfully!${NC}"
echo ""
echo -e "${YELLOW}Note: Volumes preserved. Use ./scripts/cleanup.sh --full to remove.${NC}"
echo ""
