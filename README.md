# GitHub Runner - Self-Hosted with Docker-in-Docker

High-performance, self-hosted GitHub Actions runners with Docker-in-Docker (DinD) isolation.

## Overview

This solution provides ephemeral GitHub Actions runners that:

- Run in isolated Docker-in-Docker containers
- Auto-destroy after each job (like GitHub-hosted runners)
- Support full Docker workflows (build, push, compose)
- Provide more resources than GitHub-hosted runners (16 CPU, 32GB RAM default)
- Keep other host workloads isolated and secure

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Host System                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Docker Engine (Host)                    │   │
│  │                                                      │   │
│  │  ┌────────────────────────────────────────────────┐ │   │
│  │  │           Isolated Runner Network              │ │   │
│  │  │                                                │ │   │
│  │  │  ┌──────────────┐    ┌───────────────────┐   │ │   │
│  │  │  │   DinD       │    │  GitHub Runner    │   │ │   │
│  │  │  │  Container   │◄───│    Container      │   │ │   │
│  │  │  │              │    │                   │   │ │   │
│  │  │  │  ┌────────┐  │    │  myoung34/        │   │ │   │
│  │  │  │  │ Docker │  │    │  github-runner    │   │ │   │
│  │  │  │  │ Daemon │  │    │                   │   │ │   │
│  │  │  │  └────────┘  │    └───────────────────┘   │ │   │
│  │  │  │       │      │                            │ │   │
│  │  │  │  ┌────┴────┐ │                            │ │   │
│  │  │  │  │ Workflow│ │                            │ │   │
│  │  │  │  │Containers│ │                            │ │   │
│  │  │  │  └─────────┘ │                            │ │   │
│  │  │  └──────────────┘                            │ │   │
│  │  └────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Setup Guide

### Prerequisites

- **Host System**: Linux server with Docker Engine installed
- **Docker Version**: 20.10+ with Docker Compose v2
- **Resources**: Minimum 16GB RAM, 8 CPU cores (recommended: 64GB RAM, 16+ cores)
- **Network**: Outbound internet access to GitHub (api.github.com, github.com)
- **GitHub**: Organization or Repository with admin access

### Step 1: Create GitHub Access Token

#### Option A: Personal Access Token (Classic) - Recommended for Quick Setup

**Schnellstart mit vorausgewählten Scopes:**

- **Organization Runner:** [Token erstellen (repo + admin:org)](https://github.com/settings/tokens/new?scopes=repo,admin:org&description=Self-Hosted-Runner)
- **Repository Runner:** [Token erstellen (repo)](https://github.com/settings/tokens/new?scopes=repo&description=Self-Hosted-Runner)

**Oder manuell:**

1. Go to [GitHub Settings → Tokens (classic)](https://github.com/settings/tokens)
2. Click **"Generate new token (classic)"**
3. Set expiration (recommend: 90 days)
4. Select scopes:

   | Runner Type  | Required Scopes     |
   |--------------|---------------------|
   | Organization | `repo`, `admin:org` |
   | Repository   | `repo`              |

5. Click **"Generate token"** and copy immediately

> **Hinweis zu `admin:org`:** Dieser Scope gewährt vollen Administrationszugriff auf die gesamte Organisation (nicht nur Runner). Dazu gehören:
>
> - Runner und Runner-Gruppen verwalten
> - Webhooks, Teams, Mitglieder verwalten
> - Org-Einstellungen ändern
>
> Für erhöhte Sicherheit empfehlen wir **Option C: GitHub App** - diese hat nur die minimal notwendigen Berechtigungen.

#### Option B: Fine-grained Personal Access Token (More Secure)

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens](https://github.com/settings/personal-access-tokens/new)
2. Set token name and expiration
3. Select **Resource owner**: Your organization
4. Select **Repository access**: All repositories (or specific ones)
5. Set **Permissions**:
   - Repository permissions: `Administration: Read and write`
   - Organization permissions: `Self-hosted runners: Read and write`
6. Generate and copy the token

#### Option C: GitHub App (Recommended for Production)

GitHub Apps provide better security with automatic token rotation and fine-grained permissions.

**Schnellstart mit Helper-Script:**

```bash
# Interaktives Script für GitHub App Erstellung
./scripts/create-github-app.sh
```

Das Script:

1. Erstellt das App-Manifest mit korrekten Berechtigungen
2. Generiert die URL für die Manifest-basierte App-Erstellung
3. Konfiguriert automatisch die `.env` Datei (optional)

**Oder manuell:**

1. Go to `https://github.com/organizations/{org}/settings/apps`
2. Click **"New GitHub App"**
3. Configure the app:
   - **Name**: `Self-Hosted Runner - {Environment}`
   - **Homepage URL**: Your organization URL
   - **Webhook**: Uncheck "Active" (not needed)
4. Set **Permissions**:
   - Repository permissions: `Administration: Read and write`
   - Organization permissions: `Self-hosted runners: Read and write`
5. Click **"Create GitHub App"**
6. Note the **App ID** from the app settings page
7. Generate and download a **Private Key** (.pem file)
8. Install the app to your organization

**Configure in `.env`:**

```bash
# Comment out ACCESS_TOKEN, use App instead
# GITHUB_ACCESS_TOKEN=...

APP_ID=123456
APP_LOGIN=your-org-name
APP_PRIVATE_KEY=/path/to/private-key.pem
RUNNER_SCOPE=org
ORG_NAME=your-org-name
```

Place the private key file (e.g., `github-app.pem`) in the project root, or provide an absolute path.

### Step 2: Prepare the Server

```bash
# Clone this repository to your server
cd /opt
git clone https://github.com/bauer-group/CI-GitHubRunner.git
cd CI-GitHubRunner

# Verify Docker is running
docker info

# Verify Docker Compose v2
docker compose version
```

#### Initial Deployment

Use the unified runner script for first-time setup:

```bash
# Make runner script executable and run initial setup
chmod +x runner.sh
./runner.sh deploy --init
```

The deploy command will:

1. Configure git (disable fileMode for cross-platform compatibility)
2. Pull latest changes from remote
3. Make all scripts executable (`chmod +x`)
4. Run interactive environment setup

#### Manual Setup (Alternative)

```bash
# Configure git for this repo (optional, for cross-platform compatibility)
git config core.fileMode false

# Make scripts executable
chmod +x runner.sh scripts/*.sh tools/*.sh
```

### Step 3: Configure Environment

#### Interactive Setup (Recommended)

**Linux/macOS:**

```bash
./scripts/setup-env.sh
```

**Windows (via Tools Container):**

```powershell
# Start tools container and run setup
.\tools\run.ps1 -Script "./scripts/setup-env.sh"

# Or interactive mode
.\tools\run.ps1
```

This will prompt you for:

- GitHub Access Token
- Organization/Repository URL
- Runner scope (org/repo)
- Runner labels

#### Manual Setup

```bash
# Copy example configuration
cp .env.example .env

# Edit with your values
nano .env
```

**Required settings in `.env`:**

```bash
# Your GitHub PAT from Step 1
GITHUB_ACCESS_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# For organization runner:
RUNNER_SCOPE=org
ORG_NAME=bauer-group

# For repository runner:
RUNNER_SCOPE=repo
REPO_URL=https://github.com/bauer-group/your-repo

# Custom labels for targeting in workflows
RUNNER_LABELS=docker,48-core
```

### Step 4: Start the Runner

```bash
# Start single runner
docker compose up -d

# View logs to verify registration
docker compose logs -f agent
```

**Expected output:**

```text
Runner successfully registered
Runner is listening for jobs...
```

### Step 5: Verify Registration in GitHub

#### For Organization Runners

1. Go to `https://github.com/bauer-group/settings/actions/runners`
2. Your runner should appear as **"Idle"** with labels:
   - `self-hosted`
   - `linux`
   - `x64`
   - `docker`
   - `48-core`

#### For Repository Runners

1. Go to `https://github.com/bauer-group/YOUR-REPO/settings/actions/runners`
2. Verify runner status is **"Idle"**

### Step 6: Scale Runners (Optional)

```bash
# Run 4 parallel runners (sharing one DinD instance)
docker compose up -d --scale agent=4

# Check all runners
docker compose ps
```

## Organization-Wide Runner Setup

Configure your runner to be available for **all repositories** in your organization.

### Runner Group Configuration

> **Wichtig:** Die Runner Group muss **vor** dem Start der Runner in GitHub existieren!
> Die Gruppe "Default" ist immer vorhanden. Eigene Gruppen müssen manuell erstellt werden.

**Runner Group erstellen (falls nicht vorhanden):**

1. Go to `https://github.com/organizations/bauer-group/settings/actions/runner-groups`
2. Click **"New runner group"**
3. Name: z.B. `Self-Hosted (BAUER GROUP)`
4. Configure repository access as needed
5. Click **"Create group"**

**Bestehende Gruppe konfigurieren:**

1. Go to `https://github.com/organizations/bauer-group/settings/actions/runner-groups`
2. Find your runner group (e.g., **"Self-Hosted (BAUER GROUP)"**)
3. Click on the group name to edit settings
4. Configure **Repository access**:

   - **Repository access**: Select "All repositories"
   - **Workflow access**: Enable if you have public repositories

5. Click **"Save"**

### Environment Configuration

Set the runner group in your `.env`:

```bash
# Runner will register in this group
RUNNER_GROUP=Self-Hosted (BAUER GROUP)

# Organization-level runner
RUNNER_SCOPE=org
ORG_NAME=bauer-group
```

### Using in Workflows

Once configured, all repositories in your organization can use the runner:

```yaml
# .github/workflows/build.yml
name: Build

on: [push, pull_request]

jobs:
  build:
    # Option 1: Labels only (matches any runner with these labels)
    runs-on: [self-hosted, linux, docker]
    steps:
      - uses: actions/checkout@v4
      - run: echo "Running on self-hosted runner!"

  build-specific:
    # Option 2: Runner Group + Labels (empfohlen für Orgs)
    runs-on:
      group: Self-Hosted (BAUER GROUP)
      labels: [linux, docker]
    steps:
      - uses: actions/checkout@v4
      - run: echo "Running on runner from specific group!"
```

### Optional: Disable GitHub-Hosted Runners

To enforce using only your self-hosted runners:

1. Go to `https://github.com/bauer-group/settings/actions`
2. Under **"Runners"**, uncheck:
   - ☐ Allow GitHub-hosted runners

Now all workflows **must** use your self-hosted runners.

### Verify Access

Check that your runner appears in the group:

1. Go to `https://github.com/bauer-group/settings/actions/runner-groups`
2. Click on your group (**"Self-Hosted (BAUER GROUP)"**)
3. Your runner should be listed with status **"Idle"**

## Configuration

### Key Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_ACCESS_TOKEN` | PAT with admin scopes | **Required** |
| `RUNNER_SCOPE` | `org` or `repo` | `org` |
| `ORG_NAME` | Organization name (for `org` scope) | - |
| `REPO_URL` | Repository URL (for `repo` scope) | - |
| `RUNNER_GROUP` | Runner group name (must exist in GitHub) | `Default` |
| `RUNNER_LABELS` | Additional labels (default: self-hosted, linux, x64) | `docker` |

### Resource Limits

Only DinD needs resource limits - all Docker builds run there. Runner agents are lightweight (~200MB RAM).

| Variable | Default | Description |
|----------|---------|-------------|
| `DIND_MEMORY_LIMIT` | `56g` | DinD container memory (all builds here!) |
| `DIND_CPU_LIMIT` | `28` | DinD container CPUs |
| `DIND_SHM_SIZE` | `8g` | Shared memory for large builds |

## Usage in Workflows

### Basic Usage

Target your self-hosted runner using labels in `runs-on`:

```yaml
jobs:
  build:
    runs-on: [self-hosted, linux, docker]
    steps:
      - uses: actions/checkout@v4
      - run: echo "Running on self-hosted runner!"
```

### Using Runner Groups

Für bessere Kontrolle kann die Runner Group direkt im Workflow angegeben werden:

```yaml
jobs:
  build:
    runs-on:
      group: Self-Hosted (BAUER GROUP)
      labels: [self-hosted, linux, docker]
    steps:
      - uses: actions/checkout@v4
      - run: echo "Running on runner from specific group!"
```

**Vorteile der Runner Group Angabe:**

- Explizite Zuordnung zu einer bestimmten Runner-Gruppe
- Verhindert versehentliche Ausführung auf falschen Runnern
- Bessere Kontrolle in Orgs mit mehreren Runner-Gruppen
- Labels können zusätzlich zur Gruppe gefiltert werden

**Nur Group ohne Labels:**

```yaml
jobs:
  build:
    runs-on:
      group: Self-Hosted (BAUER GROUP)
    # Verwendet jeden verfügbaren Runner aus der Gruppe
```

### Available Labels

Your runner automatically has these labels:

| Label         | Source  | Description                      |
|---------------|---------|----------------------------------|
| `self-hosted` | Default | Identifies as self-hosted runner |
| `linux`       | Default | Operating system                 |
| `x64`         | Default | Architecture                     |
| `docker`      | Custom  | Has Docker available             |
| `48-core`     | Custom  | High-performance indicator       |

**Matching rules:**

- All specified labels must match
- More labels = more specific targeting
- Use `[self-hosted]` alone to match any self-hosted runner

### Workflow Examples

#### Docker Build and Push

```yaml
name: Build and Push

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: [self-hosted, linux, docker]
    steps:
      - uses: actions/checkout@v4

      - name: Login to Registry
        run: echo "${{ secrets.REGISTRY_PASSWORD }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin

      - name: Build Image
        run: docker build -t ghcr.io/${{ github.repository }}:${{ github.sha }} .

      - name: Push Image
        run: docker push ghcr.io/${{ github.repository }}:${{ github.sha }}
```

#### Docker Compose Tests

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: [self-hosted, linux, docker]
    steps:
      - uses: actions/checkout@v4

      - name: Start Services
        run: docker compose -f docker-compose.test.yml up -d

      - name: Wait for Services
        run: sleep 10

      - name: Run Tests
        run: docker compose -f docker-compose.test.yml exec -T app npm test

      - name: Cleanup
        if: always()
        run: docker compose -f docker-compose.test.yml down -v
```

#### Multi-Stage Build with Caching

```yaml
name: Build with Cache

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: [self-hosted, linux, docker]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build with Cache
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: myapp:latest
          cache-from: type=registry,ref=ghcr.io/${{ github.repository }}:cache
          cache-to: type=registry,ref=ghcr.io/${{ github.repository }}:cache,mode=max
```

#### Matrix Build

```yaml
name: Multi-Platform Build

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: [self-hosted, linux, docker]
    strategy:
      matrix:
        node: [18, 20, 22]
    steps:
      - uses: actions/checkout@v4

      - name: Build for Node ${{ matrix.node }}
        run: docker build --build-arg NODE_VERSION=${{ matrix.node }} -t myapp:node${{ matrix.node }} .
```

#### Fallback zu GitHub-Hosted Runners

Wenn Self-Hosted Runner nicht verfügbar sind, kann auf GitHub-Hosted Runner zurückgefallen werden:

```yaml
name: Build with Fallback

on: [push, pull_request]

jobs:
  # Prüft ob Self-Hosted Runner verfügbar sind
  check-runners:
    runs-on: ubuntu-latest
    outputs:
      use-self-hosted: ${{ steps.check.outputs.available }}
    steps:
      - name: Check self-hosted runner availability
        id: check
        run: |
          # Versuche Self-Hosted Runner zu erreichen (Timeout 10s)
          # Diese Prüfung ist optional - alternativ einfach "true" setzen
          echo "available=true" >> $GITHUB_OUTPUT

  build:
    needs: check-runners
    # Dynamische Runner-Auswahl basierend auf Verfügbarkeit
    runs-on: ${{ needs.check-runners.outputs.use-self-hosted == 'true' && fromJSON('["self-hosted", "linux", "docker"]') || 'ubuntu-latest' }}
    steps:
      - uses: actions/checkout@v4

      - name: Show runner info
        run: |
          echo "Running on: ${{ runner.name }}"
          echo "OS: ${{ runner.os }}"

      - name: Build
        run: |
          if command -v docker &> /dev/null; then
            docker build -t myapp:latest .
          else
            echo "Docker not available, using alternative build"
            # Fallback build ohne Docker
          fi
```

**Einfachere Alternative mit Workflow Dispatch:**

```yaml
name: Build (Selectable Runner)

on:
  workflow_dispatch:
    inputs:
      runner:
        description: 'Runner type'
        required: true
        default: 'self-hosted'
        type: choice
        options:
          - self-hosted
          - ubuntu-latest

jobs:
  build:
    runs-on: ${{ inputs.runner == 'self-hosted' && fromJSON('["self-hosted", "linux", "docker"]') || inputs.runner }}
    steps:
      - uses: actions/checkout@v4
      - run: echo "Building on ${{ runner.name }}"
```

**Hinweis:** GitHub Actions hat keinen eingebauten automatischen Fallback-Mechanismus. Die obigen Beispiele zeigen Workarounds für verschiedene Szenarien.

### Best Practices

1. **Always use `if: always()` for cleanup steps** - ensures containers are removed even on failure
2. **Use specific labels** - `[self-hosted, linux, docker]` instead of just `[self-hosted]`
3. **Use runner groups for orgs** - `runs-on: { group: "My Group", labels: [...] }`
4. **Don't store secrets in images** - use GitHub Secrets and environment variables
5. **Clean up after tests** - `docker compose down -v` removes volumes too
6. **Use BuildKit** - faster builds with better caching (enabled by default)

## Für Entwickler

Alle Workflows in dieser Organisation unterstützen Self-Hosted GitHub Actions Runner. Dies ermöglicht:

- **Kostenkontrolle**: Keine GitHub Actions Minutes Verbrauch
- **Custom Hardware**: Nutzung spezialisierter Hardware (GPU, viel RAM, etc.)
- **Netzwerkzugang**: Zugriff auf interne Netzwerke und Ressourcen
- **Compliance**: Builds innerhalb der eigenen Infrastruktur
- **Performance**: Schnellere Builds mit lokalen Ressourcen

> **Wichtig**: Self-Hosted Runner außerhalb von GitHub's Infrastruktur haben keinen Zugriff auf den GitHub Actions Cache Service. Siehe [Cache-Konfiguration](#cache-konfiguration) für Details.

### Runner-Konfiguration via Org-Variable

Die Organisation stellt eine Variable `RUNNER_LINUX` bereit, um Self-Hosted Runner zentral zu aktivieren:

| `vars.RUNNER_LINUX` | Verwendeter Runner |
|---------------------|-------------------|
| Nicht gesetzt | `ubuntu-latest` (GitHub-hosted) |
| `["self-hosted", "linux"]` | Self-Hosted Runner |

**Verwendung in Workflows:**

```yaml
jobs:
  build:
    runs-on: ${{ vars.RUNNER_LINUX && fromJSON(vars.RUNNER_LINUX) || 'ubuntu-latest' }}
    steps:
      - uses: actions/checkout@v4
      - run: echo "Running on ${{ runner.name }}"
```

### Mit Reusable Workflows

```yaml
# Aufruf eines Reusable Workflows mit Self-Hosted Runner
jobs:
  build:
    uses: bauer-group/automation-templates/.github/workflows/docker-build.yml@main
    with:
      runs-on: ${{ vars.RUNNER_LINUX && toJSON(fromJSON(vars.RUNNER_LINUX)) || '"ubuntu-latest"' }}
      cache-enabled: ${{ !vars.RUNNER_LINUX }}  # Cache nur für GitHub-hosted
```

### Cache-Konfiguration

Self-Hosted Runner haben **keinen Zugriff** auf den GitHub Actions Cache Service (`actions/cache`). Daher:

| Runner-Typ | `actions/cache` | Docker Layer Cache | Registry Cache |
|------------|-----------------|-------------------|----------------|
| GitHub-hosted | ✅ Funktioniert | ❌ Nicht persistent | ✅ Funktioniert |
| Self-hosted | ❌ Nicht verfügbar | ✅ Lokal persistent | ✅ Funktioniert |

**Empfehlungen für Self-Hosted:**

1. **Docker Layer Cache nutzen** - Bleibt lokal erhalten zwischen Jobs
2. **Registry Cache** - `docker/build-push-action` mit `cache-to: type=registry`
3. **`cache-enabled: false`** - Bei Reusable Workflows mit Cache-Option

```yaml
# Beispiel: Docker Build mit Registry Cache (Self-Hosted kompatibel)
- uses: docker/build-push-action@v5
  with:
    context: .
    cache-from: type=registry,ref=ghcr.io/${{ github.repository }}:cache
    cache-to: type=registry,ref=ghcr.io/${{ github.repository }}:cache,mode=max
```

### Links für Entwickler

| Ressource | Link |
|-----------|------|
| Docker-in-Docker Solution | <https://github.com/bauer-group/GitHubRunner> |
| GitHub Actions Cache Docs | <https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows> |
| Docker Build Cache | <https://docs.docker.com/build/cache/> |

### Troubleshooting Workflows

**Job stuck in "Queued":**

- Verify runner is online in GitHub Settings
- Check label matching - all labels must match

**Docker commands fail:**

- Runner automatically connects to DinD
- Check DinD health: `docker compose logs docker-in-docker`

**Out of disk space:**

- Runner workspace is cleaned after each job (ephemeral mode)
- DinD volume persists - run cleanup script periodically

## Scaling

```bash
# Start with 1 runner (default)
./runner.sh start

# Start 4 runners
./runner.sh start 4

# Scale to 8 runners
./runner.sh scale 8

# Scale back down
./runner.sh scale 2
```

**Windows (via Tools Container):**

```powershell
.\tools\run.ps1 -Script "./runner.sh scale 4"
```

All runners share a single DinD instance (shared Docker cache for faster builds).

## Scripts

### runner.sh - Unified Management Tool

Zentrales Script für alle Runner-Operationen.

```bash
./runner.sh <command> [options]
```

**Befehle:**

| Command | Beschreibung |
|---------|--------------|
| `start [N]` | N Runner starten (Standard: 1) |
| `stop` | Alle Runner stoppen |
| `status` | Status und Ressourcen anzeigen |
| `scale N` | Auf N Runner skalieren |
| `logs [service]` | Logs anzeigen (agent, docker-in-docker) |
| `cleanup` | Basis-Cleanup (Work-Verzeichnisse) |
| `cleanup --full` | Vollständiger Cleanup (Volumes, Images) |
| `deploy` | Updates pullen, Berechtigungen setzen |
| `deploy --init` | Erstinstallation mit Setup |
| `help` | Hilfe anzeigen |

**Beispiele:**

```bash
# Runner starten
./runner.sh start 4        # 4 parallele Runner starten
./runner.sh status         # Status anzeigen
./runner.sh scale 8        # Auf 8 Runner skalieren
./runner.sh logs agent     # Runner-Logs verfolgen

# Wartung
./runner.sh cleanup --full # Docker-Cleanup
./runner.sh deploy         # Updates einspielen

# Erstinstallation
./runner.sh deploy --init  # Initiales Setup
```

### Setup-Scripts

Diese Scripts bleiben separat für die Erstkonfiguration:

#### setup-env.sh

Interaktiver Assistent für die `.env`-Konfiguration.

```bash
./scripts/setup-env.sh
```

Fragt ab: GitHub Token, Organisation/Repo, Runner-Scope, Labels, Gruppe.

#### create-github-app.sh

Erstellt eine GitHub App mit minimalen Berechtigungen. **Empfohlen statt PAT!**

```bash
./scripts/create-github-app.sh           # Automatisch (Python)
./scripts/create-github-app.sh --manual  # Manuelle Anleitung
```

**Automatischer Modus (Standard):**

Das Python-Tool öffnet den Browser, erstellt die App und konfiguriert alles automatisch:

1. Startet lokalen Callback-Server (Port 8765)
2. Öffnet GitHub im Browser zur App-Erstellung
3. Empfängt die Credentials automatisch via Callback
4. Speichert den Private Key
5. Aktualisiert die `.env`

**Bei Remote-Server (SSH):**

```bash
# SSH mit Port-Forwarding
ssh -L 8765:localhost:8765 user@server

# Script starten - URL wird direkt angezeigt
./scripts/create-github-app.sh

# URL aus Terminal kopieren → im lokalen Browser öffnen
# Callback kommt über Port-Forward zurück zum Server
```

**Vorteile gegenüber PAT:**

- Nur minimale Berechtigungen (nicht voller `admin:org` Zugriff)
- Automatische Token-Rotation
- Bessere Audit-Logs
- Kein manuelles Key-Management

### Windows-Nutzung

Auf Windows können die Scripts über den Tools-Container ausgeführt werden:

```powershell
# Interaktiver Modus
.\tools\run.ps1

# Script direkt ausführen
.\tools\run.ps1 -Script "./runner.sh start 4"
.\tools\run.ps1 -Script "./runner.sh status"
```

## Maintenance

### View Logs

```bash
./runner.sh logs           # Alle Services
./runner.sh logs agent     # Nur Runner
```

### Cleanup

```bash
./runner.sh cleanup        # Basis-Cleanup
./runner.sh cleanup --full # Vollständiger Cleanup
```

### Update Runner Image

```bash
docker compose pull
docker compose up -d
```

## Security Considerations

### Isolation Layers

1. **DinD Container**: All workflow Docker operations run inside DinD, not on the host
2. **Network Isolation**: Each runner pair has its own internal network
3. **Ephemeral Mode**: Runners destroy themselves after each job
4. **Resource Limits**: Prevents runaway containers from affecting host

### Privileged Mode

DinD requires `privileged: true` to run a Docker daemon. This is contained within:

- The outer Docker container boundary
- Isolated networks
- Resource limits

The host Docker socket is **never** mounted into containers.

### Recommendations

- Use organization runners only for trusted repositories
- Enable ephemeral mode (`EPHEMERAL=true`)
- Regularly update the runner image
- Monitor resource usage
- Use GitHub's runner groups to control access

## Troubleshooting

### Runner Not Registering

1. Verify token has correct scopes
2. Check REPO_URL format
3. View logs: `docker compose logs agent`

### Docker Commands Failing in Workflows

1. Verify DinD is healthy: `docker compose ps`
2. Check DinD logs: `docker compose logs docker-in-docker`
3. Ensure `DOCKER_HOST` is set correctly

### Out of Disk Space

```bash
# Clean up old images and containers
./runner.sh cleanup --full

# Or manually inside DinD
docker compose exec docker-in-docker docker system prune -af
```

### Runner Keeps Restarting

With `EPHEMERAL=true`, runners restart after each job. This is expected behavior.

To check if it's working correctly:

```bash
docker compose logs -f agent | grep -E "(Listening|Running|Removing)"
```

## File Structure

```text
GitHubRunner/
├── .github/
│   ├── workflows/
│   │   ├── release.yml
│   │   ├── docker-maintenance.yml
│   │   └── ...
│   ├── dependabot.yml
│   └── CODEOWNERS
├── scripts/
│   ├── setup-env.sh          # Interaktive .env Konfiguration
│   ├── create-github-app.sh  # GitHub App erstellen (Wrapper)
│   └── setup-github-app.py   # Automatisiertes GitHub App Setup
├── tools/
│   ├── Dockerfile
│   ├── run.sh
│   ├── run.ps1
│   └── run.cmd
├── runner.sh                  # Unified Management Tool
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── CHANGELOG.md
└── NOTICE.md
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

- [myoung34/github-runner](https://github.com/myoung34/docker-github-actions-runner) - GitHub Actions runner Docker image
- [Docker DinD](https://hub.docker.com/_/docker) - Docker-in-Docker official image
