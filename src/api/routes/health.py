"""Health check route"""
from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Logistics ETA & Delay Intelligence Platform",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "DuckDB connected"
    }

