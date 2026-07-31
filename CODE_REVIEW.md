# Code Review & Refactoring Report

## Overview

Comprehensive review of the Sun Intensity Agent codebase for structure, architecture, and code quality.

## Issues Identified

### 1. **Code Duplication in Error Handling** (High Priority)

**Location:** `cli.py` (lines 23-41) and `server.py` (lines 23-36)

**Issue:** Both CLI and server have similar error handling patterns that create an error dict and respond.

**Before:**
```python
# In cli.py
except OWMAuthError as e:
    error_response = {"error": str(e)}
    print(json.dumps(error_response), file=sys.stderr)
    sys.exit(1)

except OWMRateLimitError as e:
    error_response = {"error": str(e)}
    print(json.dumps(error_response), file=sys.stderr)
    sys.exit(1)
# ... repeated pattern
```

**After:**
Extract into a shared error mapping and handler functions.

---

### 2. **Code Duplication in Retry Logic** (Medium Priority)

**Location:** `owm_client.py` (lines 127-150)

**Issue:** Retry and sleep logic is duplicated across multiple exception handlers.

**Before:**
```python
except OWMRequestError as e:
    if not e.retryable:
        raise
    last_exception = e
    if attempt < retry_config.max_retries:
        delay = retry_config.calculate_delay(attempt)
        sleep_func(delay)
    else:
        raise

except OWMRateLimitError as e:
    last_exception = e
    if attempt < retry_config.max_retries:
        delay = retry_config.calculate_delay(attempt)
        sleep_func(delay)
    else:
        raise
# ... pattern repeats
```

**After:**
Extract into a helper method that handles retry logic.

---

### 3. **Code Duplication in Scoring Fallback** (Low Priority)

**Location:** `scoring.py` (lines 37-38 and 56-60)

**Issue:** Fallback calculation is duplicated: `round(100 - tomorrow.get("clouds", 0))`

**Impact:** If the fallback logic needs to change, must update in multiple places.

---

### 4. **Deprecated Pydantic Configuration** (Medium Priority)

**Location:** `config.py` (lines 12-14)

**Issue:** Using deprecated `class Config` pattern. Pydantic v2 prefers `ConfigDict`.

**Before:**
```python
class Settings(BaseSettings):
    owm_api_key: str
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

**After:**
```python
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
    )
    owm_api_key: str
```

---

### 5. **Redundant get_settings() Function** (Low Priority)

**Location:** `config.py` (lines 32-33)

**Issue:** `get_settings()` is creating Settings with explicit `owm_api_key`, but BaseSettings already loads from env automatically.

**Before:**
```python
def get_settings() -> Settings:
    return Settings(owm_api_key=os.getenv("OWM_API_KEY", ""))
```

**After:**
```python
def get_settings() -> Settings:
    return Settings()  # BaseSettings handles env loading automatically
```

---

### 6. **Timestamp Formatting Duplication** (Low Priority)

**Location:** `scoring.py` (lines 69-71)

**Issue:** Similar pattern used to format sunrise and sunset timestamps. Could extract.

---

### 7. **Hardcoded Magic Numbers & Status Codes** (Low Priority)

**Location:** Multiple files

**Issue:** 
- Exit codes (0, 1, 2) hardcoded in CLI
- HTTP status codes (401, 429, 502, 400, 500) hardcoded in server
- Timeout value (10s) hardcoded in owm_client

**Recommendation:** Extract to constants for maintainability.

---

### 8. **Missing Type Hints** (Low Priority)

**Location:** `server.py` (line 11)

**Issue:** Function doesn't explicitly return type. Should add return type hint.

**Before:**
```python
async def score(lat: Optional[float] = Query(None), lon: Optional[float] = Query(None)):
```

**After:**
```python
async def score(lat: Optional[float] = Query(None), lon: Optional[float] = Query(None)) -> Dict[str, Any]:
```

---

## Architecture Assessment

### Strengths ✅

1. **Clean Separation of Concerns**
   - `config.py` — Configuration
   - `owm_client.py` — API interactions
   - `scoring.py` — Core algorithm
   - `core.py` — Orchestration
   - `cli.py` / `server.py` — UI layers

2. **Pure Functions**
   - `compute_score()` is pure (no side effects)
   - Testable, predictable behavior

3. **Typed Exceptions**
   - Clear error hierarchy (OWMError → specific errors)
   - Each exception carries context

4. **Dependency Injection**
   - `fetch_forecast()` accepts `sleep_func` for testing
   - Easy to mock in tests

### Areas for Improvement 🔧

1. **Code Reuse**
   - Error handling should be shared between CLI and server
   - Retry logic should be more DRY

2. **Configuration**
   - Constants (timeouts, exit codes, status codes) should be centralized
   - Consider a `constants.py` module

3. **Validation**
   - Coordinates validated at call time, not at config initialization
   - Could validate earlier to fail fast

---

## Recommended Refactoring Priority

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| 🔴 High | Error handling duplication (CLI/server) | Small | High |
| 🟡 Medium | Retry logic duplication (owm_client) | Small | Medium |
| 🟡 Medium | Deprecated Pydantic config | Small | Low |
| 🟢 Low | Scoring fallback duplication | Small | Low |
| 🟢 Low | Timestamp formatting | Very Small | Low |
| 🟢 Low | Magic numbers/constants | Small | Medium |
| 🟢 Low | Missing return type hints | Very Small | Low |

---

## Summary

**Overall Assessment: GOOD** ✅

The code is well-organized with clear separation of concerns. The main issues are code duplication (error handling, retry logic) that should be refactored for maintainability.

**Action Items:**
1. ✅ Refactor error handling (CLI & server) into shared functions
2. ✅ Simplify retry logic in owm_client
3. ✅ Update Pydantic config to v2 style
4. ✅ Extract scoring fallback to constant
5. ✅ Add missing return type hints
6. ✅ Extract hardcoded values to constants

After refactoring: **EXCELLENT** 🌟
