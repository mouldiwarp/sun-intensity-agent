from typing import Optional, Tuple
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

from .constants import (
    DEFAULT_SERVER_PORT,
    LATITUDE_MIN,
    LATITUDE_MAX,
    LONGITUDE_MIN,
    LONGITUDE_MAX,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    owm_api_key: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    port: int = DEFAULT_SERVER_PORT

    def validate_location(self, lat: Optional[float] = None, lon: Optional[float] = None) -> Tuple[float, float]:
        """
        Resolve and validate location from arguments or environment variables.

        Args:
            lat: Override latitude (uses self.lat if None)
            lon: Override longitude (uses self.lon if None)

        Returns:
            Tuple of (latitude, longitude)

        Raises:
            ValueError: If location is missing or out of valid range
        """
        final_lat = lat if lat is not None else self.lat
        final_lon = lon if lon is not None else self.lon

        if final_lat is None or final_lon is None:
            raise ValueError("Latitude and longitude must be provided via env vars or CLI/query parameters")

        if not (LATITUDE_MIN <= final_lat <= LATITUDE_MAX):
            raise ValueError(f"Latitude must be between {LATITUDE_MIN} and {LATITUDE_MAX}, got {final_lat}")
        if not (LONGITUDE_MIN <= final_lon <= LONGITUDE_MAX):
            raise ValueError(f"Longitude must be between {LONGITUDE_MIN} and {LONGITUDE_MAX}, got {final_lon}")

        return final_lat, final_lon


def get_settings() -> Settings:
    """Get application settings from environment."""
    return Settings()
