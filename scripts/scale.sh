#!/bin/bash
# =============================================================================
# GitHub Runner - Scale Script
# =============================================================================
# Scale the number of runner instances up or down
# Usage: ./scripts/scale.sh [NUMBER]
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default scale
SCALE=${1:-1}

# Help
if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    echo "Usage: $0 [NUMBER]"
    echo ""
    echo "Scale the number of GitHub runner instances."
    echo ""
    echo "Arguments:"
    echo "  NUMBER    Number of runner instances (default: 1)"
    echo ""
    echo "Examples:"
    echo "  $0        Start 1 runner (default)"
    echo "  $0 4      Scale to 4 runners"
    echo "  $0 8      Scale to 8 runners"
    echo "  $0 1      Scale down to 1 runner"
    echo ""
    echo "Current status:"
    cd "$PROJECT_ROOT"
    docker compose ps 2>/dev/null || echo "  No containers running"
    exit 0
fi

# Validate input
if ! [[ "$SCALE" =~ ^[0-9]+$ ]] || [[ "$SCALE" -lt 1 ]]; then
    echo -e "${RED}Error: Please provide a valid number >= 1${NC}"
    exit 1
fi

cd "$PROJECT_ROOT"

echo -e "${BLUE}"
echo "============================================================================="
echo "  GitHub Runner - Scaling to $SCALE instance(s)"
echo "============================================================================="
echo -e "${NC}"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Run ./scripts/setup-env.sh first."
    exit 1
fi

# Scale runners
echo -e "${BLUE}Scaling runners...${NC}"
docker compose up -d --scale runner="$SCALE"

echo ""
echo -e "${GREEN}Done!${NC}"
echo ""

# Show status
echo -e "${BLUE}Current status:${NC}"
docker compose ps

echo ""
echo -e "${BLUE}Runner containers:${NC}"
docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep -E "(NAME|runner)"

echo ""
echo -e "${GREEN}Verify in GitHub:${NC}"
# Try to get REPO_URL from .env
REPO_URL=$(grep "^REPO_URL=" .env 2>/dev/null | cut -d'=' -f2 || echo "https://github.com/bauer-group")
echo "  ${REPO_URL}/settings/actions/runners"
echo ""
