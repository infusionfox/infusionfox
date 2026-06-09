FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps (minimal)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Create a non-root user and a data dir the user can write to.
# Non-root user for the running container.
# persistent-volume file ownership) — same continuity reasoning as the DB
# filename. The brand is InfusionFox; this is a system user inside the
# container, not user-visible.
RUN useradd --create-home --shell /bin/bash infusionfox \
    && mkdir -p /data \
    && chown infusionfox:infusionfox /data

COPY --chown=infusionfox:infusionfox . .

USER infusionfox

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["/app/scripts/entrypoint.sh"]
