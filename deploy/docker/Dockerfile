# Dockerfile for hugr — runs `hugr server`.
#
# Volumes:
#   /config  -> $XDG_CONFIG_HOME (master + per-tool configs)
#   /data    -> $HUGR_HOME      (DB, caches, sessions)
#   /state   -> $HUGR_STATE_DIR (the damsleth/hugr-state clone)
#
# Build:
#   docker build -t ghcr.io/damsleth/hugr:dev -f deploy/docker/Dockerfile .
#
# Run (loopback, no auth):
#   docker run --rm -it -p 7777:7777 \
#     -v hugr-config:/config -v hugr-data:/data -v hugr-state:/state \
#     ghcr.io/damsleth/hugr:dev
#
# Behind Cloudflare Access / tailscale: pass HUGR_AUTH_PROXY=cloudflare
# (or tailscale) and bind --host 0.0.0.0; hugr server refuses
# non-loopback binds without one of the recognized proxies.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    XDG_CONFIG_HOME=/config \
    HUGR_HOME=/data \
    HUGR_STATE_DIR=/state

# System deps:
#   git   -> hugr sync push/pull
#   age   -> hugr sync encrypt/decrypt
#   curl  -> healthcheck
#   sqlite3 -> yaams DB ops
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git age curl sqlite3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the metadata first so dependency installs cache cleanly.
COPY pyproject.toml README.md ./
COPY src ./src

# Install with the server surfaces (web, server). TUI is omitted
# in the server image; install [all] locally if you want it.
RUN pip install --upgrade pip \
    && pip install ".[server,web]"

VOLUME ["/config", "/data", "/state"]

EXPOSE 7777

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:7777/healthz || exit 1

# Default to loopback bind. Use docker run -e HUGR_AUTH_PROXY=... and
# pass --host 0.0.0.0 in CMD if running behind a recognized proxy.
CMD ["hugr", "server", "--host", "0.0.0.0", "--port", "7777"]
