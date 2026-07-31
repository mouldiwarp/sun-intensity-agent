"""
Application constants and configuration values.
"""

# API Configuration (One Call API 4.0)
OWM_API_BASE = "https://api.openweathermap.org/data/4.0/onecall"
OWM_API_HOURLY_ENDPOINT = f"{OWM_API_BASE}/timeline/1h"  # 1-hourly forecast
OWM_API_DAILY_ENDPOINT = f"{OWM_API_BASE}/timeline/1day"  # Daily forecast
OWM_REQUEST_TIMEOUT = 10  # seconds

# Retry Configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 60.0  # seconds
JITTER_FACTOR = 0.25  # ±25% of delay
MIN_BACKOFF_DELAY = 0.1  # seconds

# Scoring Configuration
SCORE_MIN = 0
SCORE_MAX = 100
SCORE_SCALE = 100  # Multiplier for percentage-to-score conversion
CLEAR_SKY_SCALE = 100  # Cloud cover percentage scale

# HTTP Status Codes
HTTP_STATUS_AUTH_ERROR = 401
HTTP_STATUS_RATE_LIMIT = 429
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_UPSTREAM_ERROR = 502
HTTP_STATUS_SERVER_ERROR = 500

# CLI Exit Codes
CLI_EXIT_SUCCESS = 0
CLI_EXIT_ERROR = 1
CLI_EXIT_UNEXPECTED_ERROR = 2

# Validation
LATITUDE_MIN = -90.0
LATITUDE_MAX = 90.0
LONGITUDE_MIN = -180.0
LONGITUDE_MAX = 180.0
DEFAULT_SERVER_PORT = 8080

# Timestamp Formatting
TIMEZONE_UTC_OFFSET = "+00:00"

# Scoring Fallback
FALLBACK_SCORE_CLEAR_SKY = 100
