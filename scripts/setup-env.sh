#!/bin/bash
# =============================================================================
# GitHub Runner - Environment Setup Script
# =============================================================================
# Interactive script to create and configure .env file
# Guides user through required configuration options
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}"
echo "============================================================================="
echo "  GitHub Runner - Environment Setup"
echo "============================================================================="
echo -e "${NC}"

# Check if .env already exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}Warning: .env file already exists!${NC}"
    read -p "Do you want to overwrite it? (y/N): " overwrite
    if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        echo "Aborting. Existing .env file preserved."
        exit 0
    fi
    # Backup existing .env
    backup_file="$PROJECT_ROOT/.env.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$PROJECT_ROOT/.env" "$backup_file"
    echo -e "${GREEN}Backup created: $backup_file${NC}"
fi

# Copy template
cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
echo -e "${GREEN}Created .env from template${NC}"

echo ""
echo -e "${BLUE}=== GitHub Configuration ===${NC}"
echo ""

# Get GitHub Access Token
echo "You need a GitHub Personal Access Token (PAT) with the following scopes:"
echo "  - For organization runners: repo, admin:org"
echo "  - For repository runners: repo, admin:repo_hook"
echo ""
echo "Create one at: https://github.com/settings/tokens"
echo ""
read -p "Enter your GitHub Access Token: " github_token

if [ -z "$github_token" ]; then
    echo -e "${RED}Error: GitHub Access Token is required!${NC}"
    exit 1
fi

# Determine scope first
echo ""
echo "Runner scope:"
echo "  1) org  - Organization-level runner (recommended)"
echo "  2) repo - Single repository runner"
read -p "Select scope (1/2) [1]: " scope_choice
scope_choice=${scope_choice:-1}

org_name=""
repo_url=""

if [ "$scope_choice" = "2" ]; then
    runner_scope="repo"
    # Get Repository URL for repo runners
    echo ""
    echo "Enter the full repository URL:"
    echo "  Example: https://github.com/bauer-group/your-repo"
    echo ""
    read -p "Repository URL: " repo_url
    if [ -z "$repo_url" ]; then
        echo -e "${RED}Error: Repository URL is required!${NC}"
        exit 1
    fi
else
    runner_scope="org"
    # Get Organization Name for org runners
    echo ""
    echo "Enter your GitHub organization name (NOT the full URL):"
    echo "  Example: bauer-group"
    echo ""
    read -p "Organization name: " org_name
    if [ -z "$org_name" ]; then
        echo -e "${RED}Error: Organization name is required!${NC}"
        exit 1
    fi
fi

# Get runner labels
echo ""
echo "Runner labels (comma-separated, added to default labels: self-hosted, linux, x64)"
read -p "Additional labels [docker]: " runner_labels
runner_labels=${runner_labels:-docker}

# Get runner name prefix
echo ""
read -p "Runner name prefix [self-hosted]: " runner_prefix
runner_prefix=${runner_prefix:-self-hosted}

# Get stack name
echo ""
read -p "Stack name (for container naming) [github-runner]: " stack_name
stack_name=${stack_name:-github-runner}

# Update .env file
echo ""
echo -e "${BLUE}Updating .env file...${NC}"

# Make scripts executable
chmod +x "$PROJECT_ROOT/runner.sh" 2>/dev/null || true
chmod +x "$PROJECT_ROOT/scripts/"*.sh 2>/dev/null || true

# Use sed to update values (cross-platform compatible)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s|^GITHUB_ACCESS_TOKEN=.*|GITHUB_ACCESS_TOKEN=$github_token|" "$PROJECT_ROOT/.env"
    sed -i '' "s|^RUNNER_SCOPE=.*|RUNNER_SCOPE=$runner_scope|" "$PROJECT_ROOT/.env"
    sed -i '' "s|^RUNNER_LABELS=.*|RUNNER_LABELS=$runner_labels|" "$PROJECT_ROOT/.env"
    sed -i '' "s|^RUNNER_NAME_PREFIX=.*|RUNNER_NAME_PREFIX=$runner_prefix|" "$PROJECT_ROOT/.env"
    sed -i '' "s|^STACK_NAME=.*|STACK_NAME=$stack_name|" "$PROJECT_ROOT/.env"
    if [ -n "$org_name" ]; then
        sed -i '' "s|^ORG_NAME=.*|ORG_NAME=$org_name|" "$PROJECT_ROOT/.env"
    fi
    if [ -n "$repo_url" ]; then
        sed -i '' "s|^# REPO_URL=.*|REPO_URL=$repo_url|" "$PROJECT_ROOT/.env"
    fi
else
    # Linux
    sed -i "s|^GITHUB_ACCESS_TOKEN=.*|GITHUB_ACCESS_TOKEN=$github_token|" "$PROJECT_ROOT/.env"
    sed -i "s|^RUNNER_SCOPE=.*|RUNNER_SCOPE=$runner_scope|" "$PROJECT_ROOT/.env"
    sed -i "s|^RUNNER_LABELS=.*|RUNNER_LABELS=$runner_labels|" "$PROJECT_ROOT/.env"
    sed -i "s|^RUNNER_NAME_PREFIX=.*|RUNNER_NAME_PREFIX=$runner_prefix|" "$PROJECT_ROOT/.env"
    sed -i "s|^STACK_NAME=.*|STACK_NAME=$stack_name|" "$PROJECT_ROOT/.env"
    if [ -n "$org_name" ]; then
        sed -i "s|^ORG_NAME=.*|ORG_NAME=$org_name|" "$PROJECT_ROOT/.env"
    fi
    if [ -n "$repo_url" ]; then
        sed -i "s|^# REPO_URL=.*|REPO_URL=$repo_url|" "$PROJECT_ROOT/.env"
    fi
fi

echo ""
echo -e "${GREEN}=============================================================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}=============================================================================${NC}"
echo ""
echo "Configuration saved to: $PROJECT_ROOT/.env"
echo ""
echo "Next steps:"
echo "  1. Review and adjust settings in .env if needed"
echo "  2. Start the runner:"
echo ""
echo "     ./runner.sh start       # Single runner"
echo "     ./runner.sh start 4     # 4 parallel runners"
echo ""
echo "  3. Check runner status:"
echo "     ./runner.sh status"
echo ""
echo "  4. Verify in GitHub:"
if [ -n "$org_name" ]; then
    echo "     https://github.com/organizations/${org_name}/settings/actions/runners"
else
    echo "     ${repo_url}/settings/actions/runners"
fi
echo ""
