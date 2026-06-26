# Run the bot in a container. Build: docker build -t mika .
# Run:   docker compose up -d   (reads your .env, persists data in ./var)
FROM python:3.12-slim

# uv: the fast Python toolchain, pinned via the lockfile for reproducible builds.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Install dependencies first (cached unless the lockfile changes).
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY config ./config
RUN uv sync --no-dev --frozen

ENV PATH="/app/.venv/bin:$PATH"

# Conversation memory and logs live here - mount a volume to persist them.
VOLUME ["/app/var"]

# Configuration comes from environment variables (see .env / docker-compose.yml).
CMD ["mika", "run"]
