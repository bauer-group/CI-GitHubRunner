#!/bin/bash
# =============================================================================
# GitHub Runner - Unified Management Script
# =============================================================================
# Single entry point for all runner operations
# Usage: ./runner.sh <command> [options]
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo -e "${BLUE}"
    echo "============================================================================="
    echo "  GitHub Runner - $1"
    echo "============================================================================="
    echo -e "${NC}"
}

check_env() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        echo -e "${RED}Error: .env file not found!${NC}"
        echo "Run ./scripts/setup-env.sh first."
        exit 1
    fi
}

get_github_url() {
    if [ -f "$PROJECT_ROOT/.env" ]; then
        local org_name=$(grep "^ORG_NAME=" "$PROJECT_ROOT/.env" 2>/dev/null | cut -d'=' -f2)
        local repo_url=$(grep "^REPO_URL=" "$PROJECT_ROOT/.env" 2>/dev/null | cut -d'=' -f2)
        if [ -n "$org_name" ]; then
            echo "https://github.com/${org_name}/settings/actions/runners"
        elif [ -n "$repo_url" ]; then
            echo "${repo_url}/settings/actions/runners"
        else
            echo "https://github.com/settings/actions/runners"
        fi
    fi
}

# Get docker compose command with appropriate config files
get_compose_cmd() {
    # Check if COMPOSE_FILE is already set (user override)
    if [ -n "${COMPOSE_FILE:-}" ]; then
        echo "docker compose"
        return
    fi

    # Check if GitHub App auth is configured
    if [ -f "$PROJECT_ROOT/.env" ]; then
        local app_id=$(grep "^APP_ID=" "$PROJECT_ROOT/.env" 2>/dev/null | cut -d'=' -f2)
        local pem_file=$(grep "^APP_PRIVATE_KEY_FILE=" "$PROJECT_ROOT/.env" 2>/dev/null | cut -d'=' -f2)

        # If APP_ID is set and PEM file exists, use app-auth override
        if [ -n "$app_id" ] && [ -n "$pem_file" ]; then
            # Handle relative paths (./github-app.pem) and absolute paths
            local pem_path="$pem_file"
            [[ "$pem_file" == ./* ]] && pem_path="$PROJECT_ROOT/${pem_file:2}"

            if [ -f "$pem_path" ]; then
                echo "docker compose -f docker-compose.yml -f docker-compose.app-auth.yml"
                return
            else
                echo -e "${YELLOW}Warning: APP_ID set but PEM file not found: $pem_file${NC}" >&2
                echo -e "${YELLOW}Falling back to ACCESS_TOKEN authentication${NC}" >&2
            fi
        fi
    fi

    # Default: just docker compose
    echo "docker compose"
}

# =============================================================================
# Commands
# =============================================================================

cmd_start() {
    local scale=${1:-1}
    local compose_cmd=$(get_compose_cmd)

    print_header "Starting"
    check_env

    echo -e "${BLUE}Starting DinD and $scale runner(s)...${NC}"
    $compose_cmd up -d --scale agent="$scale"

    echo ""
    echo -e "${GREEN}Started successfully!${NC}"
    echo ""
    $compose_cmd ps
    echo ""
    echo -e "${GREEN}Verify in GitHub:${NC}"
    echo "  $(get_github_url)"
    echo ""
}

cmd_stop() {
    local compose_cmd=$(get_compose_cmd)

    print_header "Stopping"

    cd "$PROJECT_ROOT"

    if ! $compose_cmd ps --quiet 2>/dev/null | grep -q .; then
        echo -e "${YELLOW}No containers running.${NC}"
        return 0
    fi

    echo -e "${BLUE}Stopping containers:${NC}"
    $compose_cmd ps --format "table {{.Name}}\t{{.Status}}"
    echo ""

    $compose_cmd down

    echo ""
    echo -e "${GREEN}Stopped successfully!${NC}"
    echo ""
    echo -e "${YELLOW}Note: Volumes preserved. Use './runner.sh cleanup --full' to remove.${NC}"
    echo ""
}

cmd_status() {
    local compose_cmd=$(get_compose_cmd)

    print_header "Status"

    cd "$PROJECT_ROOT"

    if ! $compose_cmd ps --quiet 2>/dev/null | grep -q .; then
        echo -e "${YELLOW}No containers running.${NC}"
        echo ""
        echo "Start with: ./runner.sh start"
        return 0
    fi

    echo -e "${BLUE}Containers:${NC}"
    $compose_cmd ps
    echo ""

    local runner_count=$($compose_cmd ps --format "{{.Name}}" 2>/dev/null | grep -c "agent" || echo "0")
    local dind_status=$($compose_cmd ps --format "{{.Status}}" docker-in-docker 2>/dev/null | head -1 || echo "not running")

    echo -e "${BLUE}Summary:${NC}"
    echo "  DinD Status:    $dind_status"
    echo "  Runner Count:   $runner_count"
    echo ""

    echo -e "${BLUE}Resource Usage:${NC}"
    docker stats --no-stream --format "  {{.Name}}: CPU {{.CPUPerc}}, Mem {{.MemUsage}}" $($compose_cmd ps -q 2>/dev/null) 2>/dev/null || echo "  Unable to get stats"
    echo ""

    echo -e "${GREEN}Verify in GitHub:${NC}"
    echo "  $(get_github_url)"
    echo ""
}

cmd_scale() {
    local scale=${1:-}
    local compose_cmd=$(get_compose_cmd)

    if [ -z "$scale" ]; then
        echo -e "${RED}Error: Please specify number of runners${NC}"
        echo "Usage: ./runner.sh scale <number>"
        exit 1
    fi

    if ! [[ "$scale" =~ ^[0-9]+$ ]] || [[ "$scale" -lt 1 ]]; then
        echo -e "${RED}Error: Please provide a valid number >= 1${NC}"
        exit 1
    fi

    print_header "Scaling to $scale instance(s)"
    check_env

    echo -e "${BLUE}Scaling runners...${NC}"
    $compose_cmd up -d --scale agent="$scale"

    echo ""
    echo -e "${GREEN}Done!${NC}"
    echo ""

    echo -e "${BLUE}Current status:${NC}"
    $compose_cmd ps --format "table {{.Name}}\t{{.Status}}" | grep -E "(NAME|agent)"
    echo ""

    echo -e "${GREEN}Verify in GitHub:${NC}"
    echo "  $(get_github_url)"
    echo ""
}

cmd_cleanup() {
    local full_cleanup=false
    local compose_cmd=$(get_compose_cmd)

    while [[ $# -gt 0 ]]; do
        case $1 in
            --full|-f)
                full_cleanup=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    print_header "Cleanup"

    cd "$PROJECT_ROOT"

    echo -e "${BLUE}Stopping containers...${NC}"
    $compose_cmd down --remove-orphans 2>/dev/null || true

    echo -e "${BLUE}Cleaning up runner work directories...${NC}"
    docker volume ls -q | grep -E "runner.*work" | xargs -r docker volume rm 2>/dev/null || true

    if [ "$full_cleanup" = true ]; then
        echo ""
        echo -e "${YELLOW}Performing full cleanup...${NC}"

        echo -e "${BLUE}Removing all project volumes...${NC}"
        $compose_cmd down -v 2>/dev/null || true

        echo -e "${BLUE}Pruning unused Docker images...${NC}"
        docker image prune -af 2>/dev/null || true

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

    echo ""
    echo -e "${BLUE}Current Docker disk usage:${NC}"
    docker system df 2>/dev/null || true
}

cmd_deploy() {
    local init_mode=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --init|-i)
                init_mode=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    print_header "Deployment"

    cd "$PROJECT_ROOT"

    # Git Configuration
    echo -e "${BLUE}Configuring git...${NC}"
    git config core.fileMode false
    git config --global --add safe.directory "$PROJECT_ROOT" 2>/dev/null || true
    echo -e "${GREEN}Git configured${NC}"

    # Pull Latest Changes
    echo ""
    echo -e "${BLUE}Pulling latest changes...${NC}"

    local stashed=false
    if ! git diff --quiet 2>/dev/null; then
        echo -e "${YELLOW}Stashing local changes...${NC}"
        git stash
        stashed=true
    fi

    git pull --ff-only || {
        echo -e "${YELLOW}Fast-forward pull failed, trying merge...${NC}"
        git pull
    }

    if [ "$stashed" = true ]; then
        echo -e "${YELLOW}Restoring stashed changes...${NC}"
        git stash pop || {
            echo -e "${RED}Warning: Could not restore stashed changes automatically.${NC}"
            echo "Run 'git stash pop' manually to restore them."
        }
    fi

    echo -e "${GREEN}Repository updated${NC}"

    # Make Scripts Executable
    echo ""
    echo -e "${BLUE}Setting script permissions...${NC}"
    chmod +x runner.sh 2>/dev/null || true
    chmod +x scripts/*.sh 2>/dev/null || true
    chmod +x tools/*.sh 2>/dev/null || true
    echo -e "${GREEN}Scripts are now executable${NC}"

    # Initial Setup
    if [ "$init_mode" = true ]; then
        echo ""
        echo -e "${BLUE}Running initial setup...${NC}"

        if [ ! -f "$PROJECT_ROOT/.env" ]; then
            echo ""
            echo -e "${YELLOW}No .env file found. Starting interactive setup...${NC}"
            "$PROJECT_ROOT/scripts/setup-env.sh"
        else
            echo -e "${GREEN}.env file already exists${NC}"
            read -p "Do you want to reconfigure? (y/N): " reconfigure
            if [[ "$reconfigure" =~ ^[Yy]$ ]]; then
                "$PROJECT_ROOT/scripts/setup-env.sh"
            fi
        fi
    fi

    # Summary
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
        echo "  ./runner.sh start       - Start runners"
        echo "  ./runner.sh start 4     - Start 4 runners"
        echo "  ./runner.sh status      - Check status"
    else
        echo -e "${YELLOW}Configuration required:${NC}"
        echo "  ./runner.sh deploy --init    - Run initial setup"
        echo "  OR"
        echo "  ./scripts/setup-env.sh       - Configure environment"
    fi
    echo ""
}

cmd_logs() {
    local service=${1:-}
    local compose_cmd=$(get_compose_cmd)

    print_header "Logs"

    cd "$PROJECT_ROOT"

    if [ -n "$service" ]; then
        $compose_cmd logs -f "$service"
    else
        $compose_cmd logs -f
    fi
}

cmd_help() {
    echo -e "${BLUE}"
    echo "============================================================================="
    echo "  GitHub Runner - Management Tool"
    echo "============================================================================="
    echo -e "${NC}"
    echo "Usage: ./runner.sh <command> [options]"
    echo ""
    echo -e "${CYAN}Operations:${NC}"
    echo "  start [N]         Start N runners (default: 1)"
    echo "  stop              Stop all runners"
    echo "  status            Show status and resources"
    echo "  scale N           Scale to N runners"
    echo "  logs [service]    Show logs (agent, docker-in-docker)"
    echo ""
    echo -e "${CYAN}Maintenance:${NC}"
    echo "  cleanup           Basic cleanup (work directories)"
    echo "  cleanup --full    Full cleanup (volumes, images, cache)"
    echo "  deploy            Pull updates, set permissions"
    echo "  deploy --init     Initial deployment with setup"
    echo ""
    echo -e "${CYAN}Setup (separate scripts):${NC}"
    echo "  ./scripts/setup-env.sh         Interactive .env configuration"
    echo "  ./scripts/create-github-app.sh Create GitHub App for auth"
    echo ""
    echo -e "${CYAN}Examples:${NC}"
    echo "  ./runner.sh start 4        # Start 4 parallel runners"
    echo "  ./runner.sh scale 8        # Scale to 8 runners"
    echo "  ./runner.sh cleanup --full # Full Docker cleanup"
    echo "  ./runner.sh logs agent     # Follow runner logs"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

cd "$PROJECT_ROOT"

case "${1:-help}" in
    start)
        shift
        cmd_start "$@"
        ;;
    stop)
        cmd_stop
        ;;
    status)
        cmd_status
        ;;
    scale)
        shift
        cmd_scale "$@"
        ;;
    cleanup|clean)
        shift
        cmd_cleanup "$@"
        ;;
    deploy)
        shift
        cmd_deploy "$@"
        ;;
    logs|log)
        shift
        cmd_logs "$@"
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        cmd_help
        exit 1
        ;;
esac
