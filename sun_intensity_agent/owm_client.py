import requests
import time
import random
from typing import Any, Dict, Callable, Optional
from datetime import datetime, timedelta

from .errors import OWMError, OWMAuthError, OWMRateLimitError, OWMRequestError
from .constants import (
    OWM_API_HOURLY_ENDPOINT,
    OWM_API_DAILY_ENDPOINT,
    OWM_REQUEST_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_DELAY,
    JITTER_FACTOR,
    MIN_BACKOFF_DELAY,
)


class RetryConfig:
    """Configuration for exponential backoff retry logic."""
    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def calculate_delay(self, attempt: int) -> float:
        """Calculate backoff delay with exponential growth and jitter."""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        jitter = delay * JITTER_FACTOR * (2 * random.random() - 1)
        return max(MIN_BACKOFF_DELAY, delay + jitter)


def _parse_retry_after_header(headers: Dict[str, str]) -> Optional[int]:
    """Extract Retry-After value from HTTP headers."""
    if "Retry-After" not in headers:
        return None
    try:
        return int(headers["Retry-After"])
    except ValueError:
        return None


def _handle_response_error(status_code: int, text: str, headers: Dict[str, str]) -> OWMError:
    """Map HTTP status code to appropriate exception."""
    if status_code == 401:
        return OWMAuthError()
    elif status_code == 429:
        retry_after = _parse_retry_after_header(headers)
        return OWMRateLimitError(retry_after=retry_after)
    elif status_code >= 500:
        return OWMRequestError(f"OpenWeatherMap server error: {status_code}", retryable=True)
    else:
        return OWMRequestError(f"OpenWeatherMap API error: {status_code} {text}", retryable=False)


def _should_retry(exception: Exception, attempt: int, max_retries: int) -> bool:
    """Check if an exception should be retried."""
    if attempt >= max_retries:
        return False
    if isinstance(exception, OWMAuthError):
        return False
    if isinstance(exception, OWMRequestError) and not exception.retryable:
        return False
    return True


def _fetch_v4_endpoint(
    endpoint: str,
    api_key: str,
    lat: float,
    lon: float,
    retry_config: RetryConfig,
    sleep_func: Callable[[float], None],
) -> Dict[str, Any]:
    """Fetch data from a V4 API endpoint with retry logic."""
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
    }

    for attempt in range(retry_config.max_retries + 1):
        exception: Optional[OWMError] = None

        try:
            response = requests.get(endpoint, params=params, timeout=OWM_REQUEST_TIMEOUT)

            if response.status_code >= 400:
                raise _handle_response_error(response.status_code, response.text, response.headers)

            return response.json()

        except (requests.Timeout, requests.ConnectionError) as e:
            exception = OWMRequestError(f"Connection error: {e}", retryable=True)
        except ValueError as e:
            exception = OWMRequestError(f"Invalid JSON response: {e}", retryable=False)
        except OWMError as e:
            exception = e

        # Handle retry logic
        if exception:
            if _should_retry(exception, attempt, retry_config.max_retries):
                delay = retry_config.calculate_delay(attempt)
                sleep_func(delay)
            else:
                raise exception

    raise OWMRequestError("Unexpected error: retry loop exhausted")


def fetch_forecast(
    api_key: str,
    lat: float,
    lon: float,
    retry_config: Optional[RetryConfig] = None,
    sleep_func: Optional[Callable[[float], None]] = None,
) -> Dict[str, Any]:
    """
    Fetch tomorrow's forecast from One Call API 4.0 with exponential backoff retry.

    Uses two endpoints:
    - /timeline/1h for hourly forecast (48 hours)
    - /timeline/1day for daily forecast

    Args:
        api_key: OpenWeatherMap API key
        lat: Latitude
        lon: Longitude
        retry_config: Retry configuration (default: 3 retries, 1s base delay)
        sleep_func: Function to sleep (default: time.sleep, overridable for testing)

    Returns:
        dict with 'daily' and 'hourly' arrays in V3.0-compatible format

    Raises:
        OWMAuthError: 401 (not retried, auth errors are permanent)
        OWMRateLimitError: 429 (retried with exponential backoff)
        OWMRequestError: Timeouts, 5xx, connection errors (retried with exponential backoff)
    """
    retry_config = retry_config or RetryConfig()
    sleep_func = sleep_func or time.sleep

    # Fetch hourly data (48 hours forecast)
    hourly_data = _fetch_v4_endpoint(
        OWM_API_HOURLY_ENDPOINT, api_key, lat, lon, retry_config, sleep_func
    )

    # Fetch daily data
    daily_data = _fetch_v4_endpoint(
        OWM_API_DAILY_ENDPOINT, api_key, lat, lon, retry_config, sleep_func
    )

    # Convert V4 response format to V3.0-compatible format for backward compatibility
    # V4 returns: {"timelines": [{"intervals": [...]}]}
    # We need: {"daily": [...], "hourly": [...]}

    daily_intervals = []
    if "timelines" in daily_data:
        for timeline in daily_data["timelines"]:
            if "intervals" in timeline:
                daily_intervals = timeline["intervals"]
                break

    hourly_intervals = []
    if "timelines" in hourly_data:
        for timeline in hourly_data["timelines"]:
            if "intervals" in timeline:
                hourly_intervals = timeline["intervals"]
                break

    # Map V4 daily format to V3.0-compatible format
    mapped_daily = []
    for interval in daily_intervals:
        day = {
            "sunrise": int(datetime.fromisoformat(interval["startTime"].replace("Z", "+00:00")).timestamp()),
            "sunset": int(
                (datetime.fromisoformat(interval["startTime"].replace("Z", "+00:00")) + timedelta(days=1)).timestamp()
            ),
            "clouds": interval.get("values", {}).get("cloudCover", 0),
        }
        mapped_daily.append(day)

    # Map V4 hourly format to V3.0-compatible format
    mapped_hourly = []
    for interval in hourly_intervals:
        hour = {
            "dt": int(datetime.fromisoformat(interval["startTime"].replace("Z", "+00:00")).timestamp()),
            "clouds": interval.get("values", {}).get("cloudCover", 0),
        }
        mapped_hourly.append(hour)

    return {
        "daily": mapped_daily,
        "hourly": mapped_hourly,
    }
