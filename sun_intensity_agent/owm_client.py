import requests
import time
import random
from typing import Any, Dict, Callable, Optional

from .errors import OWMError, OWMAuthError, OWMRateLimitError, OWMRequestError
from .constants import (
    OWM_API_ENDPOINT,
    OWM_REQUEST_TIMEOUT,
    OWM_API_EXCLUDE_PARAMS,
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


def fetch_forecast(
    api_key: str,
    lat: float,
    lon: float,
    retry_config: Optional[RetryConfig] = None,
    sleep_func: Optional[Callable[[float], None]] = None,
) -> Dict[str, Any]:
    """
    Fetch tomorrow's forecast from One Call API 3.0 with exponential backoff retry.

    Args:
        api_key: OpenWeatherMap API key
        lat: Latitude
        lon: Longitude
        retry_config: Retry configuration (default: 3 retries, 1s base delay)
        sleep_func: Function to sleep (default: time.sleep, overridable for testing)

    Returns:
        dict with 'daily' and 'hourly' arrays

    Raises:
        OWMAuthError: 401 (not retried, auth errors are permanent)
        OWMRateLimitError: 429 (retried with exponential backoff)
        OWMRequestError: Timeouts, 5xx, connection errors (retried with exponential backoff)
    """
    retry_config = retry_config or RetryConfig()
    sleep_func = sleep_func or time.sleep

    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "exclude": OWM_API_EXCLUDE_PARAMS,
    }

    for attempt in range(retry_config.max_retries + 1):
        exception: Optional[OWMError] = None

        try:
            response = requests.get(OWM_API_ENDPOINT, params=params, timeout=OWM_REQUEST_TIMEOUT)

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

    # Safety net (should not reach here)
    raise OWMRequestError("Unexpected error: retry loop exhausted")
