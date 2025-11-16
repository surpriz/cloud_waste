"""API v1 router configuration."""

from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    admin,
    admin_pricing,
    auth,
    chat,
    detection_rules,
    gdpr,
    impact,
    inventory,
    resources,
    scans,
    test_detection,
    test_sentry,
    user_preferences,
)

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["cloud-accounts"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(resources.router, prefix="/resources", tags=["resources"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["cost-intelligence"])
api_router.include_router(detection_rules.router, prefix="/detection-rules", tags=["detection-rules"])
api_router.include_router(impact.router, prefix="/impact", tags=["impact-savings"])
api_router.include_router(chat.router, prefix="/chat", tags=["ai-assistant"])
api_router.include_router(user_preferences.router, prefix="/preferences", tags=["user-preferences"])
api_router.include_router(gdpr.router, prefix="/gdpr", tags=["gdpr-compliance"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_pricing.router, prefix="/admin", tags=["admin-pricing"])
api_router.include_router(test_detection.router, prefix="", tags=["testing"])  # Test endpoints at root /api/v1/test/...
api_router.include_router(test_sentry.router, prefix="", tags=["testing"])  # Sentry test endpoints at root /api/v1/test/sentry/...

# Future routers:
# api_router.include_router(costs.router, prefix="/costs", tags=["costs"])
