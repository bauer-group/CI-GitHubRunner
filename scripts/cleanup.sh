#!/bin/bash
# =============================================================================
# GitHub Runner - Cleanup Script
# =============================================================================
# Cleans up Docker resources from the runner environment
# Use this to reclaim disk space and remove stale containers
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

echo -e "${BLUE}"
echo "============================================================================="
echo "  GitHub Runner - Cleanup"
echo "============================================================================="
echo -e "${NC}"

# Parse arguments
FULL_CLEANUP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --full)
            FULL_CLEANUP=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --full     Full cleanup including volumes and images"
            echo "  -h, --help Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

cd "$PROJECT_ROOT"

# Stop running containers
echo -e "${BLUE}Stopping containers...${NC}"
docker compose down --remove-orphans 2>/dev/null || true

# Clean up runner work directories
echo -e "${BLUE}Cleaning up runner work directories...${NC}"
docker volume ls -q | grep -E "runner.*work" | xargs -r docker volume rm 2>/dev/null || true

if [ "$FULL_CLEANUP" = true ]; then
    echo ""
    echo -e "${YELLOW}Performing full cleanup...${NC}"

    # Remove all project volumes
    echo -e "${BLUE}Removing all project volumes...${NC}"
    docker compose down -v 2>/dev/null || true

    # Prune DinD images (these can get large)
    echo -e "${BLUE}Pruning unused Docker images...${NC}"
    docker image prune -af 2>/dev/null || true

    # Prune build cache
    echo -e "${BLUE}Pruning build cache...${NC}"
    docker builder prune -af 2>/dev/null || true

    echo ""
    echo -e "${GREEN}Full cleanup completed!${NC}"
else
    echo ""
    echo -e "${GREEN}Basic cleanup completed!${NC}"
    echo ""
    echo "Tip: Run with --full for complete cleanup including volumes and images"
fi

# Show disk usage
echo ""
echo -e "${BLUE}Current Docker disk usage:${NC}"
docker system df 2>/dev/null || true
