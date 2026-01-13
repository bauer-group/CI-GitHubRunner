#!/bin/bash
# =============================================================================
# GitHub Runner - Create GitHub App Script
# =============================================================================
# Creates a GitHub App with the correct permissions for self-hosted runners
# Uses the GitHub App Manifest Flow
# Usage: ./scripts/create-github-app.sh
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

echo -e "${BLUE}"
echo "============================================================================="
echo "  GitHub App Creator - Self-Hosted Runner"
echo "============================================================================="
echo -e "${NC}"

# Get organization name
echo "This script creates a GitHub App with minimal permissions for self-hosted runners."
echo ""
echo -e "${YELLOW}Vorteile einer GitHub App gegenüber PAT:${NC}"
echo "  - Nur minimale Berechtigungen (nicht voller admin:org Zugriff)"
echo "  - Automatische Token-Rotation"
echo "  - Bessere Audit-Logs"
echo ""

read -p "Enter your GitHub organization name: " ORG_NAME

if [ -z "$ORG_NAME" ]; then
    echo -e "${RED}Error: Organization name is required!${NC}"
    exit 1
fi

# App name
DEFAULT_APP_NAME="self-hosted-runner-${ORG_NAME}"
read -p "App name [$DEFAULT_APP_NAME]: " APP_NAME
APP_NAME=${APP_NAME:-$DEFAULT_APP_NAME}

# Create manifest JSON
MANIFEST=$(cat <<EOF
{
  "name": "${APP_NAME}",
  "url": "https://github.com/${ORG_NAME}",
  "hook_attributes": {
    "active": false
  },
  "redirect_url": "https://github.com/${ORG_NAME}",
  "public": false,
  "default_permissions": {
    "organization_self_hosted_runners": "write",
    "administration": "write"
  },
  "default_events": []
}
EOF
)

echo ""
echo -e "${BLUE}GitHub App Manifest:${NC}"
echo "$MANIFEST" | jq . 2>/dev/null || echo "$MANIFEST"

echo ""
echo -e "${GREEN}=============================================================================${NC}"
echo -e "${GREEN}  Nächste Schritte - Manuelle Erstellung in GitHub${NC}"
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
echo -e "${YELLOW}=============================================================================${NC}"
echo -e "${YELLOW}  Alternativ: Manifest-basierte Erstellung (Automatisch)${NC}"
echo -e "${YELLOW}=============================================================================${NC}"
echo ""
echo "Öffne diese URL um die App mit dem Manifest zu erstellen:"
echo ""

# URL-encode the manifest
ENCODED_MANIFEST=$(echo "$MANIFEST" | jq -c . | python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read()))" 2>/dev/null || echo "$MANIFEST")

echo "https://github.com/organizations/${ORG_NAME}/settings/apps/new?manifest=${ENCODED_MANIFEST}"
echo ""
echo -e "${BLUE}=============================================================================${NC}"
echo -e "${BLUE}  Nach App-Erstellung - .env konfigurieren${NC}"
echo -e "${BLUE}=============================================================================${NC}"
echo ""
echo "Füge folgende Werte in deine .env ein:"
echo ""
echo "  # GitHub App Authentication"
echo "  APP_ID=<App ID von der GitHub App Seite>"
echo "  APP_LOGIN=${ORG_NAME}"
echo "  APP_PRIVATE_KEY=/path/to/private-key.pem"
echo ""
echo "  # Deaktiviere PAT wenn App verwendet wird"
echo "  # GITHUB_ACCESS_TOKEN=..."
echo ""

# Save manifest to file
MANIFEST_FILE="$PROJECT_ROOT/github-app-manifest.json"
echo "$MANIFEST" > "$MANIFEST_FILE"
echo -e "${GREEN}Manifest gespeichert: $MANIFEST_FILE${NC}"
echo ""

# =============================================================================
# Interactive .env Configuration
# =============================================================================
echo ""
read -p "Möchtest du die .env jetzt konfigurieren? (j/n) [n]: " CONFIGURE_ENV
CONFIGURE_ENV=${CONFIGURE_ENV:-n}

if [[ "$CONFIGURE_ENV" =~ ^[jJyY]$ ]]; then
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

    echo ""
    echo -e "${BLUE}=============================================================================${NC}"
    echo -e "${BLUE}  .env Konfiguration${NC}"
    echo -e "${BLUE}=============================================================================${NC}"
    echo ""

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
    echo "  Beispiel: /opt/CI-GitHubRunner/github-app.pem"
    echo "  Beispiel: ./github-app.pem (relativ zum Projektverzeichnis)"
    read -p "Pfad zur Private Key Datei: " PRIVATE_KEY_PATH

    if [ -z "$PRIVATE_KEY_PATH" ]; then
        echo -e "${RED}Fehler: Private Key Pfad ist erforderlich!${NC}"
        exit 1
    fi

    # Convert relative path to absolute if needed
    if [[ ! "$PRIVATE_KEY_PATH" = /* ]]; then
        PRIVATE_KEY_PATH="$PROJECT_ROOT/$PRIVATE_KEY_PATH"
    fi

    # Check if key file exists
    if [ ! -f "$PRIVATE_KEY_PATH" ]; then
        echo -e "${YELLOW}Warnung: Datei $PRIVATE_KEY_PATH existiert noch nicht.${NC}"
        echo "Stelle sicher, dass du die .pem Datei dort speicherst!"
    fi

    echo ""
    echo -e "${CYAN}Aktualisiere .env...${NC}"

    # Update or add APP_ID
    if grep -q "^APP_ID=" "$ENV_FILE"; then
        sed -i "s|^APP_ID=.*|APP_ID=$APP_ID|" "$ENV_FILE"
    elif grep -q "^# APP_ID=" "$ENV_FILE"; then
        sed -i "s|^# APP_ID=.*|APP_ID=$APP_ID|" "$ENV_FILE"
    else
        echo "" >> "$ENV_FILE"
        echo "# GitHub App Authentication" >> "$ENV_FILE"
        echo "APP_ID=$APP_ID" >> "$ENV_FILE"
    fi

    # Update or add APP_LOGIN
    if grep -q "^APP_LOGIN=" "$ENV_FILE"; then
        sed -i "s|^APP_LOGIN=.*|APP_LOGIN=$ORG_NAME|" "$ENV_FILE"
    elif grep -q "^# APP_LOGIN=" "$ENV_FILE"; then
        sed -i "s|^# APP_LOGIN=.*|APP_LOGIN=$ORG_NAME|" "$ENV_FILE"
    else
        echo "APP_LOGIN=$ORG_NAME" >> "$ENV_FILE"
    fi

    # Update or add APP_PRIVATE_KEY
    if grep -q "^APP_PRIVATE_KEY=" "$ENV_FILE"; then
        sed -i "s|^APP_PRIVATE_KEY=.*|APP_PRIVATE_KEY=$PRIVATE_KEY_PATH|" "$ENV_FILE"
    elif grep -q "^# APP_PRIVATE_KEY=" "$ENV_FILE"; then
        sed -i "s|^# APP_PRIVATE_KEY=.*|APP_PRIVATE_KEY=$PRIVATE_KEY_PATH|" "$ENV_FILE"
    else
        echo "APP_PRIVATE_KEY=$PRIVATE_KEY_PATH" >> "$ENV_FILE"
    fi

    # Comment out GITHUB_ACCESS_TOKEN if not already commented
    if grep -q "^GITHUB_ACCESS_TOKEN=" "$ENV_FILE"; then
        echo -e "${YELLOW}Kommentiere GITHUB_ACCESS_TOKEN aus (GitHub App wird verwendet)...${NC}"
        sed -i "s|^GITHUB_ACCESS_TOKEN=|# GITHUB_ACCESS_TOKEN=|" "$ENV_FILE"
    fi

    # Ensure RUNNER_SCOPE is set to org
    if grep -q "^RUNNER_SCOPE=" "$ENV_FILE"; then
        sed -i "s|^RUNNER_SCOPE=.*|RUNNER_SCOPE=org|" "$ENV_FILE"
    fi

    # Ensure ORG_NAME is set
    if grep -q "^ORG_NAME=" "$ENV_FILE"; then
        sed -i "s|^ORG_NAME=.*|ORG_NAME=$ORG_NAME|" "$ENV_FILE"
    fi

    echo ""
    echo -e "${GREEN}=============================================================================${NC}"
    echo -e "${GREEN}  .env erfolgreich konfiguriert!${NC}"
    echo -e "${GREEN}=============================================================================${NC}"
    echo ""
    echo "Konfigurierte Werte:"
    echo "  APP_ID=$APP_ID"
    echo "  APP_LOGIN=$ORG_NAME"
    echo "  APP_PRIVATE_KEY=$PRIVATE_KEY_PATH"
    echo "  RUNNER_SCOPE=org"
    echo "  ORG_NAME=$ORG_NAME"
    echo ""
    echo -e "${YELLOW}Wichtig: Vergiss nicht, die GitHub App in der Organisation zu installieren!${NC}"
    echo "  https://github.com/organizations/${ORG_NAME}/settings/apps"
    echo "  → App auswählen → 'Install App' → Organisation wählen"
    echo ""
fi

echo -e "${GREEN}Fertig!${NC}"
