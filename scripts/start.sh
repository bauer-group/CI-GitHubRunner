#!/bin/bash
# =============================================================================
# GitHub Runner - Start Script
# =============================================================================
# Start the GitHub runner stack
# Usage: ./scripts/start.sh [NUMBER_OF_RUNNERS]
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Scale (default 1)
SCALE=${1:-1}

cd "$PROJECT_ROOT"

echo -e "${BLUE}"
echo "============================================================================="
echo "  GitHub Runner - Starting"
echo "============================================================================="
echo -e "${NC}"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Run ./scripts/setup-env.sh first."
    exit 1
fi

# Start services
echo -e "${BLUE}Starting DinD and $SCALE runner(s)...${NC}"
docker compose up -d --scale runner="$SCALE"

echo ""
echo -e "${GREEN}Started successfully!${NC}"
echo ""

# Show status
docker compose ps

echo ""
REPO_URL=$(grep "^REPO_URL=" .env 2>/dev/null | cut -d'=' -f2 || echo "https://github.com/bauer-group")
echo -e "${GREEN}Verify in GitHub:${NC}"
echo "  ${REPO_URL}/settings/actions/runners"
echo ""
