# Run the bot in a container. Build: docker build -t mika .
# Run:   docker compose up -d   (reads your .env, persists data in ./var)
FROM python:3.12-slim

# Codex backend (MIKA_LLM_PROVIDER=codex) needs node + the Codex CLI + the ACP
# adapter in the image. Off by default: it adds ~200MB nobody else needs.
#   docker compose build --build-arg INSTALL_CODEX=true
ARG INSTALL_CODEX=false

# uv: the fast Python toolchain, pinned via the lockfile for reproducible builds.
RUN pip install --no-cache-dir uv

RUN if [ "$INSTALL_CODEX" = "true" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends nodejs npm ca-certificates && \
        rm -rf /var/lib/apt/lists/* && \
        npm install -g @openai/codex @agentclientprotocol/codex-acp && \
        npm cache clean --force; \
    fi

WORKDIR /app

# Install dependencies first (cached unless the lockfile changes).
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY config ./config
RUN if [ "$INSTALL_CODEX" = "true" ]; then \
        uv sync --no-dev --frozen --extra codex; \
    else \
        uv sync --no-dev --frozen; \
    fi

ENV PATH="/app/.venv/bin:$PATH"

# Conversation memory and logs live here - mount a volume to persist them.
VOLUME ["/app/var"]

# Configuration comes from environment variables (see .env / docker-compose.yml).
CMD ["mika", "run"]
