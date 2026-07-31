from fastapi import FastAPI, Query, HTTPException
from typing import Optional, Dict, Any

from .core import get_score
from .errors import get_http_status_code
from .constants import HTTP_STATUS_SERVER_ERROR

app = FastAPI(title="Sun Intensity Agent")


@app.get("/score")
async def score(lat: Optional[float] = Query(None), lon: Optional[float] = Query(None)) -> Dict[str, Any]:
    """
    Get tomorrow's sun intensity score (0-100).

    Query parameters:
    - lat: Latitude (optional, uses LAT env var if not provided)
    - lon: Longitude (optional, uses LON env var if not provided)

    Returns:
        JSON response with sun intensity score and metadata
    """
    try:
        return get_score(lat=lat, lon=lon)
    except Exception as e:
        status_code = get_http_status_code(e)
        raise HTTPException(status_code=status_code, detail=str(e))


@app.get("/health")
async def health() -> Dict[str, str]:
    """
    Health check endpoint.

    Returns:
        JSON response indicating service status
    """
    return {"status": "ok"}
