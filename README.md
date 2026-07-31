# Sun Intensity Agent

A Python service that fetches tomorrow's weather forecast from OpenWeatherMap and produces a single 0-100 "clear sky score" to help determine solar charging requirements.

## Features

- Queries OpenWeatherMap One Call API 3.0 for tomorrow's daylight hours forecast
- Computes a weighted sun intensity score (0-100) based on:
  - Sunrise/sunset times
  - Hourly cloud cover percentage
  - Solar potential weighting (higher at midday, lower at dawn/dusk)
- Runs as both:
  - CLI tool: `python -m sun_intensity_agent.cli [--lat LAT --lon LON]`
  - HTTP server: `GET /score?lat=38.9&lon=-77.0`
- Containerized: Single `Dockerfile` supports both modes
- Pure Python with minimal dependencies

## Prerequisites

- Python 3.9+
- OpenWeatherMap API key with "One Call 3.0" subscription enabled (free tier: 1,000 calls/day)
  - Get one at: https://openweathermap.org/api/one-call-3
- Environment variables:
  - `OWM_API_KEY` (required)
  - `LAT` (optional, overridable per-call)
  - `LON` (optional, overridable per-call)
  - `PORT` (optional, default: 8080 for server mode)

## Installation

```bash
pip install -r requirements.txt
```

## CLI Usage

```bash
# Using env vars
export OWM_API_KEY=your_key_here
export LAT=38.9
export LON=-77.0
python -m sun_intensity_agent.cli --pretty

# Override location per-call
python -m sun_intensity_agent.cli --lat 51.5 --lon -0.1 --pretty

# Example output:
# {
#   "date": "2026-08-01",
#   "location": {
#     "lat": 38.9,
#     "lon": -77.0
#   },
#   "sunrise": "2026-08-01T10:12:00+00:00",
#   "sunset": "2026-08-02T00:45:00+00:00",
#   "daylight_hours": 14.55,
#   "score": 72,
#   "score_description": "0-100; higher = clearer skies / more solar potential expected tomorrow",
#   "avg_cloud_cover_pct": 35.2,
#   "generated_at": "2026-07-31T23:00:00+00:00"
# }
```

Exit codes:
- `0`: Success
- `1`: Auth error, rate limit, or OWM request error
- `2`: Unexpected error

## Server Usage

```bash
# Start the server
export OWM_API_KEY=your_key_here
export LAT=38.9
export LON=-77.0
uvicorn sun_intensity_agent.server:app --host 0.0.0.0 --port 8080

# Query the endpoint
curl http://localhost:8080/score
curl http://localhost:8080/score?lat=51.5&lon=-0.1

# Health check
curl http://localhost:8080/health
```

## Docker Usage

```bash
# Build the image
docker build -t sun-intensity-agent:latest .

# Run as HTTP server (default)
docker run -e OWM_API_KEY=your_key_here \
           -e LAT=38.9 \
           -e LON=-77.0 \
           -p 8080:8080 \
           sun-intensity-agent:latest

# Run as CLI
docker run -e OWM_API_KEY=your_key_here \
           sun-intensity-agent:latest \
           python -m sun_intensity_agent.cli --lat 38.9 --lon -77.0
```

## Score Semantics

The score is a 0-100 integer representing expected solar potential for tomorrow's daylight hours:

- **100**: Fully clear skies → expect strong solar generation → charge less from grid overnight
- **0**: Fully overcast → expect minimal solar generation → charge more from grid overnight
- **50**: Partly cloudy conditions

The score is computed as a weighted average of clear-sky percentages across all daylight hours, with weighting that:
- Peaks at solar noon
- Tapers toward zero at sunrise/sunset

This makes midday cloud cover have more impact than dawn/dusk clouds.

## Scoring Algorithm

For tomorrow's forecast:

1. Extract sunrise/sunset times from daily forecast
2. Filter hourly forecast to entries within daylight window
3. For each hour:
   - Compute `clear_sky = 1 - (clouds_pct / 100)`
   - Compute `weight = sin(π × (t - sunrise) / (sunset - sunrise))`
   - This makes weight peak at solar noon, ~0 at sunrise/sunset
4. `score = round(100 × Σ(weight × clear_sky) / Σ(weight))`

If no hourly data exists in the window (shouldn't happen with 48-hour coverage), falls back to `100 - daily_clouds_pct`.

## Testing

Run unit tests:

```bash
pytest tests/ -v
```

Tests cover:
- Fully clear day → score ~100
- Fully overcast day → score ~0
- Midday clouds vs dawn/dusk clouds (proves weighting)
- Fallback when no hourly data
- ISO timestamp formatting

## Project Structure

```
sun_intensity_agent/
  __init__.py          # Package init
  __main__.py          # CLI entry point for python -m
  config.py            # Env var loading and validation
  owm_client.py        # HTTP client to OpenWeatherMap (handles auth/rate-limit errors)
  scoring.py           # Pure function: (daily, hourly) -> result dict
  core.py              # Orchestrator: fetch -> score -> envelope
  cli.py               # CLI interface (argparse)
  server.py            # FastAPI HTTP server
tests/
  test_scoring.py      # Unit tests (no network)
Dockerfile             # Single image for both CLI and server modes
requirements.txt       # Dependencies
README.md              # This file
```

## Error Handling

The service handles OpenWeatherMap errors gracefully:

- **401 (Auth)**: Points to One Call 3.0 subscription page
- **429 (Rate limit)**: Clear message to retry later
- **5xx (Server error)**: Treated as temporary failure
- **Timeout/Connection errors**: Wrapped in OWMRequestError

Both CLI and server return clean JSON error messages; server returns appropriate HTTP status codes.

## Integration with Downstream Systems

The JSON output is designed to be consumed by downstream agents. The `score` field is not inverted:

- **Higher score = clearer skies = more solar potential**
- Downstream agent inverts this to determine overnight charge percentage

Example downstream integration:
```python
# Pseudo-code in downstream agent
charge_percent = 100 - sun_intensity_score  # Invert for charge requirement
```

## Development

Install dev dependencies:
```bash
pip install -r requirements.txt
```

Run tests:
```bash
pytest tests/ -v
```

Test the CLI locally:
```bash
export OWM_API_KEY=your_key
python -m sun_intensity_agent.cli --lat 38.9 --lon -77.0 --pretty
```

Test the server locally:
```bash
export OWM_API_KEY=your_key
export LAT=38.9
export LON=-77.0
uvicorn sun_intensity_agent.server:app --reload
```

## License

See LICENSE file (if applicable).
