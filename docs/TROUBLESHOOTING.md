# Troubleshooting Guide

## API Key & Authentication Issues

### Error: "API key is invalid or One Call 4.0 is not enabled for this key"

**Status Code:** 401 Unauthorized

**Causes:**
- API key is incorrect or typo'd
- One Call 4.0 subscription not enabled
- API key has wrong permissions

**Solutions:**

1. **Verify API Key**
   ```bash
   # Check environment variable is set
   echo $OWM_API_KEY
   # Should output: sk_xxxxx...
   
   # Verify it's not empty
   if [ -z "$OWM_API_KEY" ]; then
       echo "ERROR: OWM_API_KEY not set"
   fi
   ```

2. **Enable One Call 4.0 Subscription**
   - Go to https://openweathermap.org/api/one-call-4
   - Log in to your OpenWeatherMap account
   - Click "Subscribe" on "One Call 4.0" product
   - Free tier: 1,000 calls/day (should appear immediately)
   - Wait 1-2 minutes for activation

3. **Test API Key Directly**
   ```bash
   curl "https://api.openweathermap.org/data/4.0/onecall/timeline/1h?lat=38.9&lon=-77.0&appid=$OWM_API_KEY"
   ```
   - If this returns data, your key is valid
   - If it returns 401, check subscription status

4. **Generate New API Key**
   - Go to https://openweathermap.org/api/keys
   - Create a new API key
   - Wait 1 minute for activation
   - Test again

---

## Location Validation Errors

### Error: "Latitude and longitude must be provided via env vars or CLI/query parameters"

**Causes:**
- LAT/LON not set in environment
- Not passed via CLI flags or HTTP parameters

**Solutions:**

```bash
# Set environment variables
export OWM_API_KEY="sk_your_key"
export LAT=38.9
export LON=-77.0

# Or pass via CLI flags
python -m sun_intensity_agent.cli --lat 38.9 --lon -77.0

# Or pass via HTTP query parameters
curl http://localhost:8080/score?lat=38.9&lon=-77.0
```

### Error: "Latitude must be between -90 and 90"

**Causes:**
- Latitude value is outside valid range
- Coordinate format error (e.g., passing "38.9N" instead of 38.9)

**Valid Ranges:**
- Latitude: -90 to 90 (South Pole to North Pole)
- Longitude: -180 to 180 (West to East)

**Solutions:**

```bash
# ✅ Valid coordinates
curl http://localhost:8080/score?lat=38.9&lon=-77.0    # Washington, DC
curl http://localhost:8080/score?lat=51.5&lon=-0.1     # London
curl http://localhost:8080/score?lat=-33.9&lon=151.2   # Sydney

# ❌ Invalid coordinates
curl http://localhost:8080/score?lat=91.0&lon=-77.0    # Lat too high
curl http://localhost:8080/score?lat=38.9&lon=181.0    # Lon too high
```

---

## Rate Limiting Issues

### Error: "OpenWeatherMap API rate limit exceeded"

**Status Code:** 429 Too Many Requests

**Causes:**
- Exceeded 1,000 calls/day (free tier limit)
- Too many requests in short time
- Shared API key with multiple services

**Solutions:**

1. **Check Your Usage**
   - Visit https://openweathermap.org/api
   - View your account dashboard
   - Check number of API calls made

2. **Wait Before Retrying**
   - Service automatically retries with backoff
   - Default delay: 1s, 2s, 4s, 8s...
   - Manual retry: wait 60+ seconds

3. **Reduce Request Frequency**
   ```bash
   # Current: Run every hour (24 calls/day) ✅ FINE
   # Reduce: Run every 3 hours (8 calls/day) ✅ EVEN BETTER
   # Bad: Run every minute (1,440 calls/day) ❌ EXCEEDS QUOTA
   ```

4. **Upgrade Subscription**
   - Go to https://openweathermap.org/api
   - Choose paid plan if high volume needed
   - Plans start at ~$2-5/month for higher quotas

5. **Example: Cron Configuration**
   ```bash
   # Once per day (good)
   0 20 * * * python -m sun_intensity_agent.cli
   
   # Twice per day (good)
   0 6,18 * * * python -m sun_intensity_agent.cli
   
   # Every hour (24/day) - fine for free tier
   0 * * * * python -m sun_intensity_agent.cli
   
   # Every 5 minutes (288/day) - exceeds free tier
   */5 * * * * python -m sun_intensity_agent.cli
   ```

---

## Connection & Timeout Issues

### Error: "Connection error: [Connection timeout/refused]"

**Causes:**
- Network connectivity issue
- OpenWeatherMap API unavailable
- Firewall blocking outbound connections
- DNS resolution failure

**Solutions:**

1. **Check Network Connectivity**
   ```bash
   # Ping OpenWeatherMap
   ping api.openweathermap.org
   
   # DNS resolution
   nslookup api.openweathermap.org
   dig api.openweathermap.org
   ```

2. **Check Firewall**
   ```bash
   # Test connection to API endpoint
   telnet api.openweathermap.org 443
   
   # Or use curl with verbose output
   curl -v https://api.openweathermap.org/
   ```

3. **Check OWM Status**
   - Visit https://status.openweathermap.org/
   - Check if API is operational

4. **Retry Automatically**
   - The service automatically retries with exponential backoff
   - Default: 3 retries with 1s, 2s, 4s delays
   - No action needed, will eventually succeed or timeout

5. **Increase Timeout** (if needed)
   - Edit `constants.py`
   - Change `OWM_REQUEST_TIMEOUT` from 10 to 15 or 20 seconds

---

## Docker Issues

### Error: "Cannot connect to Docker daemon"

**Causes:**
- Docker not installed
- Docker daemon not running
- User doesn't have Docker permissions

**Solutions:**

```bash
# Check if Docker is running
docker ps

# Start Docker daemon (Linux)
sudo systemctl start docker

# Start Docker daemon (Mac)
open /Applications/Docker.app

# Add user to docker group (Linux)
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker run hello-world
```

### Error: "Error response from daemon: no space left on device"

**Causes:**
- Disk space full
- Docker images/containers taking up space

**Solutions:**

```bash
# Check disk space
df -h

# Clean up Docker
docker system prune -a  # Remove all unused images/containers

# Or specifically
docker rmi $(docker images -q)  # Remove all images
docker rm $(docker ps -aq)      # Remove all containers
```

### Docker Container Exits Immediately

**Causes:**
- Missing environment variables
- Invalid API key
- Port already in use

**Solutions:**

```bash
# Run interactively to see errors
docker run -it \
  -e OWM_API_KEY=sk_key \
  -e LAT=38.9 \
  -e LON=-77.0 \
  sun-intensity-agent:latest

# Check logs
docker logs <container-id>

# Run with bash to investigate
docker run -it sun-intensity-agent:latest bash
# Then run: python -m sun_intensity_agent.cli

# Check if port is in use
lsof -i :8080
# Kill process if needed
kill -9 <process-id>
```

---

## Server/HTTP Issues

### Error: "Connection refused" when accessing http://localhost:8080

**Causes:**
- Server not running
- Wrong port
- Firewall blocking local connections

**Solutions:**

```bash
# Start server
uvicorn sun_intensity_agent.server:app --host 0.0.0.0 --port 8080

# Check if server is running
curl http://localhost:8080/health

# Verify port
netstat -tuln | grep 8080

# Try different port
uvicorn sun_intensity_agent.server:app --port 9000
curl http://localhost:9000/health
```

### Error: "Port 8080 already in use"

**Solutions:**

```bash
# Find what's using port 8080
lsof -i :8080

# Kill the process
kill -9 <process-id>

# Or use different port
uvicorn sun_intensity_agent.server:app --port 9000
```

### HTTP Error 502 "Bad Gateway"

**Causes:**
- OpenWeatherMap API is down
- Network connectivity issue
- API key rate limited

**Solutions:**

```bash
# Check OpenWeatherMap status
curl https://api.openweathermap.org/data/4.0/onecall/timeline/1h?lat=38.9&lon=-77.0&appid=$OWM_API_KEY

# Service will automatically retry
# Check application logs for details
```

---

## Configuration Issues

### Error: ".env file not found"

**Not actually an error** — the application will use environment variables

**Solutions:**

```bash
# Create .env file
cat > .env << EOF
OWM_API_KEY=sk_your_key
LAT=38.9
LON=-77.0
PORT=8080
EOF

# Or set environment variables directly
export OWM_API_KEY="sk_your_key"
export LAT=38.9
export LON=-77.0
```

### Settings not being loaded from .env

**Causes:**
- .env file in wrong directory
- File not readable
- Environment variables override .env

**Solutions:**

```bash
# Verify .env is in current directory
ls -la .env

# Make sure it's readable
chmod 644 .env

# Check contents
cat .env

# Verify Pydantic is loading it
python -c "from sun_intensity_agent.config import get_settings; s = get_settings(); print(s.owm_api_key)"
```

---

## Development & Testing Issues

### Error: "ModuleNotFoundError: No module named 'sun_intensity_agent'"

**Causes:**
- Not running from project root
- Virtual environment not activated
- Package not installed

**Solutions:**

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install in development mode
pip install -e .

# Run from project root
cd /path/to/sun-intensity-agent
python -m sun_intensity_agent.cli
```

### Tests Fail: "assert result['score'] == 100"

**Causes:**
- Constant values changed
- Algorithm modified
- Test fixture outdated

**Solutions:**

```bash
# Run single failing test with verbose output
pytest tests/test_scoring.py::test_clear_sky_day -vv

# See what the actual result was
pytest tests/test_scoring.py -s  # Show print statements

# Check if you modified the scoring algorithm
git diff sun_intensity_agent/scoring.py
```

### Import Errors in Tests

**Solutions:**

```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Reinstall in development mode
pip install -e .

# Run tests with import mode
pytest tests/ --import-mode=importlib
```

---

## Performance Issues

### Response Time is Slow (>2 seconds)

**Causes:**
- Network latency to OpenWeatherMap API
- Retry delays (if transient error occurred)
- System is under heavy load

**Solutions:**

```bash
# Expected timing:
# API call: 500ms-1s
# Parsing: <10ms
# Scoring: <5ms
# Total: ~600ms-1.1s

# If slower, check:
# 1. Network latency
ping api.openweathermap.org

# 2. DNS resolution speed
time nslookup api.openweathermap.org

# 3. Actual API response time
time curl https://api.openweathermap.org/data/4.0/onecall/timeline/1h?lat=38.9&lon=-77.0&appid=$OWM_API_KEY
```

### High Memory Usage

**Causes:**
- Memory leak in application (unlikely, stateless)
- OS caching
- Python garbage collection

**Solutions:**

```bash
# Memory usage should be ~50-100 MB
# If higher, check:
ps aux | grep python

# Monitor over time
watch -n 1 'ps aux | grep python'

# Force garbage collection
python -c "import gc; gc.collect(); print('Done')"
```

---

## Common Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| `JSONDecodeError` | Invalid JSON from API | API returned HTML error page, check API status |
| `KeyError: 'sunrise'` | Missing data in forecast | API returned incomplete data, retry |
| `ValueError: invalid literal for int()` | Type conversion failed | Check input data format |
| `Timeout` | Request took too long | Network slow, will retry automatically |
| `ConnectionError` | Network unreachable | Check connectivity, will retry automatically |

---

## Getting Help

1. **Check this guide** — Most common issues are covered above

2. **Check logs**
   - CLI: Run with `-v` flag or check stderr output
   - Server: Check application logs
   - Docker: `docker logs <container-id>`
   - Systemd: `journalctl -u sun-intensity -f`

3. **Enable debug logging**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

4. **Run manual tests**
   ```bash
   # Test CLI
   python -m sun_intensity_agent.cli --pretty
   
   # Test API directly
   curl http://localhost:8080/score
   
   # Test OWM API
   curl https://api.openweathermap.org/data/4.0/onecall/timeline/1h?lat=38.9&lon=-77.0&appid=$OWM_API_KEY
   ```

5. **Check project issues** — GitHub issues may have solutions to similar problems

---

**Last updated:** 2026-07-31  
**Still need help?** Check ARCHITECTURE.md for design context or DEVELOPMENT.md for setup help.
