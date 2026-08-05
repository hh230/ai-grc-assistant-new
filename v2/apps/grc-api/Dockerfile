# grc-api — the Rasheed V1 Product API Host (ADR 0052).
#
# Deliberately plain: one Dockerfile that any container host runs (Railway, Render, Fly, Cloud Run,
# ECS). No platform-specific manifest, because the hosting decision is still open and a Dockerfile
# is the portable form of it.
#
# BUILD CONTEXT IS `v2/`, not this directory — grc-api depends on ~20 sibling packages via
# `[tool.uv.sources]` path entries (`../../packages/*`), so a context rooted here cannot see them:
#
#     docker build -f apps/grc-api/Dockerfile -t rasheed-grc-api v2/
#
# The migrations ship inside the image (see `grc_api.migrate`) so the release step needs nothing
# from the repository at run time.

FROM python:3.12-slim AS base

# psycopg[binary] ships its own libpq, so no build toolchain is needed. curl is here for the
# platform health check; several hosts probe with it rather than with their own client.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

# The whole v2 workspace: the app plus every path dependency it resolves. Copied in one layer
# because the path deps are editable installs — splitting them from the lockfile step would just
# invalidate the cache on any package change anyway.
COPY packages/ /srv/packages/
COPY apps/grc-api/ /srv/apps/grc-api/

WORKDIR /srv/apps/grc-api

# --frozen: build from the committed lock, never silently resolve something new at image time.
# --no-dev: the production path only (see the dependency-group comment in pyproject.toml).
RUN uv sync --frozen --no-dev

# Run as a non-root user. Nothing here writes to the filesystem, so the whole tree stays read-only
# to the process that serves traffic.
RUN useradd --create-home --uid 10001 rasheed && chown -R rasheed:rasheed /srv
USER rasheed

ENV PATH="/srv/apps/grc-api/.venv/bin:${PATH}"

# The platform supplies PORT (Railway/Render/Cloud Run all do); 8000 is the local default.
ENV PORT=8000
EXPOSE 8000

# `/health` is LIVENESS — process up, no dependencies touched. Deliberately not `/health/ready`,
# which also checks Postgres: a readiness failure must not make the platform restart a container
# that is running perfectly well while the database is briefly slow. Point the PLATFORM's readiness
# probe (Railway/Render/Cloud Run) at `/health/ready`, and its restart policy at this one.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

# Migrations are a RELEASE step, not a start step: run `python -m grc_api.migrate` once per deploy
# (Railway `releaseCommand`, Render `preDeployCommand`, a Cloud Run Job). Doing it here would race
# every replica against every other on scale-out.
CMD ["sh", "-c", "exec uvicorn grc_api.app:create_app --factory --host 0.0.0.0 --port ${PORT}"]
