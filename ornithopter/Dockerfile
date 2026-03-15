FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install uv (as root)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install Claude Code globally via npm
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user (Claude Code refuses --dangerously-skip-permissions as root)
RUN useradd -m -s /bin/bash researcher
ENV PATH="/home/researcher/.local/bin:$PATH"

# Set up project
WORKDIR /app

# Install Python deps first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync

# Copy source files
COPY design.py simulate.py evaluate.py visualize.py program.md build_details.md results.tsv CLAUDE.md ./

# Create results mount point
RUN mkdir -p /app/results

# Create a script that syncs results.tsv to the mounted volume
RUN printf '#!/bin/sh\ncp -f /app/results.tsv /app/results/ 2>/dev/null\ncp -f /app/sim_output.json /app/results/ 2>/dev/null\ncp -f /app/run.log /app/results/ 2>/dev/null\n' > /app/sync-results.sh \
    && chmod +x /app/sync-results.sh

# Hand ownership to researcher and switch user
RUN chown -R researcher:researcher /app
USER researcher

# Install uv for the researcher user too
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Init git for experiment loop
RUN git config --global user.name "auto-ornithopter" && \
    git config --global user.email "auto-ornithopter@local" && \
    git init && \
    git add -A && \
    git commit -m "initial baseline"

CMD ["claude", "--dangerously-skip-permissions"]
