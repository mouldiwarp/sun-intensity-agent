# Development Guide

## Setting Up Your Development Environment

### Prerequisites

- Python 3.9 or higher
- pip or conda for package management
- Git for version control
- Docker (optional, for containerized testing)

### Quick Setup

```bash
# Clone the repository
git clone <repo-url>
cd sun-intensity-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov pytest-watch black flake8 mypy

# Verify installation
python -m pytest tests/ -v
```

### Environment Variables

Create a `.env` file for local development:

```bash
OWM_API_KEY=sk_your_test_api_key
LAT=38.9
LON=-77.0
PORT=8080
```

Or set directly:
```bash
export OWM_API_KEY=sk_your_test_api_key
export LAT=38.9
export LON=-77.0
```

## Running the Application

### CLI Mode

```bash
# Basic usage
python -m sun_intensity_agent.cli --pretty

# With location override
python -m sun_intensity_agent.cli --lat 51.5 --lon -0.1 --pretty

# Parse output with jq
python -m sun_intensity_agent.cli | jq '.score'
```

### Server Mode

```bash
# Start development server with auto-reload
uvicorn sun_intensity_agent.server:app --reload

# Start on custom port
uvicorn sun_intensity_agent.server:app --port 9000 --reload

# Visit http://localhost:8000
# API docs: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

### Docker

```bash
# Build image
docker build -t sun-intensity-agent:dev .

# Run server
docker run -e OWM_API_KEY=sk_key -e LAT=38.9 -e LON=-77.0 -p 8080:8080 sun-intensity-agent:dev

# Run CLI
docker run -e OWM_API_KEY=sk_key sun-intensity-agent:dev python -m sun_intensity_agent.cli --lat 38.9 --lon -77.0
```

## Testing

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_scoring.py -v

# Specific test class
pytest tests/test_scoring.py::TestScoringEdgeCases -v

# Specific test
pytest tests/test_scoring.py::test_clear_sky_day -v

# Tests matching pattern
pytest tests/ -k "clear" -v
```

### Test Coverage

```bash
# Generate coverage report
pytest tests/ --cov=sun_intensity_agent --cov-report=html

# View HTML report
open htmlcov/index.html

# Terminal report with missing lines
pytest tests/ --cov=sun_intensity_agent --cov-report=term-missing
```

### Watch Mode (Auto-rerun on file changes)

```bash
# Install pytest-watch
pip install pytest-watch

# Run in watch mode
ptw tests/

# Watch specific file
ptw tests/test_scoring.py
```

### Test Organization

**Unit Tests** — Pure functions with mock data
```python
# No network calls, no external dependencies
result = compute_score(mock_daily, mock_hourly)
assert result["score"] == 100
```

**Integration Tests** — End-to-end with mocked API
```python
# Tests complete flow without hitting real API
mock_response = Mock(status_code=200, json=lambda: {...})
with patch("requests.get", return_value=mock_response):
    result = fetch_forecast(api_key, lat, lon)
```

**Edge Case Tests** — Boundary conditions
```python
# Test extreme values
test_very_long_daylight()  # 24 hours
test_single_hour_daylight()  # 1 hour
test_polar_region()  # 2 hours
```

## Code Quality Tools

### Type Checking

```bash
# Install mypy
pip install mypy

# Check types
mypy sun_intensity_agent/

# Ignore specific files
mypy sun_intensity_agent/ --ignore-missing-imports
```

### Linting

```bash
# Install flake8
pip install flake8

# Run linter
flake8 sun_intensity_agent/ tests/

# Show statistics
flake8 sun_intensity_agent/ --statistics

# Check complexity
flake8 sun_intensity_agent/ --max-complexity=10
```

### Code Formatting

```bash
# Install black
pip install black

# Format code
black sun_intensity_agent/ tests/

# Check without modifying
black sun_intensity_agent/ --check
```

### Security Scanning

```bash
# Install bandit
pip install bandit

# Scan for security issues
bandit -r sun_intensity_agent/

# Skip certain checks
bandit -r sun_intensity_agent/ -s B101  # Skip assertion checks
```

### All-in-One Quality Check

```bash
# Run all quality checks
black sun_intensity_agent/ tests/
flake8 sun_intensity_agent/ tests/
mypy sun_intensity_agent/
bandit -r sun_intensity_agent/
pytest tests/ -v --cov=sun_intensity_agent
```

## Making Changes

### Code Style Guidelines

**Type Hints:**
```python
# ✅ Good
def compute_score(daily: List[Dict[str, Any]], hourly: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate sun intensity score."""
    pass

# ❌ Bad
def compute_score(daily, hourly):
    return result
```

**Docstrings:**
```python
# ✅ Good
def fetch_forecast(api_key: str, lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch tomorrow's forecast from OpenWeatherMap.
    
    Args:
        api_key: OpenWeatherMap API key
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
    
    Returns:
        dict with 'daily' and 'hourly' arrays
    
    Raises:
        OWMAuthError: Invalid API key
        OWMRateLimitError: Rate limit exceeded
        OWMRequestError: Network or server error
    """
    pass

# ❌ Bad
def fetch_forecast(api_key, lat, lon):
    """Fetch forecast"""
    pass
```

**Comments:**
```python
# ✅ Good - WHY not WHAT
# Jitter prevents thundering herd when multiple clients retry simultaneously
jitter = delay * 0.25 * (2 * random.random() - 1)

# ❌ Bad - Obvious WHAT
# Add jitter to delay
jitter = delay * 0.25 * (2 * random.random() - 1)
```

**Constants:**
```python
# ✅ Good - Use constants from constants.py
from .constants import OWM_REQUEST_TIMEOUT
timeout = OWM_REQUEST_TIMEOUT

# ❌ Bad - Hardcoded values
timeout = 10
```

### Adding a New Feature

1. **Write tests first** (TDD approach)
   ```bash
   # Add test to appropriate test file
   vim tests/test_scoring.py
   ```

2. **Implement feature**
   ```bash
   # Modify source code
   vim sun_intensity_agent/scoring.py
   ```

3. **Run tests**
   ```bash
   pytest tests/ -v
   ```

4. **Check code quality**
   ```bash
   black sun_intensity_agent/
   flake8 sun_intensity_agent/
   mypy sun_intensity_agent/
   ```

5. **Update documentation**
   ```bash
   vim README.md  # Update usage examples
   vim docs/ARCHITECTURE.md  # Update design docs
   ```

### Example: Add New HTTP Endpoint

1. **Write test** (tests would go in a new integration test)
   ```python
   # In tests/test_integration.py
   def test_new_endpoint():
       response = client.get("/new-endpoint?lat=38.9&lon=-77.0")
       assert response.status_code == 200
   ```

2. **Implement endpoint** (server.py)
   ```python
   @app.get("/new-endpoint")
   async def new_endpoint(lat: Optional[float] = Query(None)) -> Dict[str, Any]:
       """New endpoint description."""
       return get_score(lat=lat)
   ```

3. **Test locally**
   ```bash
   uvicorn sun_intensity_agent.server:app --reload
   curl http://localhost:8000/new-endpoint?lat=38.9
   ```

4. **Run full test suite**
   ```bash
   pytest tests/ -v
   ```

### Example: Modify Retry Configuration

1. **Update constants** (constants.py)
   ```python
   DEFAULT_MAX_RETRIES = 5  # was 3
   DEFAULT_BASE_DELAY = 0.5  # was 1.0
   ```

2. **No code changes needed** — RetryConfig uses these constants

3. **Run tests to verify**
   ```bash
   pytest tests/test_owm_client.py -v
   ```

## Git Workflow

### Branch Naming

```
feature/add-new-endpoint
bugfix/fix-timezone-issue
refactor/simplify-retry-logic
docs/update-architecture
```

### Commit Messages

```
# ✅ Good
Add new /health endpoint for status checks

Fix rate limit retry logic to respect Retry-After header

Refactor scoring algorithm to extract helpers

Update documentation with deployment guide

# ❌ Bad
Fix bugs
Update code
Changes
```

### Creating a Pull Request

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes
# Test locally
pytest tests/ -v

# Commit with message
git commit -m "Add feature description

This commit adds X functionality that enables Y behavior."

# Push branch
git push origin feature/my-feature

# Create PR via GitHub UI
# Link related issues
# Ensure CI passes
```

## Debugging

### Print Debugging

```python
# Use print() for quick debugging
print(f"DEBUG: latitude={lat}, longitude={lon}")

# Or use logging in production code
import logging
logger = logging.getLogger(__name__)
logger.debug(f"latitude={lat}, longitude={lon}")
```

### Python Debugger

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use breakpoint() (Python 3.7+)
breakpoint()

# Commands:
# n - next line
# s - step into
# c - continue
# p variable - print variable
# l - list surrounding code
```

### Interactive Python Shell

```bash
# Start Python REPL
python

# Import and test
from sun_intensity_agent.scoring import compute_score
result = compute_score([{...}, {...}], [...])
print(result)
```

### Logging

```python
# In development, enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# In code
logger = logging.getLogger(__name__)
logger.debug(f"Attempting retry {attempt} of {max_retries}")
```

## Common Tasks

### Running Tests for a Specific Module

```bash
# Config tests only
pytest tests/test_config.py -v

# API client tests
pytest tests/test_owm_client.py -v

# Scoring algorithm tests
pytest tests/test_scoring.py -v
```

### Finding Failing Tests

```bash
# Run with verbose output
pytest tests/ -vv

# Show local variables on failure
pytest tests/ -l

# Stop on first failure
pytest tests/ -x

# Show print statements
pytest tests/ -s
```

### Profiling Performance

```bash
# Time a specific operation
python -m timeit "from sun_intensity_agent.scoring import compute_score; compute_score(...)"

# Full profile of CLI
python -m cProfile -s cumtime -m sun_intensity_agent.cli

# Memory profiling (requires memory-profiler)
python -m memory_profiler sun_intensity_agent/cli.py
```

### Testing Against Real API

```bash
# With real API key
export OWM_API_KEY=sk_your_real_key
python -m sun_intensity_agent.cli --lat 38.9 --lon -77.0 --pretty

# Check rate limit headers
curl -v https://api.openweathermap.org/data/4.0/onecall/timeline/1h?lat=38.9&lon=-77.0&appid=$OWM_API_KEY
```

## Troubleshooting Development Issues

### Import Errors

```python
# Error: ModuleNotFoundError: No module named 'sun_intensity_agent'
# Solution: Run from project root
cd /path/to/sun-intensity-agent
python -m sun_intensity_agent.cli

# Or install in development mode
pip install -e .
```

### Test Isolation Issues

```bash
# Run test in isolation
pytest tests/test_file.py::test_name -v

# Clear pytest cache
pytest --cache-clear

# Run with fresh imports
pytest tests/ --import-mode=importlib
```

### Virtual Environment Issues

```bash
# Recreate environment
rm -rf venv/
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Port Already in Use

```bash
# Use different port
uvicorn sun_intensity_agent.server:app --port 9000

# Or kill process using port 8000
lsof -ti:8000 | xargs kill -9
```

## Resources

### Project Structure
- See [ARCHITECTURE.md](./ARCHITECTURE.md) for system design
- See [CLAUDE.md](../CLAUDE.md) for quick reference

### External Documentation
- [Python Best Practices](https://pep8.org/)
- [Type Hints](https://docs.python.org/3/library/typing.html)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Pytest](https://docs.pytest.org/)
- [Pydantic](https://docs.pydantic.dev/)

### OpenWeatherMap API
- [One Call 4.0 API](https://openweathermap.org/api/one-call-4)
- [API Documentation](https://openweathermap.org/api)

---

**Last updated:** 2026-07-31  
**Happy coding! 🚀**
