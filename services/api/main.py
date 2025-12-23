"""Main FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import Config

# Import routers
from routers import campaigns, emails, recipients

# Validate config on startup
Config.validate()

app = FastAPI(
    title="Campaign API",
    description="Unified API service for campaign management",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[Config.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["campaigns"])
app.include_router(emails.router, prefix="/api/v1/campaigns", tags=["emails"])
app.include_router(recipients.router, prefix="/api/v1/campaigns", tags=["recipients"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

