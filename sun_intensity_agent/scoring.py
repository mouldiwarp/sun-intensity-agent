import math
from datetime import datetime
from typing import Any, Dict, List

from .constants import SCORE_MAX, SCORE_SCALE, CLEAR_SKY_SCALE, TIMEZONE_UTC_OFFSET


def _format_timestamp(epoch_seconds: int) -> str:
    """Format Unix epoch timestamp as ISO 8601 string with UTC offset."""
    return datetime.utcfromtimestamp(epoch_seconds).isoformat() + TIMEZONE_UTC_OFFSET


def _calculate_fallback_score(daily_clouds: int) -> int:
    """Calculate fallback score when no hourly data available."""
    return round(SCORE_SCALE - daily_clouds)


def _calculate_weighted_score(
    daylight_hours_list: List[Dict[str, Any]], sunrise_epoch: int, daylight_duration: int
) -> int:
    """
    Calculate weighted sun intensity score from hourly forecast.

    Args:
        daylight_hours_list: Hourly forecasts within daylight window
        sunrise_epoch: Sunrise time (Unix epoch)
        daylight_duration: Duration of daylight in seconds

    Returns:
        Score from 0-100
    """
    total_weight = 0.0
    weighted_clear_sky = 0.0

    for hour in daylight_hours_list:
        clouds_pct = hour.get("clouds", 0)
        clear_sky = 1 - (clouds_pct / CLEAR_SKY_SCALE)

        # Sine weighting: peaks at solar noon, tapers at sunrise/sunset
        normalized_time = (hour["dt"] - sunrise_epoch) / daylight_duration
        weight = math.sin(math.pi * normalized_time)

        total_weight += weight
        weighted_clear_sky += weight * clear_sky

    if total_weight > 0:
        avg_clear_sky = weighted_clear_sky / total_weight
        return round(SCORE_SCALE * avg_clear_sky)
    else:
        return SCORE_MAX


def _calculate_avg_cloud_cover(daylight_hours_list: List[Dict[str, Any]], daily_clouds: int) -> float:
    """Calculate average cloud cover percentage."""
    if daylight_hours_list:
        return sum(h.get("clouds", 0) for h in daylight_hours_list) / len(daylight_hours_list)
    return daily_clouds


def compute_score(daily: List[Dict[str, Any]], hourly: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute sun intensity score (0-100) for tomorrow's forecast.

    Args:
        daily: Daily forecast array (daily[0] = today, daily[1] = tomorrow)
        hourly: Hourly forecast array (next 48 hours)

    Returns:
        Dict with score, sunrise, sunset, daylight_hours, avg_cloud_cover_pct, and date.

    Raises:
        ValueError: If insufficient data or invalid timestamps
    """
    if not daily or len(daily) < 2:
        raise ValueError("Need at least 2 days of daily forecast data")

    tomorrow = daily[1]
    sunrise_epoch = tomorrow["sunrise"]
    sunset_epoch = tomorrow["sunset"]
    daylight_duration = sunset_epoch - sunrise_epoch

    if daylight_duration <= 0:
        raise ValueError("Invalid sunrise/sunset times")

    daylight_hours = daylight_duration / 3600

    # Filter hourly to those within tomorrow's daylight window
    daylight_hours_list = [
        h for h in hourly
        if sunrise_epoch <= h["dt"] < sunset_epoch
    ]

    # Calculate score
    if daylight_hours_list:
        score = _calculate_weighted_score(daylight_hours_list, sunrise_epoch, daylight_duration)
    else:
        daily_clouds = tomorrow.get("clouds", 0)
        score = _calculate_fallback_score(daily_clouds)

    # Calculate average cloud cover
    daily_clouds = tomorrow.get("clouds", 0)
    avg_clouds = _calculate_avg_cloud_cover(daylight_hours_list, daily_clouds)

    return {
        "date": datetime.utcfromtimestamp(sunrise_epoch).date().isoformat(),
        "sunrise": _format_timestamp(sunrise_epoch),
        "sunset": _format_timestamp(sunset_epoch),
        "daylight_hours": round(daylight_hours, 2),
        "score": score,
        "score_description": "0-100; higher = clearer skies / more solar potential expected tomorrow",
        "avg_cloud_cover_pct": round(avg_clouds, 1),
    }
