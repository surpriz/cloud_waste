"""FastAPI Application Entry Point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="CloudWaste - Detect and identify orphaned cloud resources",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", tags=["health"])
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": settings.APP_NAME,
            "environment": settings.APP_ENV,
        },
    )


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Welcome to CloudWaste API",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }


# Include routers (will be added in future sprints)
# from app.api.v1 import auth, accounts, scans, resources, costs
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
# app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["accounts"])
# app.include_router(scans.router, prefix="/api/v1/scans", tags=["scans"])
# app.include_router(resources.router, prefix="/api/v1/resources", tags=["resources"])
# app.include_router(costs.router, prefix="/api/v1/costs", tags=["costs"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
