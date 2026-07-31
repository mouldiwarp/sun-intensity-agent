# Sun Intensity Agent

**A production-grade Python service for forecasting solar panel performance using OpenWeatherMap API.**

Generate a 0-100 "clear sky score" for tomorrow's daylight hours to inform solar battery charging decisions. The service features automatic retry with exponential backoff, comprehensive test coverage, and both CLI and HTTP server modes.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-55%2F55%20passing-brightgreen)](./tests/)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

## Quick Start

### Prerequisites

- Python 3.9+
- OpenWeatherMap API key with "One Call 3.0" subscription (free: 1,000 calls/day)
- Docker (optional, for containerized deployment)

### 1. Get API Key

Visit [OpenWeatherMap One Call 3.0](https://openweathermap.org/api/one-call-3) and:
1. Create an account
2. Subscribe to "One Call 3.0" (free tier available)
3. Copy your API key

### 2. Install & Configure

```bash
# Clone and install
git clone <repo-url>
cd sun-intensity-agent
pip install -r requirements.txt

# Set environment variables
export OWM_API_KEY="your_api_key_here"
export LAT=38.9      # Your latitude
export LON=-77.0     # Your longitude
```

### 3. Run

**CLI Mode:**
```bash
python -m sun_intensity_agent.cli --pretty
```

**Server Mode:**
```bash
uvicorn sun_intensity_agent.server:app --host 0.0.0.0 --port 8080
curl http://localhost:8080/score
```

**Docker:**
```bash
docker build -t sun-intensity-agent .
docker run -e OWM_API_KEY=your_key -e LAT=38.9 -e LON=-77.0 -p 8080:8080 sun-intensity-agent
```

## Features

### ⚡ Core Functionality
- **Tomorrow's Forecast** — Queries 48-hour weather forecast
- **Smart Scoring** — Weighted algorithm that prioritizes midday cloud cover
- **Error Resilience** — Automatic retry with exponential backoff for transient failures
- **Multi-Mode** — Run as CLI tool or HTTP service
- **Containerized** — Single Docker image, both modes

### 🛡️ Resilience
- **Rate Limit Handling** — Respects HTTP 429 with Retry-After header
- **Server Error Retry** — Retries 5xx with exponential backoff
- **Connection Resilience** — Handles timeouts and connection errors
- **Auth Error Handling** — Clear error messages for credential issues

### 🧪 Quality Assurance
- **55 Comprehensive Tests** — 100% passing
- **No Network Dependencies** — All tests fully mocked
- **Edge Case Coverage** — Polar regions, equator, boundary conditions
- **Type Hints** — Full type safety throughout

### 📊 Output Format

```json
{
  "date": "2026-08-01",
  "location": {
    "lat": 38.9,
    "lon": -77.0
  },
  "sunrise": "2026-08-01T10:12:00+00:00",
  "sunset": "2026-08-02T00:45:00+00:00",
  "daylight_hours": 14.55,
  "score": 72,
  "score_description": "0-100; higher = clearer skies / more solar potential expected tomorrow",
  "avg_cloud_cover_pct": 35.2,
  "generated_at": "2026-07-31T23:00:00+00:00"
}
```

## Understanding the Score

The **sun intensity score (0-100)** represents expected solar potential for tomorrow's daylight hours:

| Score | Condition | Interpretation |
|-------|-----------|-----------------|
| **90-100** | Clear skies | Rely on solar, minimal grid charging needed |
| **70-89** | Mostly clear | Good solar day, moderate grid charging |
| **50-69** | Partly cloudy | Mixed power, balanced grid charging |
| **30-49** | Mostly cloudy | Limited solar, significant grid charging |
| **0-29** | Overcast | Minimal solar, charge fully from grid |

### Algorithm Details

The score uses **sine-weighted averaging** across daylight hours:

1. **Sunrise/Sunset** — Extract from daily forecast (Unix epoch timestamps)
2. **Daylight Filter** — Select hourly forecasts within sunrise-sunset window
3. **Weight Calculation** — `weight = sin(π × (t - sunrise) / daylight_duration)`
   - Peaks at solar noon (highest value)
   - Tapers to ~0 at sunrise/sunset
4. **Clear Sky** — `clear_sky = 1 - (clouds_pct / 100)`
5. **Final Score** — `score = 100 × Σ(weight × clear_sky) / Σ(weight)`

**Result:** Midday cloud cover impacts the score much more than clouds at dawn/dusk.

## Installation

### From Source

```bash
git clone <repo-url>
cd sun-intensity-agent

# Install dependencies
pip install -r requirements.txt

# (Optional) Install dev dependencies for testing
pip install -e ".[dev]"
```

### From Docker

```bash
docker build -t sun-intensity-agent:latest .
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OWM_API_KEY` | ✅ Yes | — | OpenWeatherMap API key |
| `LAT` | ✗ No | — | Panel location latitude (-90 to 90) |
| `LON` | ✗ No | — | Panel location longitude (-180 to 180) |
| `PORT` | ✗ No | 8080 | Server port |

### Example `.env` File

```bash
OWM_API_KEY=sk_your_openweathermap_key_here
LAT=38.9
LON=-77.0
PORT=8080
```

### Per-Call Overrides

**CLI:**
```bash
python -m sun_intensity_agent.cli --lat 51.5 --lon -0.1 --pretty
```

**HTTP:**
```bash
curl http://localhost:8080/score?lat=51.5&lon=-0.1
```

## Usage

### Command Line Interface

**Run with defaults (from env vars):**
```bash
python -m sun_intensity_agent.cli --pretty
```

**Override location:**
```bash
python -m sun_intensity_agent.cli --lat 51.5 --lon -0.1 --pretty
```

**Pipe output:**
```bash
python -m sun_intensity_agent.cli | jq '.score'
```

**Exit codes:**
- `0` — Success
- `1` — API error, validation error, rate limit
- `2` — Unexpected error

### HTTP Server

**Start server:**
```bash
uvicorn sun_intensity_agent.server:app --host 0.0.0.0 --port 8080
```

**Get score (use env vars):**
```bash
curl http://localhost:8080/score
```

**Get score (override location):**
```bash
curl http://localhost:8080/score?lat=51.5&lon=-0.1
```

**Health check:**
```bash
curl http://localhost:8080/health
# {"status": "ok"}
```

### Docker Container

**Server mode (default):**
```bash
docker run \
  -e OWM_API_KEY=sk_your_key \
  -e LAT=38.9 \
  -e LON=-77.0 \
  -p 8080:8080 \
  sun-intensity-agent:latest
```

**CLI mode:**
```bash
docker run \
  -e OWM_API_KEY=sk_your_key \
  sun-intensity-agent:latest \
  python -m sun_intensity_agent.cli --lat 38.9 --lon -77.0
```

## API Reference

### GET `/score`

Get tomorrow's sun intensity score.

**Query Parameters:**
- `lat` (float, optional) — Latitude override
- `lon` (float, optional) — Longitude override

**Response (200 OK):**
```json
{
  "date": "2026-08-01",
  "location": {"lat": 38.9, "lon": -77.0},
  "sunrise": "2026-08-01T10:12:00+00:00",
  "sunset": "2026-08-02T00:45:00+00:00",
  "daylight_hours": 14.55,
  "score": 72,
  "score_description": "0-100; higher = clearer skies / more solar potential expected tomorrow",
  "avg_cloud_cover_pct": 35.2,
  "generated_at": "2026-07-31T23:00:00+00:00"
}
```

**Error Responses:**

| Status | Error | Meaning |
|--------|-------|---------|
| **400** | Missing/invalid location | LAT/LON not provided or out of range |
| **401** | Unauthorized | Invalid API key or missing One Call 3.0 subscription |
| **429** | Too Many Requests | Rate limit exceeded; retry later |
| **502** | Bad Gateway | OpenWeatherMap server error; retry later |
| **500** | Internal Server Error | Unexpected error |

### GET `/health`

Health check endpoint.

**Response (200 OK):**
```json
{"status": "ok"}
```

## Development

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_scoring.py -v

# Single test
pytest tests/test_scoring.py::test_clear_sky_day -v

# With coverage
pytest tests/ --cov=sun_intensity_agent --cov-report=html
```

### Project Structure

```
sun_intensity_agent/
├── __init__.py              # Package metadata
├── __main__.py              # CLI entry point
├── constants.py             # Centralized configuration
├── errors.py                # Exception hierarchy + helpers
├── config.py                # Settings management
├── owm_client.py            # OpenWeatherMap API client
├── scoring.py               # Solar intensity algorithm
├── core.py                  # Orchestrator
├── cli.py                   # CLI interface
└── server.py                # FastAPI HTTP server

tests/
├── test_config.py           # 19 config tests
├── test_owm_client.py       # 17 API + retry tests
├── test_scoring.py          # 16 algorithm tests
└── test_integration.py      # 3 end-to-end tests

docs/
├── ARCHITECTURE.md          # System design
├── DEVELOPMENT.md           # Developer guide
├── DEPLOYMENT.md            # Deployment guide
└── TROUBLESHOOTING.md       # Common issues
```

### Code Quality Tools

```bash
# Type checking
mypy sun_intensity_agent/

# Linting
flake8 sun_intensity_agent/ tests/

# Code formatting
black sun_intensity_agent/ tests/

# Security scanning
bandit -r sun_intensity_agent/
```

### Common Development Tasks

```bash
# Run tests with coverage
pytest tests/ --cov=sun_intensity_agent --cov-report=term-missing

# Run single test file
pytest tests/test_scoring.py -v

# Run tests matching pattern
pytest tests/ -k "clear_sky" -v

# Run with verbose output
pytest tests/ -vv --tb=long

# Run in watch mode (requires pytest-watch)
ptw tests/
```

## Integration with Solar Systems

### Example: Charge Battery Control

```python
import requests
from datetime import datetime

def set_battery_charge(percentage: int) -> None:
    """Set battery charge based on sun intensity score."""
    # Get tomorrow's score
    response = requests.get("http://localhost:8080/score")
    data = response.json()
    score = data["score"]
    
    # Invert: higher score (clearer) = charge less from grid
    charge_percent = 100 - score
    
    # Call battery control system
    # (example: Solax inverter API)
    print(f"Setting battery charge to {charge_percent}%")
    # battery_api.set_charge(charge_percent)

if __name__ == "__main__":
    set_battery_charge(0)  # Will charge based on tomorrow's forecast
```

### Example: Scheduled Daily Run

```bash
#!/bin/bash
# Run every evening at 8 PM to set next day's battery charge

0 20 * * * /path/to/solar_charge_scheduler.sh

# solar_charge_scheduler.sh
export OWM_API_KEY="sk_your_key"
export LAT=38.9
export LON=-77.0

RESULT=$(python -m sun_intensity_agent.cli)
SCORE=$(echo "$RESULT" | jq '.score')
CHARGE_PERCENT=$((100 - SCORE))

echo "Tomorrow's sun score: $SCORE, charging battery to $CHARGE_PERCENT%"
# Call your battery control system here
```

## Troubleshooting

### Common Issues

**Error: "API key is invalid or One Call 3.0 is not enabled"**
- ✅ Check that `OWM_API_KEY` is set correctly
- ✅ Verify you subscribed to "One Call 3.0" at https://openweathermap.org/api/one-call-3
- ✅ Wait a few moments for the subscription to activate

**Error: "Latitude and longitude must be provided"**
- ✅ Set `LAT` and `LON` environment variables
- ✅ Or pass `--lat` and `--lon` CLI flags
- ✅ Or use `?lat=&lon=` query parameters

**Error: "Rate limit exceeded"**
- ✅ Wait a few seconds and retry
- ✅ The service automatically retries with backoff
- ✅ If frequent, upgrade your OWM subscription plan

**Docker container exits immediately**
- ✅ Check environment variables: `docker run -e OWM_API_KEY=... `
- ✅ View logs: `docker logs <container-id>`
- ✅ Run interactively: `docker run -it <image> bash`

See [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) for more details.

## Performance & Limits

### API Quotas
- **Free tier:** 1,000 calls/day
- **Cost:** Free (including production use)
- **Rate limiting:** Respects OpenWeatherMap limits

### Service Performance
- **API latency:** ~500ms-1s per request (network to OWM)
- **Memory usage:** ~50-100 MB for the service
- **CPU usage:** Minimal (I/O bound)

### Backoff Timing (Default)
- **Attempt 0:** ~1s (0.75-1.25s with jitter)
- **Attempt 1:** ~2s (1.5-2.5s)
- **Attempt 2:** ~4s (3-5s)
- **Attempt 3:** ~8s (6-10s)
- **Max:** 60s (with ±25% jitter)

## Architecture

The service follows a layered architecture:

```
┌─────────────────────────────────────┐
│  CLI / HTTP Server (Interfaces)     │
├─────────────────────────────────────┤
│  Core (Orchestrator)                │
├─────────────────────────────────────┤
│  OWM Client │ Scoring │ Config      │
├─────────────────────────────────────┤
│  Constants  │  Errors (Shared)      │
├─────────────────────────────────────┤
│  OpenWeatherMap API (External)      │
└─────────────────────────────────────┘
```

See [ARCHITECTURE.md](./docs/ARCHITECTURE.md) for detailed design documentation.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest tests/ -v`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

### Code Standards
- All code must have type hints
- All functions must have docstrings
- New features require tests
- All tests must pass before merge

## Testing

The project includes comprehensive test coverage:

- **Unit Tests:** Scoring algorithm, config validation, error handling
- **Integration Tests:** End-to-end with mocked API
- **Backoff Tests:** Retry logic with exponential delays
- **Edge Cases:** Polar regions, equator, boundary conditions

```bash
pytest tests/ -v --cov=sun_intensity_agent --cov-report=term-missing
```

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## Support

For issues, questions, or suggestions:

1. Check [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)
2. Review [ARCHITECTURE.md](./docs/ARCHITECTURE.md)
3. See [DEVELOPMENT.md](./docs/DEVELOPMENT.md) for development setup
4. Open an issue on GitHub

## Roadmap

**Completed:**
- ✅ OpenWeatherMap API integration
- ✅ Weighted solar scoring algorithm
- ✅ Exponential backoff retry logic
- ✅ CLI and HTTP server modes
- ✅ Docker containerization
- ✅ Comprehensive test suite (55 tests)
- ✅ Full type hints

**Planned:**
- 🔄 Circuit breaker pattern for persistent failures
- 🔄 Structured logging with context
- 🔄 Metrics/telemetry (Prometheus)
- 🔄 Async/await for high throughput
- 🔄 GraphQL API option
- 🔄 Web UI dashboard

## References

- [OpenWeatherMap One Call 3.0 API](https://openweathermap.org/api/one-call-3)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

---

**Built with ❤️ for solar energy enthusiasts**

*Last updated: 2026-07-31*
