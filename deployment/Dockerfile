# Multi-stage production Dockerfile for ALD Control System
# Optimized for security, performance, and minimal attack surface

# Build stage - for dependencies and compilation
FROM python:3.9-slim as builder

LABEL maintainer="ALD Control System Team"
LABEL version="1.0"
LABEL description="Production-ready ALD Control System"

# Security: Create non-root user early
RUN groupadd -r ald && useradd -r -g ald ald

# Set working directory
WORKDIR /build

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
COPY requirements-prod.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-prod.txt

# Production stage - minimal runtime image
FROM python:3.9-slim as production

# Security: Use non-root user
RUN groupadd -r ald && useradd -r -g ald ald

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=ald:ald src/ ./src/
COPY --chown=ald:ald main.py ./
COPY --chown=ald:ald CLAUDE.md ./

# Create required directories
RUN mkdir -p /app/logs /app/data /app/config && \
    chown -R ald:ald /app

# Security: Remove unnecessary packages and clean up
RUN apt-get autoremove -y && \
    apt-get autoclean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Switch to non-root user
USER ald

# Expose application port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command
CMD ["python", "main.py"]

# Metadata labels
LABEL org.opencontainers.image.title="ALD Control System"
LABEL org.opencontainers.image.description="Production-ready Atomic Layer Deposition Control System"
LABEL org.opencontainers.image.vendor="ALD Control System Team"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/your-org/ald-control-system"