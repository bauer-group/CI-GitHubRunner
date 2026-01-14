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

```text
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

**Quick start with pre-selected scopes:**

- **Organization Runner:** [Create token (repo + admin:org)](https://github.com/settings/tokens/new?scopes=repo,admin:org&description=Self-Hosted-Runner)
- **Repository Runner:** [Create token (repo)](https://github.com/settings/tokens/new?scopes=repo&description=Self-Hosted-Runner)

**Or manually:**

1. Go to [GitHub Settings → Tokens (classic)](https://github.com/settings/tokens)
2. Click **"Generate new token (classic)"**
3. Set expiration (recommend: 90 days)
4. Select scopes:

   | Runner Type  | Required Scopes     |
   |--------------|---------------------|
   | Organization | `repo`, `admin:org` |
   | Repository   | `repo`              |

5. Click **"Generate token"** and copy immediately

> **Note on `admin:org`:** This scope grants full administrative access to the entire organization (not just runners). This includes:
>
> - Managing runners and runner groups
> - Managing webhooks, teams, members
> - Changing organization settings
>
> For enhanced security, we recommend **Option C: GitHub App** - it has only the minimum required permissions.

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

**Quick start with helper script:**

```bash
# Interactive script for GitHub App creation
./scripts/create-github-app.sh
```

The script:

1. Creates the app manifest with correct permissions
2. Generates the URL for manifest-based app creation
3. Automatically configures the `.env` file (optional)

**Or manually:**

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
APP_PRIVATE_KEY=./github-app.pem
RUNNER_SCOPE=org
ORG_NAME=your-org-name
```

**Note:** `APP_PRIVATE_KEY` is the host path to the PEM file. The setup script writes the absolute path (more secure). Relative paths (`./github-app.pem`) also work. The `runner.sh` script automatically detects GitHub App auth and mounts the file to `/opt/github-app.pem` in the container.

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

> **Important:** The runner group must exist in GitHub **before** starting the runners!
> The "Default" group always exists. Custom groups must be created manually.

**Create runner group (if not exists):**

1. Go to `https://github.com/organizations/bauer-group/settings/actions/runner-groups`
2. Click **"New runner group"**
3. Name: e.g., `Self-Hosted (BAUER GROUP)`
4. Configure repository access as needed
5. Click **"Create group"**

**Configure existing group:**

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
    # Option 2: Runner Group + Labels (recommended for orgs)
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

| Variable              | Description                                    | Default      |
|-----------------------|------------------------------------------------|--------------|
| `GITHUB_ACCESS_TOKEN` | PAT with admin scopes                          | **Required** |
| `RUNNER_SCOPE`        | `org` or `repo`                                | `org`        |
| `ORG_NAME`            | Organization name (for `org` scope)            | -            |
| `REPO_URL`            | Repository URL (for `repo` scope)              | -            |
| `RUNNER_GROUP`        | Runner group name (must exist in GitHub)       | `Default`    |
| `RUNNER_LABELS`       | Additional labels (default: self-hosted, linux, x64) | `docker` |

### Resource Limits

Only DinD needs resource limits - all Docker builds run there. Runner agents are lightweight (~200MB RAM).

| Variable            | Default | Description                          |
|---------------------|---------|--------------------------------------|
| `DIND_MEMORY_LIMIT` | `56g`   | DinD container memory (all builds here!) |
| `DIND_CPU_LIMIT`    | `28`    | DinD container CPUs                  |
| `DIND_SHM_SIZE`     | `8g`    | Shared memory for large builds       |

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

For better control, you can specify the runner group directly in the workflow:

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

**Benefits of specifying runner group:**

- Explicit assignment to a specific runner group
- Prevents accidental execution on wrong runners
- Better control in orgs with multiple runner groups
- Labels can be additionally filtered within the group

**Group only without labels:**

```yaml
jobs:
  build:
    runs-on:
      group: Self-Hosted (BAUER GROUP)
    # Uses any available runner from the group
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

#### Fallback to GitHub-Hosted Runners

When self-hosted runners are unavailable, you can fall back to GitHub-hosted runners:

```yaml
name: Build with Fallback

on: [push, pull_request]

jobs:
  # Check if self-hosted runners are available
  check-runners:
    runs-on: ubuntu-latest
    outputs:
      use-self-hosted: ${{ steps.check.outputs.available }}
    steps:
      - name: Check self-hosted runner availability
        id: check
        run: |
          # Try to reach self-hosted runner (timeout 10s)
          # This check is optional - alternatively just set "true"
          echo "available=true" >> $GITHUB_OUTPUT

  build:
    needs: check-runners
    # Dynamic runner selection based on availability
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
            # Fallback build without Docker
          fi
```

**Simpler alternative with workflow dispatch:**

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

**Note:** GitHub Actions has no built-in automatic fallback mechanism. The examples above show workarounds for various scenarios.

### Best Practices

1. **Always use `if: always()` for cleanup steps** - ensures containers are removed even on failure
2. **Use specific labels** - `[self-hosted, linux, docker]` instead of just `[self-hosted]`
3. **Use runner groups for orgs** - `runs-on: { group: "My Group", labels: [...] }`
4. **Don't store secrets in images** - use GitHub Secrets and environment variables
5. **Clean up after tests** - `docker compose down -v` removes volumes too
6. **Use BuildKit** - faster builds with better caching (enabled by default)

## For Developers

All workflows in this organization support self-hosted GitHub Actions runners. This enables:

- **Cost Control**: No GitHub Actions minutes consumption
- **Custom Hardware**: Use specialized hardware (GPU, high RAM, etc.)
- **Network Access**: Access to internal networks and resources
- **Compliance**: Builds within your own infrastructure
- **Performance**: Faster builds with local resources

> **Important**: Self-hosted runners outside of GitHub's infrastructure do not have access to the GitHub Actions Cache Service. See [Cache Configuration](#cache-configuration) for details.

### Runner Configuration via Org Variable

The organization provides a variable `RUNNER_LINUX` to centrally enable self-hosted runners:

| `vars.RUNNER_LINUX`          | Runner Used                   |
|------------------------------|-------------------------------|
| Not set                      | `ubuntu-latest` (GitHub-hosted) |
| `["self-hosted", "linux"]`   | Self-Hosted Runner            |

**Usage in workflows:**

```yaml
jobs:
  build:
    runs-on: ${{ vars.RUNNER_LINUX && fromJSON(vars.RUNNER_LINUX) || 'ubuntu-latest' }}
    steps:
      - uses: actions/checkout@v4
      - run: echo "Running on ${{ runner.name }}"
```

### With Reusable Workflows

```yaml
# Call a reusable workflow with self-hosted runner
jobs:
  build:
    uses: bauer-group/automation-templates/.github/workflows/docker-build.yml@main
    with:
      runs-on: ${{ vars.RUNNER_LINUX && toJSON(fromJSON(vars.RUNNER_LINUX)) || '"ubuntu-latest"' }}
      cache-enabled: ${{ !vars.RUNNER_LINUX }}  # Cache only for GitHub-hosted
```

### Cache Configuration

Self-hosted runners have **no access** to the GitHub Actions Cache Service (`actions/cache`). Therefore:

| Runner Type   | `actions/cache` | Docker Layer Cache | Registry Cache |
|---------------|-----------------|-------------------|----------------|
| GitHub-hosted | ✅ Works        | ❌ Not persistent  | ✅ Works       |
| Self-hosted   | ❌ Not available | ✅ Locally persistent | ✅ Works    |

**Recommendations for self-hosted:**

1. **Use Docker layer cache** - Persists locally between jobs
2. **Registry cache** - `docker/build-push-action` with `cache-to: type=registry`
3. **`cache-enabled: false`** - For reusable workflows with cache option

```yaml
# Example: Docker build with registry cache (self-hosted compatible)
- uses: docker/build-push-action@v5
  with:
    context: .
    cache-from: type=registry,ref=ghcr.io/${{ github.repository }}:cache
    cache-to: type=registry,ref=ghcr.io/${{ github.repository }}:cache,mode=max
```

### Developer Links

| Resource                  | Link                                                                                      |
|---------------------------|-------------------------------------------------------------------------------------------|
| Docker-in-Docker Solution | <https://github.com/bauer-group/GitHubRunner>                                             |
| GitHub Actions Cache Docs | <https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows> |
| Docker Build Cache        | <https://docs.docker.com/build/cache/>                                                    |

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

Central script for all runner operations.

```bash
./runner.sh <command> [options]
```

**Commands:**

| Command         | Description                              |
|-----------------|------------------------------------------|
| `start [N]`     | Start N runners (default: 1)             |
| `stop`          | Stop all runners                         |
| `status`        | Show status and resources                |
| `scale N`       | Scale to N runners                       |
| `logs [service]`| Show logs (agent, docker-in-docker)      |
| `cleanup`       | Basic cleanup (work directories)         |
| `cleanup --full`| Full cleanup (volumes, images)           |
| `deploy`        | Pull updates, set permissions            |
| `deploy --init` | Initial deployment with setup            |
| `help`          | Show help                                |

**Examples:**

```bash
# Start runners
./runner.sh start 4        # Start 4 parallel runners
./runner.sh status         # Show status
./runner.sh scale 8        # Scale to 8 runners
./runner.sh logs agent     # Follow runner logs

# Maintenance
./runner.sh cleanup --full # Docker cleanup
./runner.sh deploy         # Apply updates

# Initial setup
./runner.sh deploy --init  # Initial setup
```

### Setup Scripts

These scripts remain separate for initial configuration:

#### setup-env.sh

Interactive assistant for `.env` configuration.

```bash
./scripts/setup-env.sh
```

Prompts for: GitHub token, organization/repo, runner scope, labels, group.

#### create-github-app.sh

Creates a GitHub App with minimal permissions. **Recommended over PAT!**

```bash
./scripts/create-github-app.sh           # Automatic (Python)
./scripts/create-github-app.sh --manual  # Manual instructions
```

**Automatic mode (default):**

The Python tool opens the browser, creates the app, and configures everything automatically:

1. Starts local callback server (port 8765)
2. Opens GitHub in browser for app creation
3. Receives credentials automatically via callback
4. Saves the private key
5. Updates the `.env`

**For remote server (SSH):**

```bash
# SSH with port forwarding
ssh -L 8765:localhost:8765 user@server

# Start script - URL is displayed directly
./scripts/create-github-app.sh

# Copy URL from terminal → open in local browser
# Callback comes back to server via port forward
```

**Advantages over PAT:**

- Only minimal permissions (not full `admin:org` access)
- Automatic token rotation
- Better audit logs
- No manual key management

### Windows Usage

On Windows, scripts can be executed via the tools container:

```powershell
# Interactive mode
.\tools\run.ps1

# Execute script directly
.\tools\run.ps1 -Script "./runner.sh start 4"
.\tools\run.ps1 -Script "./runner.sh status"
```

## Maintenance

### View Logs

```bash
./runner.sh logs           # All services
./runner.sh logs agent     # Runner only
```

### Cleanup

```bash
./runner.sh cleanup        # Basic cleanup
./runner.sh cleanup --full # Full cleanup
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
│   ├── setup-env.sh          # Interactive .env configuration
│   ├── create-github-app.sh  # Create GitHub App (wrapper)
│   └── setup-github-app.py   # Automated GitHub App setup
├── tools/
│   ├── Dockerfile
│   ├── run.sh
│   ├── run.ps1
│   └── run.cmd
├── runner.sh                  # Unified Management Tool
├── docker-compose.yml         # Base Docker Compose config
├── docker-compose.app-auth.yml # GitHub App auth override (auto-detected)
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
