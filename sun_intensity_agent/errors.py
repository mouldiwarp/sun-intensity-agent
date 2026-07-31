"""
Error handling utilities and exception definitions.
"""
from typing import Dict, Tuple, Type
from .constants import (
    HTTP_STATUS_AUTH_ERROR,
    HTTP_STATUS_RATE_LIMIT,
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_UPSTREAM_ERROR,
    HTTP_STATUS_SERVER_ERROR,
)


class OWMError(Exception):
    """Base exception for OWM errors."""
    pass


class OWMAuthError(OWMError):
    """401 authentication failure."""
    def __init__(self):
        super().__init__(
            "API key is invalid or One Call 3.0 is not enabled for this key. "
            "Subscribe to One Call 3.0 at https://openweathermap.org/api/one-call-3"
        )


class OWMRateLimitError(OWMError):
    """429 rate limit exceeded."""
    def __init__(self, retry_after: int = None):
        msg = "OpenWeatherMap API rate limit exceeded. Please retry later."
        if retry_after:
            msg += f" (Retry-After: {retry_after}s)"
        super().__init__(msg)
        self.retry_after = retry_after


class OWMRequestError(OWMError):
    """Generic request error (timeout, 5xx, connection failure, etc.)."""
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


# Exception to HTTP status code mapping
EXCEPTION_TO_HTTP_STATUS: Dict[Type[Exception], int] = {
    OWMAuthError: HTTP_STATUS_AUTH_ERROR,
    OWMRateLimitError: HTTP_STATUS_RATE_LIMIT,
    ValueError: HTTP_STATUS_BAD_REQUEST,
    OWMRequestError: HTTP_STATUS_UPSTREAM_ERROR,
}


def get_http_status_code(exception: Exception) -> int:
    """
    Map an exception to an appropriate HTTP status code.

    Args:
        exception: The exception to map

    Returns:
        HTTP status code (default: 500 for unmapped exceptions)
    """
    for exc_type, status_code in EXCEPTION_TO_HTTP_STATUS.items():
        if isinstance(exception, exc_type):
            return status_code
    return HTTP_STATUS_SERVER_ERROR


def format_error_response(exception: Exception) -> Dict[str, str]:
    """
    Format an exception as an error response dict.

    Args:
        exception: The exception to format

    Returns:
        Dict with "error" key containing the error message
    """
    if isinstance(exception, OWMError):
        message = str(exception)
    elif isinstance(exception, ValueError):
        message = str(exception)
    else:
        message = f"Unexpected error: {str(exception)}"

    return {"error": message}
