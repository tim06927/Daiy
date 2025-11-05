# Dev container configuration for Node.js, Python, Playwright, and Postgres
FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# Install Node.js (LTS), Python, Playwright, and Postgres
RUN apt-get update && \
    apt-get install -y curl python3 python3-pip python3-venv postgresql postgresql-contrib && \
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g playwright && \
    playwright install --with-deps

# Set up a non-root user (optional, recommended for dev containers)
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*

USER $USERNAME

# Expose Postgres default port
EXPOSE 5432
