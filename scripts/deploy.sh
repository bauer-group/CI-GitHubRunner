#!/bin/bash
# =============================================================================
# GitHub Runner - Deployment Script
# =============================================================================
# Deploys or updates the GitHub Runner on a host system
# Usage: ./scripts/deploy.sh [--init]
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

# Parse arguments
INIT_MODE=false
if [[ "$1" == "--init" ]] || [[ "$1" == "-i" ]]; then
    INIT_MODE=true
fi

if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Deploy or update the GitHub Runner on this host."
    echo ""
    echo "Options:"
    echo "  --init, -i    Initial deployment (configure git, pull, setup)"
    echo "  --help, -h    Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 --init     First-time setup on a new host"
    echo "  $0            Update existing deployment"
    exit 0
fi

cd "$PROJECT_ROOT"

echo -e "${BLUE}"
echo "============================================================================="
echo "  GitHub Runner - Deployment"
echo "============================================================================="
echo -e "${NC}"

# =============================================================================
# Git Configuration
# =============================================================================
echo -e "${BLUE}Configuring git...${NC}"

# Disable fileMode tracking (important for Windows/Linux compatibility)
git config core.fileMode false

# Set safe directory (for running as different user)
git config --global --add safe.directory "$PROJECT_ROOT" 2>/dev/null || true

echo -e "${GREEN}Git configured${NC}"

# =============================================================================
# Pull Latest Changes
# =============================================================================
echo ""
echo -e "${BLUE}Pulling latest changes...${NC}"

# Stash any local changes
if ! git diff --quiet 2>/dev/null; then
    echo -e "${YELLOW}Stashing local changes...${NC}"
    git stash
    STASHED=true
else
    STASHED=false
fi

# Pull from remote
git pull --ff-only || {
    echo -e "${YELLOW}Fast-forward pull failed, trying merge...${NC}"
    git pull
}

# Restore stashed changes if any
if [ "$STASHED" = true ]; then
    echo -e "${YELLOW}Restoring stashed changes...${NC}"
    git stash pop || {
        echo -e "${RED}Warning: Could not restore stashed changes automatically.${NC}"
        echo "Run 'git stash pop' manually to restore them."
    }
fi

echo -e "${GREEN}Repository updated${NC}"

# =============================================================================
# Make Scripts Executable
# =============================================================================
echo ""
echo -e "${BLUE}Setting script permissions...${NC}"

chmod +x scripts/*.sh 2>/dev/null || true
chmod +x tools/*.sh 2>/dev/null || true

echo -e "${GREEN}Scripts are now executable${NC}"

# =============================================================================
# Initial Setup (only with --init)
# =============================================================================
if [ "$INIT_MODE" = true ]; then
    echo ""
    echo -e "${BLUE}Running initial setup...${NC}"

    # Check if .env exists
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        echo ""
        echo -e "${YELLOW}No .env file found. Starting interactive setup...${NC}"
        "$SCRIPT_DIR/setup-env.sh"
    else
        echo -e "${GREEN}.env file already exists${NC}"
        read -p "Do you want to reconfigure? (y/N): " reconfigure
        if [[ "$reconfigure" =~ ^[Yy]$ ]]; then
            "$SCRIPT_DIR/setup-env.sh"
        fi
    fi
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo -e "${GREEN}=============================================================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}=============================================================================${NC}"
echo ""
echo "Current version:"
git log -1 --format="  Commit: %h - %s (%cr)"
echo ""

if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Next steps:"
    echo "  ./scripts/start.sh       - Start runners"
    echo "  ./scripts/start.sh 4     - Start 4 runners"
    echo "  ./scripts/status.sh      - Check status"
else
    echo -e "${YELLOW}Configuration required:${NC}"
    echo "  ./scripts/deploy.sh --init    - Run initial setup"
    echo "  OR"
    echo "  ./scripts/setup-env.sh        - Configure environment"
fi
echo ""
