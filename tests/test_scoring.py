import pytest
from datetime import datetime, timedelta
import math

from sun_intensity_agent.scoring import compute_score


def test_clear_sky_day():
    """Test with a fully clear day (0% clouds)."""
    now = datetime.utcnow()
    today = int(now.timestamp())
    tomorrow_date = now + timedelta(days=1)
    tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    sunrise = tomorrow_start + 6 * 3600  # 6 AM UTC
    sunset = tomorrow_start + 18 * 3600  # 6 PM UTC (12 hours daylight)

    daily = [
        {"sunrise": sunrise, "sunset": sunset, "clouds": 0},  # today
        {"sunrise": sunrise, "sunset": sunset, "clouds": 0},  # tomorrow
    ]

    hourly = []
    for i in range(12):  # 12 hours from sunrise to sunset
        dt = sunrise + i * 3600
        hourly.append({"dt": dt, "clouds": 0})

    result = compute_score(daily, hourly)

    # Clear day should score near 100
    assert result["score"] == 100
    assert result["avg_cloud_cover_pct"] == 0.0


def test_overcast_day():
    """Test with a fully overcast day (100% clouds)."""
    now = datetime.utcnow()
    tomorrow_date = now + timedelta(days=1)
    tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    sunrise = tomorrow_start + 6 * 3600
    sunset = tomorrow_start + 18 * 3600

    daily = [
        {"sunrise": sunrise, "sunset": sunset, "clouds": 100},
        {"sunrise": sunrise, "sunset": sunset, "clouds": 100},
    ]

    hourly = []
    for i in range(12):
        dt = sunrise + i * 3600
        hourly.append({"dt": dt, "clouds": 100})

    result = compute_score(daily, hourly)

    # Overcast day should score 0
    assert result["score"] == 0
    assert result["avg_cloud_cover_pct"] == 100.0


def test_partly_cloudy_midday_vs_dawn():
    """
    Test that midday cloud cover matters more than dawn/dusk.
    Scenario 1: 50% clouds at midday only
    Scenario 2: 50% clouds at sunrise/sunset only
    Scenario 1 should score lower (worse) than Scenario 2.
    """
    now = datetime.utcnow()
    tomorrow_date = now + timedelta(days=1)
    tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    sunrise = tomorrow_start + 6 * 3600  # 6 AM
    sunset = tomorrow_start + 18 * 3600  # 6 PM

    daily = [
        {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
        {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
    ]

    # Scenario 1: 50% clouds only at midday (hours 5-7, i.e., 11 AM - 1 PM)
    hourly_scenario1 = []
    for i in range(12):
        dt = sunrise + i * 3600
        clouds = 50 if 5 <= i <= 7 else 0
        hourly_scenario1.append({"dt": dt, "clouds": clouds})

    result1 = compute_score(daily, hourly_scenario1)

    # Scenario 2: 50% clouds only at dawn/dusk (hours 0-1 and 10-11)
    hourly_scenario2 = []
    for i in range(12):
        dt = sunrise + i * 3600
        clouds = 50 if i <= 1 or i >= 10 else 0
        hourly_scenario2.append({"dt": dt, "clouds": clouds})

    result2 = compute_score(daily, hourly_scenario2)

    # Midday clouds should hurt more, so scenario1 score should be lower
    assert result1["score"] < result2["score"]


def test_no_hourly_data_fallback():
    """Test fallback when no hourly data exists in daylight window."""
    now = datetime.utcnow()
    tomorrow_date = now + timedelta(days=1)
    tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    sunrise = tomorrow_start + 6 * 3600
    sunset = tomorrow_start + 18 * 3600

    daily = [
        {"sunrise": sunrise, "sunset": sunset, "clouds": 30},
        {"sunrise": sunrise, "sunset": sunset, "clouds": 30},
    ]

    hourly = []  # Empty hourly data

    result = compute_score(daily, hourly)

    # Fallback: 100 - clouds = 100 - 30 = 70
    assert result["score"] == 70


def test_sunrise_sunset_times_formatted():
    """Test that sunrise/sunset are formatted as ISO strings."""
    now = datetime.utcnow()
    tomorrow_date = now + timedelta(days=1)
    tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    sunrise = tomorrow_start + 6 * 3600
    sunset = tomorrow_start + 18 * 3600

    daily = [
        {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
        {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
    ]

    hourly = [{"dt": sunrise + i * 3600, "clouds": 0} for i in range(12)]

    result = compute_score(daily, hourly)

    # Check format: should contain "T" and "+00:00"
    assert "T" in result["sunrise"]
    assert "+00:00" in result["sunrise"]
    assert "T" in result["sunset"]
    assert "+00:00" in result["sunset"]


class TestScoringEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_hour_daylight(self):
        """Test with only 1 hour of daylight (edge case)."""
        now = datetime.utcnow()
        tomorrow_date = now + timedelta(days=1)
        tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        sunrise = tomorrow_start + 12 * 3600
        sunset = tomorrow_start + 13 * 3600  # Only 1 hour

        daily = [
            {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
            {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
        ]

        hourly = [{"dt": sunrise, "clouds": 50}]

        result = compute_score(daily, hourly)

        # Score should reflect 50% clouds
        assert 0 <= result["score"] <= 100
        assert result["daylight_hours"] == pytest.approx(1.0, rel=0.01)

    def test_short_daylight(self):
        """Test with short daylight window (polar regions)."""
        now = datetime.utcnow()
        tomorrow_date = now + timedelta(days=1)
        tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        sunrise = tomorrow_start + 11 * 3600
        sunset = tomorrow_start + 13 * 3600  # 2 hours

        daily = [
            {"sunrise": sunrise, "sunset": sunset, "clouds": 30},
            {"sunrise": sunrise, "sunset": sunset, "clouds": 30},
        ]

        hourly = [
            {"dt": sunrise, "clouds": 30},
            {"dt": sunrise + 3600, "clouds": 30},
        ]

        result = compute_score(daily, hourly)

        assert result["daylight_hours"] == pytest.approx(2.0, rel=0.01)
        assert result["score"] >= 70  # 30% clouds → ~70 score

    def test_very_long_daylight(self):
        """Test with very long daylight window (polar summer)."""
        now = datetime.utcnow()
        tomorrow_date = now + timedelta(days=1)
        tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        sunrise = tomorrow_start + 0  # Midnight
        sunset = tomorrow_start + 24 * 3600  # Full 24 hours

        daily = [
            {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
            {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
        ]

        hourly = [{"dt": sunrise + i * 3600, "clouds": 0} for i in range(24)]

        result = compute_score(daily, hourly)

        assert result["daylight_hours"] == pytest.approx(24.0, rel=0.01)
        assert result["score"] == 100  # All clear

    def test_all_hours_at_boundaries(self):
        """Test when all hourly data is at sunrise/sunset boundaries."""
        now = datetime.utcnow()
        tomorrow_date = now + timedelta(days=1)
        tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        sunrise = tomorrow_start + 6 * 3600
        sunset = tomorrow_start + 18 * 3600

        daily = [
            {"sunrise": sunrise, "sunset": sunset, "clouds": 50},
            {"sunrise": sunrise, "sunset": sunset, "clouds": 50},
        ]

        # Only hours at sunrise/sunset (low weight) with mixed clouds
        hourly = [
            {"dt": sunrise, "clouds": 50},  # Weight ~0 at sunrise
            {"dt": sunset - 1, "clouds": 50},  # Weight ~0 at sunset
        ]

        result = compute_score(daily, hourly)

        # Mixed clouds at low-weight times should give reasonable score
        assert 0 <= result["score"] <= 100

    def test_mixed_cloud_cover_distribution(self):
        """Test realistic cloud cover distribution."""
        now = datetime.utcnow()
        tomorrow_date = now + timedelta(days=1)
        tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        sunrise = tomorrow_start + 6 * 3600
        sunset = tomorrow_start + 18 * 3600

        daily = [
            {"sunrise": sunrise, "sunset": sunset, "clouds": 40},
            {"sunrise": sunrise, "sunset": sunset, "clouds": 40},
        ]

        # Clouds: 80% dawn, 20% midday, 80% dusk (realistic)
        hourly = [
            {"dt": sunrise + 0 * 3600, "clouds": 80},
            {"dt": sunrise + 1 * 3600, "clouds": 70},
            {"dt": sunrise + 2 * 3600, "clouds": 60},
            {"dt": sunrise + 3 * 3600, "clouds": 40},
            {"dt": sunrise + 4 * 3600, "clouds": 20},
            {"dt": sunrise + 5 * 3600, "clouds": 10},  # Solar noon area
            {"dt": sunrise + 6 * 3600, "clouds": 20},
            {"dt": sunrise + 7 * 3600, "clouds": 40},
            {"dt": sunrise + 8 * 3600, "clouds": 60},
            {"dt": sunrise + 9 * 3600, "clouds": 70},
            {"dt": sunrise + 10 * 3600, "clouds": 80},
            {"dt": sunrise + 11 * 3600, "clouds": 80},
        ]

        result = compute_score(daily, hourly)

        # Midday is clear (10-20%), so score should be decent despite cloudy dawn/dusk
        assert result["score"] > 50

    def test_score_boundary_zero(self):
        """Test that score is clamped to [0, 100]."""
        now = datetime.utcnow()
        tomorrow_date = now + timedelta(days=1)
        tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        sunrise = tomorrow_start + 6 * 3600
        sunset = tomorrow_start + 18 * 3600

        daily = [
            {"sunrise": sunrise, "sunset": sunset, "clouds": 100},
            {"sunrise": sunrise, "sunset": sunset, "clouds": 100},
        ]

        hourly = [{"dt": sunrise + i * 3600, "clouds": 100} for i in range(12)]

        result = compute_score(daily, hourly)

        assert result["score"] == 0
        assert result["score"] >= 0

    def test_score_boundary_hundred(self):
        """Test that score can reach 100."""
        now = datetime.utcnow()
        tomorrow_date = now + timedelta(days=1)
        tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        sunrise = tomorrow_start + 6 * 3600
        sunset = tomorrow_start + 18 * 3600

        daily = [
            {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
            {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
        ]

        hourly = [{"dt": sunrise + i * 3600, "clouds": 0} for i in range(12)]

        result = compute_score(daily, hourly)

        assert result["score"] == 100
        assert result["score"] <= 100

    def test_invalid_daily_data_too_short(self):
        """Test error handling for insufficient daily data."""
        daily = [{"sunrise": 1000000, "sunset": 1010000, "clouds": 0}]
        hourly = []

        with pytest.raises(ValueError) as exc_info:
            compute_score(daily, hourly)

        assert "Need at least 2 days" in str(exc_info.value)

    def test_invalid_sunrise_sunset(self):
        """Test error handling for invalid sunrise/sunset."""
        daily = [
            {"sunrise": 1000000, "sunset": 1010000, "clouds": 0},
            {"sunrise": 1010000, "sunset": 1010000, "clouds": 0},  # sunrise == sunset
        ]
        hourly = []

        with pytest.raises(ValueError) as exc_info:
            compute_score(daily, hourly)

        assert "Invalid sunrise/sunset" in str(exc_info.value)


class TestScoringOutputFormat:
    """Test output data structure and format."""

    def test_response_has_all_required_fields(self):
        """Test that response contains all required fields."""
        now = datetime.utcnow()
        tomorrow_date = now + timedelta(days=1)
        tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        sunrise = tomorrow_start + 6 * 3600
        sunset = tomorrow_start + 18 * 3600

        daily = [
            {"sunrise": sunrise, "sunset": sunset, "clouds": 50},
            {"sunrise": sunrise, "sunset": sunset, "clouds": 50},
        ]

        hourly = [{"dt": sunrise + i * 3600, "clouds": 50} for i in range(12)]

        result = compute_score(daily, hourly)

        required_fields = [
            "date",
            "sunrise",
            "sunset",
            "daylight_hours",
            "score",
            "score_description",
            "avg_cloud_cover_pct",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_score_is_integer(self):
        """Test that score is an integer."""
        now = datetime.utcnow()
        tomorrow_date = now + timedelta(days=1)
        tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        sunrise = tomorrow_start + 6 * 3600
        sunset = tomorrow_start + 18 * 3600

        daily = [
            {"sunrise": sunrise, "sunset": sunset, "clouds": 33},
            {"sunrise": sunrise, "sunset": sunset, "clouds": 33},
        ]

        hourly = [{"dt": sunrise + i * 3600, "clouds": 33} for i in range(12)]

        result = compute_score(daily, hourly)

        assert isinstance(result["score"], int)

    def test_date_format_is_iso(self):
        """Test that date is in ISO format (YYYY-MM-DD)."""
        now = datetime.utcnow()
        tomorrow_date = now + timedelta(days=1)
        tomorrow_start = int(tomorrow_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

        sunrise = tomorrow_start + 6 * 3600
        sunset = tomorrow_start + 18 * 3600

        daily = [
            {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
            {"sunrise": sunrise, "sunset": sunset, "clouds": 0},
        ]

        hourly = [{"dt": sunrise, "clouds": 0}]

        result = compute_score(daily, hourly)

        # Check format: YYYY-MM-DD
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}", result["date"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
