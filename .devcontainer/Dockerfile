# Dev container configuration for Node.js, Python, Playwright, and Postgres
FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# Install Node.js (LTS), Python, Playwright, and Postgres
RUN apt-get update && \
    apt-get install -y curl python3 python3-pip python3-venv postgresql postgresql-contrib sudo && \
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g playwright && \
    playwright install --with-deps && \
    apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Configure PostgreSQL
RUN mkdir -p /var/run/postgresql && \
    chown -R postgres:postgres /var/run/postgresql && \
    chmod 2777 /var/run/postgresql

# Give vscode user sudo access for postgres commands
RUN echo "vscode ALL=(postgres) NOPASSWD: ALL" >> /etc/sudoers.d/vscode && \
    chmod 0440 /etc/sudoers.d/vscode

# Expose Postgres default port
EXPOSE 5432
