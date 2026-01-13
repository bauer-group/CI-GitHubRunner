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

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click **"Generate new token (classic)"**
3. Set a descriptive name: `Self-Hosted Runner - {Server Name}`
4. Set expiration (recommend: 90 days or custom)
5. Select scopes:

   **For Organization Runner:**

   ```text
   ☑ repo (Full control of private repositories)
   ☑ admin:org → manage_runners:org (Manage org runners and runner groups)
   ```

   **For Repository Runner:**

   ```text
   ☑ repo (Full control of private repositories)
   ```

6. Click **"Generate token"**
7. **Copy the token immediately** - it won't be shown again!

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

1. Go to `https://github.com/organizations/{your-org}/settings/apps`
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
RUNNER_SCOPE=org
```

Place the private key file as `github-app.pem` in the project root, or mount it via volume.

### Step 2: Prepare the Server

```bash
# Clone or copy this repository to your server
cd /opt
git clone https://github.com/your-org/GitHubRunner.git
cd GitHubRunner

# Verify Docker is running
docker info

# Verify Docker Compose v2
docker compose version
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
REPO_URL=https://github.com/your-organization
RUNNER_SCOPE=org

# For repository runner:
REPO_URL=https://github.com/your-org/your-repo
RUNNER_SCOPE=repo

# Custom labels for targeting in workflows
RUNNER_LABELS=docker,48-core
```

### Step 4: Start the Runner

```bash
# Start single runner
docker compose up -d

# View logs to verify registration
docker compose logs -f runner
```

**Expected output:**

```text
Runner successfully registered
Runner is listening for jobs...
```

### Step 5: Verify Registration in GitHub

#### For Organization Runners

1. Go to `https://github.com/YOUR-ORG/settings/actions/runners`
2. Your runner should appear as **"Idle"** with labels:
   - `self-hosted`
   - `linux`
   - `x64`
   - `docker`
   - `48-core`

#### For Repository Runners

1. Go to `https://github.com/YOUR-ORG/YOUR-REPO/settings/actions/runners`
2. Verify runner status is **"Idle"**

### Step 6: Scale Runners (Optional)

```bash
# Run 4 parallel runners (sharing one DinD instance)
docker compose up -d --scale runner=4

# Check all runners
docker compose ps
```

## Organization-Wide Runner Setup

Configure your runner to be available for **all repositories** in your organization.

### Runner Group Configuration

1. Go to `https://github.com/YOUR-ORG/settings/actions/runner-groups`
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
REPO_URL=https://github.com/your-org
```

### Using in Workflows

Once configured, all repositories in your organization can use the runner:

```yaml
# .github/workflows/build.yml
name: Build

on: [push, pull_request]

jobs:
  build:
    # Use self-hosted runner from your group
    runs-on: [self-hosted, docker]
    steps:
      - uses: actions/checkout@v4
      - run: echo "Running on self-hosted runner!"
```

### Optional: Disable GitHub-Hosted Runners

To enforce using only your self-hosted runners:

1. Go to `https://github.com/YOUR-ORG/settings/actions`
2. Under **"Runners"**, uncheck:
   - ☐ Allow GitHub-hosted runners

Now all workflows **must** use your self-hosted runners.

### Verify Access

Check that your runner appears in the group:

1. Go to `https://github.com/YOUR-ORG/settings/actions/runner-groups`
2. Click on your group (**"Self-Hosted (BAUER GROUP)"**)
3. Your runner should be listed with status **"Idle"**

## Configuration

### Key Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_ACCESS_TOKEN` | PAT with admin scopes | **Required** |
| `REPO_URL` | Target org/repo URL | **Required** |
| `RUNNER_SCOPE` | `org` or `repo` | `org` |
| `RUNNER_LABELS` | Additional labels (default: self-hosted, linux, x64) | `docker,48-core` |

### Resource Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `DIND_MEMORY_LIMIT` | `32g` | DinD container memory |
| `DIND_CPU_LIMIT` | `16` | DinD container CPUs |
| `RUNNER_MEMORY_LIMIT` | `32g` | Runner container memory |
| `RUNNER_CPU_LIMIT` | `16` | Runner container CPUs |

## Usage in Workflows

### Basic Usage

Target your self-hosted runner using labels in `runs-on`:

```yaml
jobs:
  build:
    runs-on: [self-hosted, docker, 48-core]
    steps:
      - uses: actions/checkout@v4
      - run: echo "Running on self-hosted runner!"
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
    runs-on: [self-hosted, docker]
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
    runs-on: [self-hosted, docker]
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
    runs-on: [self-hosted, docker, 48-core]
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
    runs-on: [self-hosted, docker]
    strategy:
      matrix:
        node: [18, 20, 22]
    steps:
      - uses: actions/checkout@v4

      - name: Build for Node ${{ matrix.node }}
        run: docker build --build-arg NODE_VERSION=${{ matrix.node }} -t myapp:node${{ matrix.node }} .
```

### Best Practices

1. **Always use `if: always()` for cleanup steps** - ensures containers are removed even on failure
2. **Use specific labels** - `[self-hosted, docker]` instead of just `[self-hosted]`
3. **Don't store secrets in images** - use GitHub Secrets and environment variables
4. **Clean up after tests** - `docker compose down -v` removes volumes too
5. **Use BuildKit** - faster builds with better caching (enabled by default)

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

Use the scale script to manage runner instances:

**Linux/macOS:**

```bash
# Start with 1 runner (default)
./scripts/scale.sh

# Scale to 4 runners
./scripts/scale.sh 4

# Scale to 8 runners
./scripts/scale.sh 8

# Scale back down
./scripts/scale.sh 2
```

**Windows (via Tools Container):**

```powershell
.\tools\run.ps1 -Script "./scripts/scale.sh 4"
```

**Or use Docker Compose directly:**

```bash
docker compose up -d --scale runner=4
```

All runners share a single DinD instance (shared Docker cache for faster builds).

## Maintenance

### Available Scripts

| Script | Description |
|--------|-------------|
| `./scripts/setup-env.sh` | Interactive environment configuration |
| `./scripts/start.sh [N]` | Start runners (N = number, default 1) |
| `./scripts/stop.sh` | Stop all runners |
| `./scripts/status.sh` | Show status and resource usage |
| `./scripts/scale.sh N` | Scale to N runners |
| `./scripts/cleanup.sh` | Cleanup Docker resources |

**Windows users:** Run scripts via tools container:

```powershell
.\tools\run.ps1 -Script "./scripts/start.sh 4"
```

### View Logs

```bash
# All services
docker compose logs -f

# Runner only
docker compose logs -f runner

# DinD only
docker compose logs -f docker-in-docker
```

### Cleanup

**Linux/macOS:**

```bash
# Basic cleanup (remove work directories)
./scripts/cleanup.sh

# Full cleanup (including volumes and images)
./scripts/cleanup.sh --full
```

**Windows (via Tools Container):**

```powershell
# Basic cleanup
.\tools\run.ps1 -Script "./scripts/cleanup.sh"

# Full cleanup
.\tools\run.ps1 -Script "./scripts/cleanup.sh --full"
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
3. View logs: `docker compose logs runner`

### Docker Commands Failing in Workflows

1. Verify DinD is healthy: `docker compose ps`
2. Check DinD logs: `docker compose logs docker-in-docker`
3. Ensure `DOCKER_HOST` is set correctly

### Out of Disk Space

```bash
# Clean up old images and containers
./scripts/cleanup.sh --full

# Or manually inside DinD
docker compose exec docker-in-docker docker system prune -af
```

### Runner Keeps Restarting

With `EPHEMERAL=true`, runners restart after each job. This is expected behavior.

To check if it's working correctly:

```bash
docker compose logs -f runner | grep -E "(Listening|Running|Removing)"
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
│   ├── setup-env.sh
│   ├── start.sh
│   ├── stop.sh
│   ├── status.sh
│   ├── scale.sh
│   └── cleanup.sh
├── tools/
│   ├── Dockerfile
│   ├── run.sh
│   ├── run.ps1
│   └── run.cmd
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
