#!/bin/bash
# =============================================================================
# Development Tools Container Launcher (Linux/macOS)
# Starts an interactive Linux container with all required tools
# =============================================================================

set -euo pipefail

# Configuration - get project dir (parent of tools folder)
TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$TOOLS_DIR")"
IMAGE_NAME="github-runner-tools"
CONTAINER_NAME="github-runner-tools-shell"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}[ERROR] Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Parse arguments
BUILD=false
SCRIPT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --build|-b)
            BUILD=true
            shift
            ;;
        --script|-s)
            SCRIPT="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --build, -b          Rebuild the tools container"
            echo "  --script, -s CMD     Run a script directly without interactive shell"
            echo "  --help, -h           Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                   Start interactive shell"
            echo "  $0 --build           Rebuild and start interactive shell"
            echo "  $0 -s './scripts/setup-env.sh'"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Build if requested or image doesn't exist
if [[ "$BUILD" == "true" ]]; then
    echo -e "${CYAN}[INFO] Rebuilding tools container...${NC}"
    docker build -t "$IMAGE_NAME" "$TOOLS_DIR"
    echo ""
elif ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
    echo -e "${CYAN}[INFO] Tools image not found. Building...${NC}"
    docker build -t "$IMAGE_NAME" "$TOOLS_DIR"
    echo ""
fi

# If a script is specified, run it directly
if [[ -n "$SCRIPT" ]]; then
    echo -e "${CYAN}[INFO] Running: $SCRIPT${NC}"
    docker run --rm \
        -v "$PROJECT_DIR:/workspace" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -w /workspace \
        "$IMAGE_NAME" \
        /bin/bash -c "$SCRIPT"
    exit $?
fi

# Interactive mode
echo ""
echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN} GitHub Runner - Development Tools${NC}"
echo -e "${GREEN}===========================================${NC}"
echo ""
echo "Available scripts:"
echo -e "  ${YELLOW}./scripts/deploy.sh${NC}      - Deploy/update on host"
echo -e "  ${YELLOW}./scripts/setup-env.sh${NC}   - Interactive environment setup"
echo -e "  ${YELLOW}./scripts/start.sh [N]${NC}   - Start N runners (default: 1)"
echo -e "  ${YELLOW}./scripts/stop.sh${NC}        - Stop all runners"
echo -e "  ${YELLOW}./scripts/status.sh${NC}      - Show status and resources"
echo -e "  ${YELLOW}./scripts/scale.sh N${NC}     - Scale to N runners"
echo -e "  ${YELLOW}./scripts/cleanup.sh${NC}     - Cleanup Docker resources"
echo ""
echo "Type 'exit' to leave the container."
echo -e "${GREEN}===========================================${NC}"
echo ""

# Run interactive container
docker run -it --rm \
    --name "$CONTAINER_NAME" \
    -v "$PROJECT_DIR:/workspace" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -w /workspace \
    "$IMAGE_NAME"
