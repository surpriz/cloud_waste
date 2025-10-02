"""API v1 router configuration."""

from fastapi import APIRouter

from app.api.v1 import accounts, auth, detection_rules, resources, scans

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["cloud-accounts"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(resources.router, prefix="/resources", tags=["resources"])
api_router.include_router(detection_rules.router, prefix="/detection-rules", tags=["detection-rules"])

# Future routers:
# api_router.include_router(costs.router, prefix="/costs", tags=["costs"])
