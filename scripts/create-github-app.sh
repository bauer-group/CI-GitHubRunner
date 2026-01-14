#!/bin/bash
# =============================================================================
# GitHub Runner - Create GitHub App Script
# =============================================================================
# Creates a GitHub App with the correct permissions for self-hosted runners
# Uses either the automated Python tool or manual instructions
# Usage: ./scripts/create-github-app.sh [--manual]
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
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Make scripts executable
chmod +x "$PROJECT_ROOT/runner.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null || true
chmod +x "$SCRIPT_DIR"/*.py 2>/dev/null || true

# Check for --manual flag
if [[ "$1" == "--manual" ]] || [[ "$1" == "-m" ]]; then
    MANUAL_MODE=true
else
    MANUAL_MODE=false
fi

# Check if Python 3 is available
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    # Check if it's Python 3
    if python --version 2>&1 | grep -q "Python 3"; then
        PYTHON_CMD="python"
    fi
fi

# If Python 3 is available and not manual mode, use the automated tool
if [[ -n "$PYTHON_CMD" ]] && [[ "$MANUAL_MODE" == "false" ]]; then
    echo -e "${BLUE}"
    echo "============================================================================="
    echo "  GitHub App Creator - Automated Setup"
    echo "============================================================================="
    echo -e "${NC}"
    echo ""
    echo -e "${GREEN}Using automated Python tool for GitHub App creation.${NC}"
    echo "This will:"
    echo "  1. Open your browser to create the app"
    echo "  2. Automatically receive the credentials"
    echo "  3. Save the private key"
    echo "  4. Configure .env"
    echo ""
    echo -e "${YELLOW}For manual instructions, run: $0 --manual${NC}"
    echo ""

    exec "$PYTHON_CMD" "$SCRIPT_DIR/setup-github-app.py"
fi

# Manual mode or no Python available
echo -e "${BLUE}"
echo "============================================================================="
echo "  GitHub App Creator - Manual Setup"
echo "============================================================================="
echo -e "${NC}"

if [[ -z "$PYTHON_CMD" ]]; then
    echo -e "${YELLOW}Note: Python 3 not found. Using manual setup.${NC}"
    echo -e "${YELLOW}Install Python 3 for automated setup.${NC}"
    echo ""
fi

echo "This guide helps you create a GitHub App with minimal permissions."
echo ""
echo -e "${CYAN}Vorteile einer GitHub App gegenüber PAT:${NC}"
echo "  - Nur minimale Berechtigungen (nicht voller admin:org Zugriff)"
echo "  - Automatische Token-Rotation"
echo "  - Bessere Audit-Logs"
echo ""

read -p "Enter your GitHub organization name: " ORG_NAME

if [ -z "$ORG_NAME" ]; then
    echo -e "${RED}Error: Organization name is required!${NC}"
    exit 1
fi

APP_NAME="self-hosted-runner-${ORG_NAME}"

echo ""
echo -e "${GREEN}=============================================================================${NC}"
echo -e "${GREEN}  Schritt 1: GitHub App erstellen${NC}"
echo -e "${GREEN}=============================================================================${NC}"
echo ""
echo "1. Öffne: https://github.com/organizations/${ORG_NAME}/settings/apps/new"
echo ""
echo "2. Konfiguriere die App:"
echo "   - Name: ${APP_NAME}"
echo "   - Homepage URL: https://github.com/${ORG_NAME}"
echo "   - Webhook: DEAKTIVIEREN (Häkchen entfernen)"
echo ""
echo "3. Permissions setzen:"
echo "   - Organization permissions:"
echo "     - Self-hosted runners: Read and write"
echo "   - Repository permissions:"
echo "     - Administration: Read and write"
echo ""
echo "4. 'Create GitHub App' klicken"
echo ""
echo "5. Nach Erstellung:"
echo "   - App ID notieren (oben auf der App-Seite)"
echo "   - 'Generate a private key' klicken und .pem Datei speichern"
echo "   - App installieren: 'Install App' → Organisation auswählen"
echo ""

read -p "Drücke Enter wenn die App erstellt wurde..."

echo ""
echo -e "${BLUE}=============================================================================${NC}"
echo -e "${BLUE}  Schritt 2: .env konfigurieren${NC}"
echo -e "${BLUE}=============================================================================${NC}"
echo ""

ENV_FILE="$PROJECT_ROOT/.env"

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        echo -e "${YELLOW}Keine .env gefunden. Kopiere .env.example...${NC}"
        cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
    else
        echo -e "${RED}Fehler: Keine .env oder .env.example gefunden!${NC}"
        exit 1
    fi
fi

# Get App ID
read -p "GitHub App ID (Zahl von der App-Seite): " APP_ID
if [ -z "$APP_ID" ]; then
    echo -e "${RED}Fehler: App ID ist erforderlich!${NC}"
    exit 1
fi

# Validate App ID is numeric
if ! [[ "$APP_ID" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}Fehler: App ID muss eine Zahl sein!${NC}"
    exit 1
fi

# Get Private Key path
echo ""
echo "Wo hast du die Private Key Datei (.pem) gespeichert?"
echo "  Beispiel: ./github-app.pem (im Projektverzeichnis)"
read -p "Pfad zur Private Key Datei: " PRIVATE_KEY_PATH

if [ -z "$PRIVATE_KEY_PATH" ]; then
    echo -e "${RED}Fehler: Private Key Pfad ist erforderlich!${NC}"
    exit 1
fi

# Convert relative path to absolute if needed
if [[ ! "$PRIVATE_KEY_PATH" = /* ]]; then
    PRIVATE_KEY_PATH="$PROJECT_ROOT/$PRIVATE_KEY_PATH"
fi

echo ""
echo -e "${CYAN}Aktualisiere .env...${NC}"

# Update .env file using sed
update_env() {
    local key=$1
    local value=$2
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    elif grep -q "^# ${key}=" "$ENV_FILE"; then
        sed -i "s|^# ${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

update_env "APP_ID" "$APP_ID"
update_env "APP_LOGIN" "$ORG_NAME"
update_env "APP_PRIVATE_KEY" "$PRIVATE_KEY_PATH"
update_env "RUNNER_SCOPE" "org"
update_env "ORG_NAME" "$ORG_NAME"

# Comment out GITHUB_ACCESS_TOKEN
if grep -q "^GITHUB_ACCESS_TOKEN=" "$ENV_FILE"; then
    echo -e "${YELLOW}Kommentiere GITHUB_ACCESS_TOKEN aus...${NC}"
    sed -i "s|^GITHUB_ACCESS_TOKEN=|# GITHUB_ACCESS_TOKEN=|" "$ENV_FILE"
fi

echo ""
echo -e "${GREEN}=============================================================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}=============================================================================${NC}"
echo ""
echo "Konfigurierte Werte:"
echo "  APP_ID=$APP_ID"
echo "  APP_LOGIN=$ORG_NAME"
echo "  APP_PRIVATE_KEY=$PRIVATE_KEY_PATH"
echo ""
echo -e "${YELLOW}Wichtig: Vergiss nicht, die GitHub App in der Organisation zu installieren!${NC}"
echo "  https://github.com/organizations/${ORG_NAME}/settings/apps"
echo ""
echo "Nächste Schritte:"
echo "  ./runner.sh start       - Runner starten"
echo "  ./runner.sh status      - Status prüfen"
echo ""
