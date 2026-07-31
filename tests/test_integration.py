"""
Integration tests with mock OWM data.
Verifies the complete flow from raw OWM response to final score JSON.
"""
import pytest
from datetime import datetime, timedelta
from sun_intensity_agent.scoring import compute_score


def create_owm_response_clear_day():
    """Create a mock OWM response for a clear day."""
    now = datetime.utcnow()
    tomorrow = now + timedelta(days=1)
    tomorrow_start = int(tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    sunrise = tomorrow_start + 6 * 3600  # 6 AM UTC
    sunset = tomorrow_start + 18 * 3600   # 6 PM UTC

    daily = [
        {
            "sunrise": sunrise,
            "sunset": sunset,
            "clouds": 0,
            "temp": {"day": 25, "night": 15},
        },
        {
            "sunrise": sunrise,
            "sunset": sunset,
            "clouds": 0,
            "temp": {"day": 26, "night": 14},
        },
    ]

    hourly = []
    for i in range(12):
        hourly.append({
            "dt": sunrise + i * 3600,
            "temp": 20 + i,
            "clouds": 0,
            "wind_speed": 5,
            "humidity": 60,
        })

    return {"daily": daily, "hourly": hourly}


def create_owm_response_overcast_day():
    """Create a mock OWM response for an overcast day."""
    now = datetime.utcnow()
    tomorrow = now + timedelta(days=1)
    tomorrow_start = int(tomorrow.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    sunrise = tomorrow_start + 6 * 3600
    sunset = tomorrow_start + 18 * 3600

    daily = [
        {"sunrise": sunrise, "sunset": sunset, "clouds": 100},
        {"sunrise": sunrise, "sunset": sunset, "clouds": 100},
    ]

    hourly = []
    for i in range(12):
        hourly.append({
            "dt": sunrise + i * 3600,
            "temp": 18,
            "clouds": 100,
            "wind_speed": 8,
            "humidity": 85,
        })

    return {"daily": daily, "hourly": hourly}


def test_integration_clear_day():
    """Test complete flow: OWM response -> score."""
    owm_data = create_owm_response_clear_day()
    result = compute_score(owm_data["daily"], owm_data["hourly"])

    assert result["score"] == 100
    assert result["avg_cloud_cover_pct"] == 0.0
    assert "sunrise" in result
    assert "sunset" in result
    assert "date" in result
    assert result["daylight_hours"] > 10


def test_integration_overcast_day():
    """Test complete flow: OWM response -> score."""
    owm_data = create_owm_response_overcast_day()
    result = compute_score(owm_data["daily"], owm_data["hourly"])

    assert result["score"] == 0
    assert result["avg_cloud_cover_pct"] == 100.0
    assert "sunrise" in result
    assert "sunset" in result


def test_response_structure():
    """Verify response has all required fields for downstream integration."""
    owm_data = create_owm_response_clear_day()
    result = compute_score(owm_data["daily"], owm_data["hourly"])

    # Core fields for downstream agent
    assert "score" in result
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100

    # Context fields
    assert "location" not in result  # Added by core.py, not scoring.py
    assert "date" in result
    assert "sunrise" in result
    assert "sunset" in result
    assert "daylight_hours" in result
    assert "avg_cloud_cover_pct" in result
    assert "score_description" in result

    # Format checks
    assert "T" in result["sunrise"] and "+00:00" in result["sunrise"]
    assert "T" in result["sunset"] and "+00:00" in result["sunset"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
