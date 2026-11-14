"""FastAPI Main Application Entry Point
Logistics ETA Prediction & Delay Intelligence Platform
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.dependencies import get_cached_data, get_repository, get_predictor
from src.api.routes import (
    health,
    dashboard,
    shipments,
    predictions,
    anomalies,
    exceptions,
    analytics,
    carriers,
    facilities,
    weather,
    routes_api,
    validation,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm cached data and model service
    print("Pre-warming application cache and analytical storage...")
    get_cached_data()
    get_repository()
    get_predictor()
    print("Application successfully initialized and ready for requests.")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Enterprise API for logistics ETA forecasting, delay risk classification, anomaly detection, and operational exceptions.",
    lifespan=lifespan
)

# Enable CORS for local dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route modules (both with API prefix and root for direct convenience)
app.include_router(health.router)
app.include_router(dashboard.router, prefix=settings.api_prefix)
app.include_router(shipments.router, prefix=settings.api_prefix)
app.include_router(shipments.router)
app.include_router(predictions.router, prefix=settings.api_prefix)
app.include_router(anomalies.router, prefix=settings.api_prefix)
app.include_router(exceptions.router, prefix=settings.api_prefix)
app.include_router(analytics.router, prefix=settings.api_prefix)
app.include_router(analytics.router)
app.include_router(carriers.router, prefix=settings.api_prefix)
app.include_router(carriers.router)
app.include_router(facilities.router, prefix=settings.api_prefix)
app.include_router(facilities.router)
app.include_router(weather.router, prefix=settings.api_prefix)
app.include_router(weather.router)
app.include_router(routes_api.router, prefix=settings.api_prefix)
app.include_router(routes_api.router)
app.include_router(validation.router, prefix=settings.api_prefix)
app.include_router(validation.router)


@app.get("/")
def root():
    return {
        "service": settings.app_name,
        "version": settings.version,
        "docs_url": "/docs",
        "health_check": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

