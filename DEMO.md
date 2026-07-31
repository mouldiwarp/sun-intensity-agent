# Sun Intensity Agent - Demo & Examples

This document shows practical examples of using the sun intensity agent in different scenarios.

## Quick Start

### 1. Set up environment

```bash
cp .env.example .env
# Edit .env and add your OpenWeatherMap API key:
# OWM_API_KEY=sk_openweathermap_...
# LAT=38.9
# LON=-77.0
```

### 2. Run CLI

```bash
# Using env vars
python -m sun_intensity_agent.cli --pretty

# Override location for a one-off query
python -m sun_intensity_agent.cli --lat 51.5 --lon -0.1 --pretty

# Piping output to jq for further processing
python -m sun_intensity_agent.cli | jq '.score'
```

### 3. Start the HTTP server

```bash
uvicorn sun_intensity_agent.server:app --reload
# Server runs on http://localhost:8080
```

## Example Workflows

### Workflow 1: Daily scheduled job

Query the score every evening to decide battery charge level for the next day:

```bash
#!/bin/bash
# solar_charge_scheduler.sh

export OWM_API_KEY="your_api_key"
export LAT=38.9
export LON=-77.0

# Get tomorrow's score
RESULT=$(python -m sun_intensity_agent.cli)
SCORE=$(echo "$RESULT" | jq '.score')

# Calculate charge requirement: invert the score
# Score 100 (clear) = charge 0% (sun will power it)
# Score 0 (overcast) = charge 100% (need grid power)
CHARGE_PERCENT=$((100 - SCORE))

echo "Tomorrow's sun intensity: $SCORE"
echo "Recommended battery charge from grid: $CHARGE_PERCENT%"

# Call your battery control system (e.g., SOLAX)
# curl -X POST http://battery-control/charge -d "{\"percent\": $CHARGE_PERCENT}"
```

### Workflow 2: HTTP endpoint integration

Use the HTTP server in a containerized environment:

```bash
# Start the server
docker run -e OWM_API_KEY=sk_... \
           -e LAT=38.9 \
           -e LON=-77.0 \
           -p 8080:8080 \
           sun-intensity-agent:latest
```

Then query it from another service:

```python
import requests

response = requests.get('http://sun-intensity-agent:8080/score')
score = response.json()['score']

# Integrate with your solar control system
charge_percent = 100 - score  # Invert for charge requirement
print(f"Set battery charge to {charge_percent}%")
```

### Workflow 3: Multiple locations

Monitor solar potential across several panel installations:

```bash
#!/bin/bash
LOCATIONS=(
  "New York:40.7128:-74.0060"
  "London:51.5074:-0.1278"
  "Sydney:-33.8688:151.2093"
)

export OWM_API_KEY="your_api_key"

for loc in "${LOCATIONS[@]}"; do
  IFS=':' read -r name lat lon <<< "$loc"
  SCORE=$(python -m sun_intensity_agent.cli --lat $lat --lon $lon | jq '.score')
  echo "$name: score=$SCORE"
done
```

### Workflow 4: Monitoring dashboard

Set up a cron job to log scores periodically and visualize trends:

```bash
#!/bin/bash
# Log scores every 6 hours
(crontab -l 2>/dev/null; echo "0 */6 * * * /path/to/log_scores.sh") | crontab -

# log_scores.sh
export OWM_API_KEY="your_api_key"
export LAT=38.9
export LON=-77.0

RESULT=$(python -m sun_intensity_agent.cli)
TIMESTAMP=$(echo "$RESULT" | jq -r '.generated_at')
SCORE=$(echo "$RESULT" | jq '.score')
DATE=$(echo "$RESULT" | jq -r '.date')

echo "$TIMESTAMP,$DATE,$SCORE" >> /var/log/sun_intensity.csv
```

## Error Scenarios & Recovery

### Scenario 1: API key not subscribed to One Call 3.0

**Error:**
```
{"error": "API key is invalid or One Call 3.0 is not enabled for this key. Subscribe to One Call 3.0 at https://openweathermap.org/api/one-call-3"}
```

**Fix:**
1. Visit https://openweathermap.org/api/one-call-3
2. Log in to your account
3. Subscribe to "One Call 3.0" (free tier: 1,000 calls/day)
4. Re-run the command

### Scenario 2: Rate limit exceeded

**Error:**
```
{"error": "OpenWeatherMap API rate limit exceeded. Please retry later."}
```

**Fix:**
- Wait a few seconds and retry
- If frequent, upgrade your OWM subscription
- Implement exponential backoff in your calling code:

```python
import time
from sun_intensity_agent.core import get_score
from sun_intensity_agent.owm_client import OWMRateLimitError

max_retries = 3
for attempt in range(max_retries):
    try:
        result = get_score()
        break
    except OWMRateLimitError:
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            time.sleep(wait_time)
        else:
            raise
```

### Scenario 3: Network timeout

**Error:**
```
{"error": "Connection error: HTTPSConnectionPool(...)"}
```

**Fix:**
- Check your internet connection
- OWM may be experiencing issues; retry after a minute
- Implement timeouts and retries in your client code

## Response Examples

### Clear day forecast (likely to use solar)

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
  "score": 92,
  "score_description": "0-100; higher = clearer skies / more solar potential expected tomorrow",
  "avg_cloud_cover_pct": 5.1,
  "generated_at": "2026-07-31T23:00:00+00:00"
}
```

**Interpretation:** 92% clear skies expected tomorrow. Charge battery from grid only 8% (if you have 100% capacity).

### Overcast day forecast (need grid charging)

```json
{
  "date": "2026-08-02",
  "location": {
    "lat": 38.9,
    "lon": -77.0
  },
  "sunrise": "2026-08-02T10:13:00+00:00",
  "sunset": "2026-08-03T00:44:00+00:00",
  "daylight_hours": 14.52,
  "score": 12,
  "score_description": "0-100; higher = clearer skies / more solar potential expected tomorrow",
  "avg_cloud_cover_pct": 91.3,
  "generated_at": "2026-08-01T23:00:00+00:00"
}
```

**Interpretation:** Only 12% clear skies expected. Charge battery from grid 88% to be safe.

### Partly cloudy (typical mid-range scenario)

```json
{
  "date": "2026-08-03",
  "location": {
    "lat": 38.9,
    "lon": -77.0
  },
  "sunrise": "2026-08-03T10:14:00+00:00",
  "sunset": "2026-08-04T00:43:00+00:00",
  "daylight_hours": 14.48,
  "score": 58,
  "score_description": "0-100; higher = clearer skies / more solar potential expected tomorrow",
  "avg_cloud_cover_pct": 48.7,
  "generated_at": "2026-08-02T23:00:00+00:00"
}
```

**Interpretation:** Mixed clouds throughout the day. Charge battery 42% from grid as a middle ground.

## Testing Your Integration

### Unit tests

```bash
pytest tests/ -v
```

All tests pass and cover:
- Clear sky scenarios
- Overcast scenarios
- Weighting verification (midday clouds matter more)
- Fallback behavior
- ISO timestamp formatting

### Manual testing

```bash
# Test CLI with real API
export OWM_API_KEY="your_key"
python -m sun_intensity_agent.cli --lat 38.9 --lon -77.0 --pretty

# Test server locally
python -m uvicorn sun_intensity_agent.server:app --reload
# In another terminal:
curl http://localhost:8080/score?lat=38.9\&lon=-77.0 | jq '.'
curl http://localhost:8080/health
```

### Docker testing

```bash
# Build image
docker build -t sun-intensity-agent:latest .

# Run server
docker run -e OWM_API_KEY=sk_... -e LAT=38.9 -e LON=-77.0 -p 8080:8080 sun-intensity-agent

# Run CLI in container
docker run -e OWM_API_KEY=sk_... sun-intensity-agent python -m sun_intensity_agent.cli --lat 38.9 --lon -77.0
```

## Performance & Costs

- **API calls**: 1 call per score query
- **OWM free tier**: 1,000 calls/day (plenty for daily use or hourly checks)
- **Latency**: ~500ms-1s per request (network to OWM + processing)
- **Memory**: ~50-100 MB for the service
- **CPU**: Minimal (compute is lightweight, I/O bound on OWM API)

If querying hourly (24 calls/day), you're well under the free tier limit.

## Next Steps

1. Get your OWM API key and subscribe to One Call 3.0
2. Copy `.env.example` to `.env` and fill in your details
3. Run `python -m sun_intensity_agent.cli --pretty` to test
4. Choose your deployment mode (CLI cron job, containerized server, etc.)
5. Integrate the score with your battery/solar control system
