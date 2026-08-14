"""Versioned API router. Feature routers mount here as modules land."""

from fastapi import APIRouter

from aegis_api.api.v1 import (
    alerts,
    audit,
    notifications,
    invites,
    workspaces,
    assets,
    auth,
    digitaltwin,
    health,
    incidents,
    missioniq,
    missions,
    quantum,
    reports,
    sentinel,
    sso,
    threatintel,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(sso.router)
api_router.include_router(users.router)
api_router.include_router(workspaces.router)
api_router.include_router(invites.router)
api_router.include_router(audit.router)
api_router.include_router(notifications.router)
api_router.include_router(notifications.prefs_router)
api_router.include_router(assets.router)
api_router.include_router(missions.router)
api_router.include_router(alerts.router)
api_router.include_router(incidents.router)
api_router.include_router(quantum.router)
api_router.include_router(missioniq.router)
api_router.include_router(sentinel.router)
api_router.include_router(threatintel.router)
api_router.include_router(reports.router)
api_router.include_router(digitaltwin.router)
