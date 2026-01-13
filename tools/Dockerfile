# =============================================================================
# Development Tools Container
# Provides Unix/bash environment for running scripts on Windows hosts
# =============================================================================

FROM alpine:3

# Install required tools
RUN apk add --no-cache \
    # Shell
    bash \
    # Core utilities
    coreutils \
    grep \
    sed \
    # Docker CLI (to interact with host Docker)
    docker-cli \
    docker-cli-compose \
    # Useful extras
    curl \
    jq \
    git \
    ca-certificates

# Set bash as default shell
SHELL ["/bin/bash", "-c"]

# Working directory (will be mounted from host)
WORKDIR /workspace

# Default command: interactive bash
CMD ["/bin/bash"]
