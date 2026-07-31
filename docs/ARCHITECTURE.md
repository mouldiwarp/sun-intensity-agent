# Architecture Documentation

## System Overview

Sun Intensity Agent is a layered Python service that forecasts solar panel performance by analyzing tomorrow's weather conditions from OpenWeatherMap. The system is designed for reliability, maintainability, and extensibility.

### Core Philosophy

- **Separation of Concerns** — Each module has a single, well-defined responsibility
- **Defensive Programming** — Explicit error handling, validation at boundaries
- **Type Safety** — Full type hints throughout for IDE support and error detection
- **Testability** — Pure functions where possible, dependency injection for testing
- **Resilience** — Automatic retry with exponential backoff for transient failures

## Layered Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Interfaces Layer                      │
│                    (CLI / HTTP Server)                       │
│  ┌────────────────────┐              ┌──────────────────┐   │
│  │   cli.py           │              │   server.py      │   │
│  │ (argparse, JSON)   │              │ (FastAPI, REST)  │   │
│  └────────────────────┘              └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌──────────────────────────────────────────────────────────────┐
│                     Orchestration Layer                      │
│                       (core.py)                              │
│     Coordinates: fetch → validate → score → format          │
└──────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌──────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ owm_client   │  │   scoring    │  │    config        │  │
│  │ (API+retry)  │  │  (algorithm) │  │ (settings)       │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌──────────────────────────────────────────────────────────────┐
│                     Shared Layer                             │
│  ┌──────────────┐              ┌──────────────────────────┐ │
│  │ constants.py │              │   errors.py              │ │
│  │ (all config) │              │ (exceptions + helpers)   │ │
│  └──────────────┘              └──────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌──────────────────────────────────────────────────────────────┐
│                    External Services                         │
│          OpenWeatherMap One Call API 3.0                     │
│         (https://api.openweathermap.org/...)                 │
└──────────────────────────────────────────────────────────────┘
```

## Module Details

### 1. Interfaces Layer

#### `cli.py` — Command-Line Interface
**Responsibility:** Parse CLI arguments and return JSON to stdout

**Key Components:**
- `main()` — Entry point using argparse
- Handles `--lat`, `--lon`, `--pretty` flags
- Exit codes: 0 (success), 1 (error), 2 (unexpected)

**Data Flow:**
```
CLI Args → validate_location → get_score → format_json → stdout
                                    ↓
                              (errors) → stderr
```

**Error Handling:**
- Catches `OWMError`, `ValueError`, generic exceptions
- Uses `format_error_response()` from `errors.py`
- Prints JSON to stderr with appropriate exit code

#### `server.py` — HTTP Server
**Responsibility:** Serve sun intensity scores via REST API

**Key Components:**
- `score()` — GET `/score` endpoint
- `health()` — GET `/health` endpoint
- FastAPI with automatic request validation

**Endpoints:**
```
GET /score?lat=38.9&lon=-77.0
GET /health
GET /docs (auto-generated from docstrings)
```

**Error Handling:**
- Uses `get_http_status_code()` from `errors.py`
- Maps exceptions to HTTP status codes
- Returns clean JSON error responses

### 2. Orchestration Layer

#### `core.py` — Orchestrator
**Responsibility:** Coordinate fetch, validate, score, and format

**Key Function:**
```python
def get_score(lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]
```

**Data Flow:**
```
Input (lat, lon override)
    ↓
get_settings() → validate_location()
    ↓
fetch_forecast() → daily, hourly arrays
    ↓
compute_score() → score + metadata
    ↓
Envelope (add location, timestamp)
    ↓
Output (JSON dict)
```

**Responsibilities:**
- Loads settings from environment
- Validates location coordinates
- Calls OWM API (with retry)
- Computes score from forecast
- Adds metadata (location, timestamp)

**Error Propagation:**
- Raises exceptions as-is
- Errors are handled by the interface layer (CLI or server)

### 3. Business Logic Layer

#### `owm_client.py` — OpenWeatherMap Integration
**Responsibility:** Fetch weather data with resilience

**Key Components:**
- `RetryConfig` — Configurable retry behavior
- `fetch_forecast()` — Main function with exponential backoff
- Helper functions:
  - `_parse_retry_after_header()` — Extract Retry-After
  - `_handle_response_error()` — Map HTTP status to exceptions
  - `_should_retry()` — Determine if exception is retryable

**Retry Logic:**
```
for attempt in range(max_retries + 1):
    try:
        response = requests.get(...)
        if error_status:
            raise appropriate_exception()
        return response.json()
    except retryable_error as e:
        if should_retry:
            delay = calculate_exponential_backoff(attempt)
            sleep(delay)
        else:
            raise
```

**Exception Handling:**
- **Permanent failures** (no retry):
  - 401 Unauthorized (auth issue)
  - 4xx Client errors (bad request)
- **Transient failures** (with retry):
  - 429 Rate Limit (respects Retry-After header)
  - 5xx Server errors
  - Timeouts and connection errors

#### `scoring.py` — Solar Intensity Algorithm
**Responsibility:** Compute score from weather data

**Key Function:**
```python
def compute_score(daily: List[Dict], hourly: List[Dict]) -> Dict[str, Any]
```

**Algorithm Steps:**
1. Extract sunrise/sunset from `daily[1]` (tomorrow)
2. Filter `hourly` to daylight window (sunrise to sunset)
3. For each hour in window:
   - Extract cloud cover percentage
   - Calculate clear sky: `1 - (clouds / 100)`
   - Calculate weight: `sin(π × (t - sunrise) / daylight_duration)`
   - Accumulate weighted average
4. Compute final score: `100 × avg_weighted_clear_sky`
5. Format timestamps as ISO 8601 with UTC offset

**Key Helpers:**
- `_format_timestamp()` — Convert epoch to ISO string
- `_calculate_weighted_score()` — Compute weighted average
- `_calculate_fallback_score()` — Fallback if no hourly data
- `_calculate_avg_cloud_cover()` — Average clouds for reference

**Data Structures:**

Daily object:
```python
{
    "sunrise": 1234567890,  # Unix epoch
    "sunset": 1234567890,
    "clouds": 30,            # 0-100 percentage
}
```

Hourly object:
```python
{
    "dt": 1234567890,        # Unix epoch
    "clouds": 30,             # 0-100 percentage
}
```

Result:
```python
{
    "date": "2026-08-01",
    "sunrise": "2026-08-01T10:12:00+00:00",
    "sunset": "2026-08-02T00:45:00+00:00",
    "daylight_hours": 14.55,
    "score": 72,
    "score_description": "...",
    "avg_cloud_cover_pct": 35.2,
}
```

#### `config.py` — Settings Management
**Responsibility:** Load and validate application configuration

**Key Class:**
```python
class Settings(BaseSettings):
    owm_api_key: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    port: int = 8080
```

**Features:**
- Loads from environment variables (`.env` support)
- Validates location coordinates
- Pydantic v2 compliant (ConfigDict)
- `validate_location()` method for runtime validation

**Config Sources** (priority order):
1. CLI arguments (`--lat`, `--lon`)
2. HTTP query parameters (`?lat=`, `?lon=`)
3. Environment variables (`LAT`, `LON`)
4. Defaults (for port)

### 4. Shared Layer

#### `constants.py` — Centralized Configuration
**Responsibility:** Single source of truth for all constants

**Categories:**
- **API Config:** Endpoint, timeout, exclude params
- **Retry Config:** Max retries, base/max delays, jitter
- **Scoring:** Scale factors, clear sky scale
- **HTTP Codes:** Status codes for different errors
- **CLI Codes:** Exit codes (0, 1, 2)
- **Validation:** Coordinate ranges
- **Formatting:** Timezone offset for timestamps

**Usage Pattern:**
```python
from .constants import OWM_REQUEST_TIMEOUT, DEFAULT_MAX_RETRIES
```

#### `errors.py` — Exception Hierarchy
**Responsibility:** Define exceptions and error handling helpers

**Exception Classes:**
```
OWMError (base)
├── OWMAuthError (401)
├── OWMRateLimitError (429, with retry_after field)
└── OWMRequestError (generic, with retryable flag)
```

**Helper Functions:**
- `get_http_status_code(exception)` → HTTP status code
- `format_error_response(exception)` → {"error": message} dict

**Usage Pattern:**
```python
from .errors import OWMAuthError, format_error_response

try:
    result = fetch_forecast(...)
except OWMAuthError as e:
    response = format_error_response(e)  # {"error": "..."}
    return HTTPException(status_code=401, detail=response["error"])
```

## Data Flow Examples

### Example 1: CLI Success Path

```
User: python -m sun_intensity_agent.cli --lat 38.9 --lon -77.0 --pretty

1. cli.py: main()
   - Parse args: lat=38.9, lon=-77.0, pretty=True
   
2. core.py: get_score(lat=38.9, lon=-77.0)
   - Load settings from env
   - Validate location (38.9, -77.0)
   
3. owm_client.py: fetch_forecast(api_key, 38.9, -77.0)
   - Make HTTP request to OpenWeatherMap
   - Parse response → {"daily": [...], "hourly": [...]}
   
4. scoring.py: compute_score(daily, hourly)
   - Extract sunrise/sunset
   - Filter hourly to daylight window
   - Calculate weighted average
   - Return {"date": "...", "score": 72, ...}
   
5. core.py: Add envelope
   - Add location: {"lat": 38.9, "lon": -77.0}
   - Add timestamp: "generated_at": "..."
   - Return complete result
   
6. cli.py: Format and output
   - json.dumps(result, indent=2)
   - print() to stdout
   - sys.exit(0)

Output:
{
  "date": "2026-08-01",
  "location": {"lat": 38.9, "lon": -77.0},
  "score": 72,
  ...
}
```

### Example 2: Error Handling (Rate Limit)

```
1. owm_client.py: fetch_forecast()
   - HTTP request returns 429 status
   - _handle_response_error() → OWMRateLimitError(retry_after=60)
   
2. Retry loop:
   - Catch OWMRateLimitError
   - _should_retry() → True (attempt 0 of 3)
   - delay = calculate_delay(0) ≈ 1s
   - sleep(1)
   - Retry request
   
3. Retry attempt succeeds:
   - Return {"daily": [...], "hourly": [...]}
   
4. Continue normal flow:
   - compute_score()
   - format response
   - Return to caller
```

### Example 3: Permanent Error (Auth Failure)

```
1. owm_client.py: fetch_forecast()
   - HTTP request returns 401 status
   - _handle_response_error() → OWMAuthError()
   
2. Retry loop:
   - Catch OWMAuthError
   - _should_retry() → False (auth is permanent)
   - raise OWMAuthError immediately
   
3. Exception propagates:
   - core.py: get_score() → not caught, propagates
   - cli.py: main() → catches OWMError
   
4. Error handling:
   - format_error_response() → {"error": "API key invalid..."}
   - print to stderr
   - sys.exit(1)
```

## Key Design Decisions

### 1. Pure Functions for Scoring
**Decision:** `compute_score()` is pure (no side effects, no I/O)

**Rationale:**
- Easy to test with mock data
- No dependency injection needed
- Predictable, repeatable behavior
- Can be parallelized or cached

### 2. Unix Epoch Timestamps
**Decision:** All timestamps are Unix epoch seconds internally

**Rationale:**
- No timezone conversion needed
- Simple arithmetic (`sunrise <= dt < sunset`)
- Consistent across timezones
- Easy conversion to ISO format when needed

### 3. Exponential Backoff with Jitter
**Decision:** Use 2^attempt × base_delay ± 25% jitter

**Rationale:**
- Prevents hammering failed servers
- Jitter prevents thundering herd
- Respects Retry-After header when present
- Configurable per-call if needed

### 4. Type Hints Throughout
**Decision:** All functions have full type annotations

**Rationale:**
- IDE support (autocomplete, type checking)
- Self-documenting code
- Catches errors at development time
- MyPy/Pyright compatibility

### 5. Centralized Constants
**Decision:** All magic numbers in `constants.py`

**Rationale:**
- Single source of truth
- Easy to adjust for different deployments
- Clear documentation of expected values
- Reduces duplication

### 6. Separated Error Definitions
**Decision:** All exceptions in `errors.py`, not in individual modules

**Rationale:**
- Shared between CLI and server
- Consistent error handling
- Single place to map exceptions to HTTP status codes
- Easy to extend with new error types

## Extensibility Points

### Adding New Error Types

```python
# 1. Define in errors.py
class OWMCustomError(OWMError):
    def __init__(self, message: str):
        super().__init__(message)

# 2. Add to status mapping
EXCEPTION_TO_HTTP_STATUS[OWMCustomError] = 503

# 3. Raise in owm_client.py
if response.status_code == 503:
    raise OWMCustomError("Service unavailable")

# 4. CLI and server handle automatically via shared helpers
```

### Adding New Configuration

```python
# 1. Add to constants.py
MY_NEW_CONSTANT = "value"

# 2. Use in modules
from .constants import MY_NEW_CONSTANT
```

### Adding New Endpoints

```python
# In server.py
@app.get("/new-endpoint")
async def new_endpoint() -> Dict[str, Any]:
    """New endpoint description."""
    return get_score()

# FastAPI handles validation, documentation, and error mapping
```

## Testing Architecture

### Test Organization

```
tests/
├── test_config.py       # 19 tests: Settings, validation, location
├── test_owm_client.py   # 17 tests: API client, backoff retry
├── test_scoring.py      # 16 tests: Algorithm, edge cases
└── test_integration.py  # 3 tests: End-to-end flow
```

### Testing Patterns

**Unit Tests (Pure Functions):**
```python
# No mocking needed for pure functions
result = compute_score(
    daily=[{...}, {...}],
    hourly=[{...}, {...}],
)
assert result["score"] == 100
```

**API Client Tests (Mocked Network):**
```python
# Mock HTTP responses
@patch("requests.get")
def test_rate_limit_retry(mock_get):
    mock_get.side_effect = [
        Mock(status_code=429),  # First fails
        Mock(status_code=200, json=lambda: {...}),  # Second succeeds
    ]
    
    result = fetch_forecast("key", 38.9, -77.0)
    assert result["daily"] is not None
```

**Integration Tests (Mock API):**
```python
# Test complete flow with mock data
daily = [{...}, {...}]
hourly = [{...}, {...}]
result = compute_score(daily, hourly)
assert result["location"] is None  # Not added by scoring.py
```

## Performance Characteristics

### Time Complexity
- **API Call:** O(1) + network latency
- **Scoring:** O(h) where h = hours in daylight window
  - Typically h ≈ 12 hours
  - Linear scan through hourly data
- **Total:** O(1) + O(h) ≈ O(1) for practical purposes

### Space Complexity
- **Hourly Array:** O(h) where h ≈ 48 hours
- **Result Dict:** O(1) fixed size
- **Total:** O(h) ≈ 50-100 MB per request

### Network
- **API Latency:** ~500ms-1s typical
- **Retry Delays:** exponential backoff (1s, 2s, 4s, 8s, 60s)
- **Total Time (failure + retry):** ~8 seconds worst case (3 retries)

## Security Considerations

### API Key Management
- ✅ Stored in environment variables, never in code
- ✅ Not logged or printed
- ✅ Should use secrets manager in production

### Input Validation
- ✅ Coordinates validated (within valid ranges)
- ✅ API responses validated (JSON parsing error handling)
- ✅ HTTP parameters validated (type hints, query validation)

### Error Information
- ✅ Auth errors don't expose full error details
- ✅ Server errors logged at appropriate levels
- ✅ API keys never included in error messages

## Monitoring & Observability

### Current State
- Error messages are informative
- Exit codes distinguish error types
- HTTP status codes follow REST conventions

### Future Enhancements
- Structured logging with context
- Prometheus metrics
- Distributed tracing
- Error rate alerting

---

**Last updated:** 2026-07-31  
**Status:** Production-ready
