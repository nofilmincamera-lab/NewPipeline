FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

LABEL maintainer="Joshua - BPO Intelligence"
LABEL description="Playwright Browser Pool with FastAPI service"

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
RUN pip install --no-cache-dir \
    playwright==1.48.0 \
    playwright-stealth==1.0.5 \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    pydantic==2.9.2 \
    loguru==0.7.3

# Create service file
COPY docker/playwright/service.py /app/service.py

# Create non-root user (check if exists first)
RUN if ! id -u 1000 > /dev/null 2>&1; then \
        useradd -m -u 1000 playwright; \
    else \
        usermod -a -G $(id -gn 1000) $(id -un 1000) || true; \
    fi && \
    chown -R 1000:1000 /app

USER 1000

# Expose service port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Start FastAPI service
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "3000", "--workers", "4"]
