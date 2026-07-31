from datetime import datetime
from typing import Any, Optional, Dict

from .config import get_settings
from .owm_client import fetch_forecast
from .scoring import compute_score


def get_score(lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
    """
    Orchestrator: fetch OWM data, compute score, return result envelope.

    Args:
        lat: Override latitude from env var
        lon: Override longitude from env var

    Returns:
        Dict with score, location, sunrise, sunset, and metadata.

    Raises:
        OWMAuthError, OWMRateLimitError, OWMRequestError, ValueError
    """
    settings = get_settings()
    final_lat, final_lon = settings.validate_location(lat, lon)

    data = fetch_forecast(settings.owm_api_key, final_lat, final_lon)
    result = compute_score(data["daily"], data["hourly"])

    result["location"] = {"lat": final_lat, "lon": final_lon}
    result["generated_at"] = datetime.utcnow().isoformat() + "+00:00"

    return result
