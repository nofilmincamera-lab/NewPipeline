"""
Playwright Service - FastAPI endpoint for browser automation
Minimal service for Tier 1 (will be enhanced for Tier 2/3)
"""

from fastapi import FastAPI
from datetime import datetime

app = FastAPI(
    title="Playwright Browser Pool",
    description="Browser automation service",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "playwright-pool"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Playwright Browser Pool",
        "version": "1.0.0",
        "status": "running"
    }

# Note: Full scraping endpoints will be added in Tier 2/3
# Tier 1 uses curl_cffi, not Playwright
