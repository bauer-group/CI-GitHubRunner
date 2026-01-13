#!/bin/bash
# =============================================================================
# GitHub Runner - Status Script
# =============================================================================
# Show status of the GitHub runner stack
# Usage: ./scripts/status.sh
# =============================================================================

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${BLUE}"
echo "============================================================================="
echo "  GitHub Runner - Status"
echo "============================================================================="
echo -e "${NC}"

# Check if any containers exist
if ! docker compose ps --quiet 2>/dev/null | grep -q .; then
    echo -e "${YELLOW}No containers running.${NC}"
    echo ""
    echo "Start with: ./scripts/start.sh"
    exit 0
fi

# Container status
echo -e "${BLUE}Containers:${NC}"
docker compose ps

echo ""

# Count runners
RUNNER_COUNT=$(docker compose ps --format "{{.Name}}" 2>/dev/null | grep -c "agent" || echo "0")
DIND_STATUS=$(docker compose ps --format "{{.Status}}" docker-in-docker 2>/dev/null | head -1 || echo "not running")

echo -e "${BLUE}Summary:${NC}"
echo "  DinD Status:    $DIND_STATUS"
echo "  Runner Count:   $RUNNER_COUNT"

echo ""

# Health check
echo -e "${BLUE}Health:${NC}"
docker compose ps --format "  {{.Name}}: {{.Status}}"

echo ""

# Resource usage
echo -e "${BLUE}Resource Usage:${NC}"
docker stats --no-stream --format "  {{.Name}}: CPU {{.CPUPerc}}, Mem {{.MemUsage}}" $(docker compose ps -q 2>/dev/null) 2>/dev/null || echo "  Unable to get stats"

echo ""

# GitHub link
if [ -f ".env" ]; then
    REPO_URL=$(grep "^REPO_URL=" .env 2>/dev/null | cut -d'=' -f2)
    if [ -n "$REPO_URL" ]; then
        echo -e "${GREEN}Verify in GitHub:${NC}"
        echo "  ${REPO_URL}/settings/actions/runners"
        echo ""
    fi
fi
