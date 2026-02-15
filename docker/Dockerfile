FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy project metadata and install dependencies
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
RUN pip install --no-cache-dir .

# Production image
FROM python:3.12-slim

WORKDIR /app

# Non-root user for security
RUN groupadd --gid 1000 spvwallet && \
    useradd --uid 1000 --gid spvwallet --shell /bin/bash --create-home spvwallet && \
    apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=base /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=base /usr/local/bin/py-spv /usr/local/bin/py-spv
COPY --from=base /app/src /app/src
COPY alembic/ /app/alembic/

RUN mkdir -p /data && chown spvwallet:spvwallet /data

USER spvwallet

ENV SPVWALLET_DB__ENGINE=sqlite
ENV SPVWALLET_DB__DSN=sqlite+aiosqlite:////data/spv_wallet.db

EXPOSE 3003
EXPOSE 9090

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:3003/health || exit 1

ENTRYPOINT ["py-spv"]
