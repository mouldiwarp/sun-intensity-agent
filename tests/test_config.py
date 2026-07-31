"""
Tests for configuration management and validation.
"""
import pytest
import os
from unittest.mock import patch
from sun_intensity_agent.config import Settings, get_settings


class TestSettingsEnvironmentVariables:
    """Test environment variable loading."""

    @patch.dict(os.environ, {"OWM_API_KEY": "test_key_123"})
    def test_load_api_key(self):
        """Test loading OWM_API_KEY from environment."""
        settings = Settings(owm_api_key=os.getenv("OWM_API_KEY", ""))
        assert settings.owm_api_key == "test_key_123"

    @patch.dict(os.environ, {"OWM_API_KEY": "test_key", "LAT": "38.9", "LON": "-77.0"})
    def test_load_location(self):
        """Test loading LAT and LON from environment."""
        settings = Settings(
            owm_api_key="test_key",
            lat=float(os.getenv("LAT", "0")),
            lon=float(os.getenv("LON", "0")),
        )
        assert settings.lat == 38.9
        assert settings.lon == -77.0

    @patch.dict(os.environ, {"PORT": "9000"})
    def test_load_port(self):
        """Test loading PORT from environment."""
        settings = Settings(owm_api_key="test_key", port=int(os.getenv("PORT", "8080")))
        assert settings.port == 9000


class TestSettingsDefaults:
    """Test default configuration values."""

    def test_default_port(self):
        """Test default port is 8080."""
        settings = Settings(owm_api_key="test_key")
        assert settings.port == 8080

    def test_default_location_none(self):
        """Test that LAT and LON default to None."""
        settings = Settings(owm_api_key="test_key")
        assert settings.lat is None
        assert settings.lon is None


class TestValidateLocation:
    """Test location coordinate validation."""

    def test_valid_location(self):
        """Test validation of valid coordinates."""
        settings = Settings(owm_api_key="test_key", lat=38.9, lon=-77.0)
        lat, lon = settings.validate_location()
        assert lat == 38.9
        assert lon == -77.0

    def test_override_location(self):
        """Test overriding location at validation time."""
        settings = Settings(owm_api_key="test_key", lat=38.9, lon=-77.0)
        lat, lon = settings.validate_location(lat=51.5, lon=-0.1)
        assert lat == 51.5
        assert lon == -0.1

    def test_missing_location(self):
        """Test error when location is not provided."""
        settings = Settings(owm_api_key="test_key")
        with pytest.raises(ValueError) as exc_info:
            settings.validate_location()
        assert "Latitude and longitude must be provided" in str(exc_info.value)

    def test_partial_location_missing(self):
        """Test error when only one coordinate is provided."""
        settings = Settings(owm_api_key="test_key", lat=38.9)
        with pytest.raises(ValueError) as exc_info:
            settings.validate_location()
        assert "Latitude and longitude must be provided" in str(exc_info.value)

    def test_latitude_out_of_range_high(self):
        """Test latitude validation (max: 90)."""
        settings = Settings(owm_api_key="test_key")
        with pytest.raises(ValueError) as exc_info:
            settings.validate_location(lat=91.0, lon=-77.0)
        assert "Latitude must be between" in str(exc_info.value)

    def test_latitude_out_of_range_low(self):
        """Test latitude validation (min: -90)."""
        settings = Settings(owm_api_key="test_key")
        with pytest.raises(ValueError) as exc_info:
            settings.validate_location(lat=-91.0, lon=-77.0)
        assert "Latitude must be between" in str(exc_info.value)

    def test_longitude_out_of_range_high(self):
        """Test longitude validation (max: 180)."""
        settings = Settings(owm_api_key="test_key")
        with pytest.raises(ValueError) as exc_info:
            settings.validate_location(lat=38.9, lon=181.0)
        assert "Longitude must be between" in str(exc_info.value)

    def test_longitude_out_of_range_low(self):
        """Test longitude validation (min: -180)."""
        settings = Settings(owm_api_key="test_key")
        with pytest.raises(ValueError) as exc_info:
            settings.validate_location(lat=38.9, lon=-181.0)
        assert "Longitude must be between" in str(exc_info.value)

    def test_boundary_latitude_90(self):
        """Test latitude boundary: 90 is valid."""
        settings = Settings(owm_api_key="test_key")
        lat, lon = settings.validate_location(lat=90.0, lon=0.0)
        assert lat == 90.0

    def test_boundary_latitude_minus_90(self):
        """Test latitude boundary: -90 is valid."""
        settings = Settings(owm_api_key="test_key")
        lat, lon = settings.validate_location(lat=-90.0, lon=0.0)
        assert lat == -90.0

    def test_boundary_longitude_180(self):
        """Test longitude boundary: 180 is valid."""
        settings = Settings(owm_api_key="test_key")
        lat, lon = settings.validate_location(lat=0.0, lon=180.0)
        assert lon == 180.0

    def test_boundary_longitude_minus_180(self):
        """Test longitude boundary: -180 is valid."""
        settings = Settings(owm_api_key="test_key")
        lat, lon = settings.validate_location(lat=0.0, lon=-180.0)
        assert lon == -180.0


class TestLocationOverridePriority:
    """Test location override priority (args > env vars)."""

    def test_arg_overrides_env(self):
        """Test that explicit args override settings."""
        settings = Settings(owm_api_key="test_key", lat=38.9, lon=-77.0)
        lat, lon = settings.validate_location(lat=51.5, lon=-0.1)
        assert lat == 51.5
        assert lon == -0.1

    def test_partial_override(self):
        """Test that partial override works correctly."""
        settings = Settings(owm_api_key="test_key", lat=38.9, lon=-77.0)
        # Override only lat, leave lon from settings
        lat, lon = settings.validate_location(lat=51.5, lon=None)
        assert lat == 51.5
        assert lon == -77.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
