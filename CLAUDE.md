# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Sun Intensity Agent** is a Python service that queries tomorrow's weather forecast from OpenWeatherMap and produces a 0-100 "clear sky score" to inform solar battery charging decisions. The score feeds a downstream agent (mcp__solax-cloud__set_battery_self_use_mode) to determine overnight charge percentage.

The service runs in two modes:
- **CLI**: One-shot query via `python -m sun_intensity_agent.cli`
- **HTTP Server**: FastAPI on port 8080 with GET /score endpoint

Both modes are containerized in a single Docker image.

## Architecture & Design

### Core Separation of Concerns

```
config.py          Load & validate env vars (OWM_API_KEY, LAT, LON, PORT)
                   ↓
owm_client.py      Fetch One Call API 3.0 data
                   (handles 401, 429, timeouts → typed exceptions)
                   ↓
scoring.py         Pure function: (daily, hourly) → score dict
                   (No I/O, timezone-safe via Unix epoch)
                   ↓
core.py            Orchestrator: validate → fetch → score → envelope
                   ↓
cli.py / server.py Two UI layers: argparse vs FastAPI
```

### Key Design Decisions

1. **Pure Function for Algorithm** (`scoring.py`)
   - No external I/O, side effects, or state
   - Fully testable with mock data
   - Reusable in different contexts

2. **Unix Epoch Throughout**
   - sunrise/sunset/hourly timestamps are all Unix epoch seconds
   - Eliminates timezone math entirely
   - Comparison `sunrise <= dt < sunset` is timezone-safe

3. **Sine Weighting for Solar Potential**
   - Weight peaks at solar noon, tapers to ~0 at sunrise/sunset
   - Formula: `weight = sin(π × (t - sunrise) / (sunset - sunrise))`
   - Makes midday cloud cover matter more than dawn/dusk

4. **Exponential Backoff Retry Logic**
   - Transient errors (429 rate limit, 5xx server, timeouts) → retried with exponential backoff
   - Permanent errors (401 auth, 4xx client errors) → no retry, fail immediately
   - Default: 3 retries, 1s base delay, 60s max, ±25% jitter to avoid thundering herd
   - `RetryConfig` class for customization (max_retries, base_delay, max_delay)
   - Parses `Retry-After` header from 429 responses
   - Fully testable via `sleep_func` parameter (allows unit tests without actual delays)

5. **Typed Exceptions**
   - `OWMAuthError` → 401 (points to subscription page)
   - `OWMRateLimitError` → 429 (rate limit hit), includes `retry_after` field
   - `OWMRequestError` → timeouts, 5xx, 4xx client errors; has `retryable` boolean
   - Both CLI (exit codes) and server (HTTP status) handle consistently

6. **Location Override at Multiple Levels**
   - Env vars: LAT, LON (default)
   - CLI flags: `--lat`, `--lon`
   - HTTP query params: `?lat=38.9&lon=-77.0`
   - Each layer overrides the previous; validated at core.get_score()

## Common Commands

### Development & Testing

```bash
# Run all tests (55 tests: 19 config, 3 integration, 17 OWM client + backoff, 16 scoring edge cases)
pytest tests/ -v

# Run single test
pytest tests/test_scoring.py::test_clear_sky_day -v

# Run tests for a specific module
pytest tests/test_owm_client.py -v  # Test backoff retry logic
pytest tests/test_config.py -v      # Test location validation
pytest tests/test_scoring.py -v     # Test algorithm and edge cases

# Verify Python syntax (before committing)
python3 -m py_compile sun_intensity_agent/*.py

# Check imports work (before deploying)
python3 -c "from sun_intensity_agent.server import app; print('OK')"
```

### CLI Usage (Local)

```bash
# Set env vars
export OWM_API_KEY="sk_your_key"
export LAT=38.9
export LON=-77.0

# Run one-shot query
python3 -m sun_intensity_agent.cli --pretty

# Override location for a test
python3 -m sun_intensity_agent.cli --lat 51.5 --lon -0.1 --pretty

# Pipe output to jq
python3 -m sun_intensity_agent.cli | jq '.score'
```

### Server Usage (Local Development)

```bash
# Start server with auto-reload
export OWM_API_KEY="sk_your_key"
export LAT=38.9
export LON=-77.0
uvicorn sun_intensity_agent.server:app --reload

# In another terminal, query it
curl http://localhost:8080/score
curl http://localhost:8080/score?lat=51.5\&lon=-0.1
curl http://localhost:8080/health
```

### Docker

```bash
# Build image (reads Dockerfile, installs deps, bundles code)
docker build -t sun-intensity-agent:latest .

# Run server (default CMD)
docker run -e OWM_API_KEY=sk_... -e LAT=38.9 -e LON=-77.0 \
           -p 8080:8080 sun-intensity-agent:latest

# Run CLI inside container
docker run -e OWM_API_KEY=sk_... \
           sun-intensity-agent:latest \
           python -m sun_intensity_agent.cli --lat 38.9 --lon -77.0
```

## File Organization

### Application Code

- **config.py** — Settings class with `validate_location()` method. Loads OWM_API_KEY (required), LAT/LON/PORT (optional) from environment.
- **owm_client.py** — Single `fetch_forecast(api_key, lat, lon)` function. Returns dict with `daily` and `hourly` arrays; raises OWMAuthError/OWMRateLimitError/OWMRequestError.
- **scoring.py** — `compute_score(daily, hourly)` pure function. Takes OWM daily/hourly arrays, returns dict with score (0-100), sunrise/sunset (ISO), daylight_hours, avg_cloud_cover_pct.
- **core.py** — `get_score(lat=None, lon=None)` orchestrator. Validates location, calls fetch_forecast, calls compute_score, wraps result with location + generated_at timestamp.
- **cli.py** — argparse CLI: `--lat`, `--lon`, `--pretty` flags. Prints JSON to stdout, errors to stderr, exits with code 0/1/2.
- **server.py** — FastAPI app: GET /score (with optional ?lat=&lon= query params), GET /health. Returns JSON or HTTPException with appropriate status codes.

### Tests

- **test_scoring.py** — 5 unit tests: clear day, overcast day, midday-vs-dawn weighting, fallback to daily clouds, ISO timestamp format.
- **test_integration.py** — 3 integration tests: clear day (mock OWM response), overcast day (mock OWM response), response structure validation.

All tests use constructed fixtures (no network calls) and are fully deterministic.

### Config & Deployment

- **requirements.txt** — FastAPI, uvicorn, requests, pydantic, pydantic-settings, pytest
- **Dockerfile** — python:3.12-slim, installs deps, copies code, default CMD runs uvicorn server
- **.env.example** — Template for OWM_API_KEY, LAT, LON, PORT
- **.gitignore** — Python cache, IDE files, .env (secrets), __pycache__

## Typical Workflows

### Adding a New Scoring Factor

1. Modify `scoring.py:compute_score()` — add calculation, update return dict
2. Add test in `test_scoring.py` or `test_integration.py` with mock data
3. Run `pytest tests/ -v` to verify
4. Update README.md algorithm section if the math changed

### Debugging an API Error

1. Check `owm_client.py` error handling — is the HTTP status code mapped to the right exception?
2. If it's a 401, verify the user has subscribed to "One Call 3.0" (not just any OWM product)
3. Look at error message text — auth errors point to https://openweathermap.org/api/one-call-3
4. For 429 (rate limit), check free tier is 1,000 calls/day; user may have hit the quota or misconfigured their plan

### Changing the Score Scale (e.g., 0-100 → 0-10)

1. Update the constant in `scoring.py:compute_score()`: `score = round(100 * avg_clear_sky)` → `score = round(10 * avg_clear_sky)`
2. Update test expectations in `test_scoring.py` (e.g., `assert result["score"] == 100` → `assert result["score"] == 10`)
3. Update README.md and DEMO.md examples
4. Update score_description in `scoring.py`

Note: The downstream agent (mcp__solax-cloud__set_battery_self_use_mode) expects the current 0-100 scale; coordinate any changes with that system's owner.

## Backoff Retry Logic

The `fetch_forecast()` function includes automatic exponential backoff for transient failures:

**Retried (with backoff):**
- 429 (rate limit) — uses `Retry-After` header if present
- 5xx (server error) — transient, may recover
- Timeouts & connection errors — network issues, may recover

**Not retried (permanent failures):**
- 401 (auth) — invalid API key or subscription issue
- 4xx client errors (400, 403, 404, etc.) — malformed request, won't help to retry

**Configuration:**
```python
from sun_intensity_agent.owm_client import RetryConfig, fetch_forecast

# Custom backoff config
config = RetryConfig(max_retries=5, base_delay=2.0, max_delay=120.0)
result = fetch_forecast(api_key, lat, lon, retry_config=config)

# Default: 3 retries, 1s base delay, 60s max delay, ±25% jitter
```

**Backoff formula:**
- Delay = min(base_delay × 2^attempt, max_delay) ± 25% jitter
- Example: attempt 0→1s, 1→2s, 2→4s, 3→8s (with jitter)
- Jitter prevents thundering herd when multiple clients retry simultaneously

## Error Handling Patterns

Both CLI and server follow the same error→JSON pattern:

**CLI (to stderr):**
```json
{"error": "API key is invalid or One Call 3.0 is not enabled for this key. Subscribe to One Call 3.0 at https://openweathermap.org/api/one-call-3"}
```
Exit code: 1 (for known OWM errors), 2 (for unexpected errors)

**Server (HTTP response body):**
```json
{"detail": "API key is invalid or One Call 3.0 is not enabled for this key. Subscribe to One Call 3.0 at https://openweathermap.org/api/one-call-3"}
```
Status code: 401 (auth), 429 (rate limit), 502 (OWM server error), 400 (validation), 500 (unexpected)

## Testing Strategy

- **Unit tests** (test_scoring.py): Pure function with constructed inputs, no network. Validates algorithm correctness.
- **Integration tests** (test_integration.py): Mock OWM response structures, verify end-to-end flow without hitting real API.
- **Manual testing**: `python -m sun_intensity_agent.cli --pretty` with real API key to verify round-trip.
- **No mocking of scoring.py**: It's pure, so fixtures are just dicts.

## Deployment Notes

### API Key Management

- `OWM_API_KEY` must be set as environment variable (never in code, .env, or git)
- In Docker: pass at runtime (`docker run -e OWM_API_KEY=...`)
- In production: use secrets manager (GitHub Secrets, K8s Secrets, etc.)

### Rate Limiting

- Free tier: 1,000 calls/day
- Each score query = 1 API call
- Daily cron job or hourly checks are well within limits
- If hitting 429, check user hasn't exceeded plan or add exponential backoff retry logic

### Timezone Handling

All timestamp operations use Unix epoch (seconds since 1970 UTC):
- OWM returns sunrise/sunset as Unix epoch (no timezone ambiguity)
- Hourly dt is also Unix epoch
- Comparison `sunrise <= dt < sunset` works in any timezone
- Output includes "+00:00" suffix (UTC) for clarity, but times are calculated timezone-independently

## Common Pitfalls

1. **Forgetting to subscribe to One Call 3.0** — OWM account may have other products enabled (weather, air quality, etc.) but One Call 3.0 is opt-in per product. Error message clearly points to the subscription page.

2. **Modifying scoring.py without updating tests** — The algorithm is the core logic; tests should drive any changes. Add test cases before refactoring the scoring logic.

3. **Docker image won't build** — Requires Docker daemon running. Dockerfile syntax is correct; just can't spin up containers without the daemon.

4. **Location validation** — Coordinates are validated in `config.py:validate_location()`. Lat must be -90..90, lon must be -180..180. Both must be floats.

5. **Confusing inverted scores** — The service outputs higher = clearer (100 = clear, 0 = overcast). The downstream agent inverts this to get charge percentage. Don't invert in this service.

## Performance & Limits

- API call: ~500ms-1s (network to OWM + parsing response)
- Scoring: <1ms (pure math)
- Memory: ~50-100 MB for the service
- CPU: Minimal (I/O bound)
- OWM free tier: 1,000 calls/day (enough for hourly checks or daily cron)

## Further Reading

- **README.md** — Full usage guide, algorithm explanation, Docker setup
- **DEMO.md** — Real-world example workflows (scheduled jobs, HTTP integration, dashboards)
- **IMPLEMENTATION_SUMMARY.md** — Feature overview and integration notes
- **OpenWeatherMap API docs** — https://openweathermap.org/api/one-call-3
