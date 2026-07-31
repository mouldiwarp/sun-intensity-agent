"""
Tests for OpenWeatherMap API client, including backoff retry logic.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from sun_intensity_agent.owm_client import fetch_forecast, RetryConfig
from sun_intensity_agent.errors import OWMAuthError, OWMRateLimitError, OWMRequestError


class TestRetryConfig:
    """Test retry configuration and backoff calculation."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(max_retries=5, base_delay=0.5, max_delay=30.0)
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        config = RetryConfig(base_delay=1.0, max_delay=60.0)

        # Exponential backoff: 2^attempt * base_delay
        # Without jitter, delays would be: 1s, 2s, 4s, 8s, etc.
        delay_0 = config.calculate_delay(0)
        delay_1 = config.calculate_delay(1)
        delay_2 = config.calculate_delay(2)

        # With jitter (±25%), delays should be within expected ranges
        assert 0.75 <= delay_0 <= 1.25  # 1s ± 25%
        assert 1.5 <= delay_1 <= 2.5   # 2s ± 25%
        assert 3.0 <= delay_2 <= 5.0   # 4s ± 25%

    def test_max_delay_cap(self):
        """Test that backoff is capped at max_delay."""
        config = RetryConfig(base_delay=1.0, max_delay=10.0)

        # After enough retries, delay should be capped
        delay_5 = config.calculate_delay(5)  # Would be 32s without cap
        assert delay_5 <= 12.5  # 10s + 25% jitter


def _mock_v4_daily_response():
    """Create a mock V4 daily response."""
    return {
        "timelines": [
            {
                "intervals": [
                    {
                        "startTime": "2026-08-01T00:00:00Z",
                        "values": {"cloudCover": 0}
                    },
                    {
                        "startTime": "2026-08-02T00:00:00Z",
                        "values": {"cloudCover": 10}
                    }
                ]
            }
        ]
    }


def _mock_v4_hourly_response():
    """Create a mock V4 hourly response."""
    return {
        "timelines": [
            {
                "intervals": [
                    {
                        "startTime": "2026-08-01T00:00:00Z",
                        "values": {"cloudCover": 0}
                    },
                    {
                        "startTime": "2026-08-01T01:00:00Z",
                        "values": {"cloudCover": 5}
                    }
                ]
            }
        ]
    }


class TestFetchForecastSuccess:
    """Test successful API calls."""

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_successful_fetch(self, mock_get):
        """Test successful forecast fetch (V4 API)."""
        # Mock two separate calls: one for hourly, one for daily
        mock_response_hourly = Mock()
        mock_response_hourly.status_code = 200
        mock_response_hourly.json.return_value = _mock_v4_hourly_response()

        mock_response_daily = Mock()
        mock_response_daily.status_code = 200
        mock_response_daily.json.return_value = _mock_v4_daily_response()

        # Both hourly and daily calls return 200
        mock_get.side_effect = [mock_response_hourly, mock_response_daily]

        result = fetch_forecast("test_key", 38.9, -77.0)

        assert result["daily"][0]["clouds"] == 0
        assert len(result["hourly"]) == 2
        # Should be called twice: once for hourly, once for daily
        assert mock_get.call_count == 2


class TestFetchForecastAuthError:
    """Test authentication error handling (not retried)."""

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_auth_error_no_retry(self, mock_get):
        """Test that 401 errors are not retried."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        with pytest.raises(OWMAuthError) as exc_info:
            fetch_forecast("bad_key", 38.9, -77.0)

        assert "One Call 4.0" in str(exc_info.value) or "API key" in str(exc_info.value)
        # Should only be called once (no retries) - first endpoint call fails with 401
        assert mock_get.call_count == 1


class TestFetchForecastRateLimit:
    """Test rate limit error handling (with retry)."""

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_rate_limit_retry_success(self, mock_get):
        """Test that 429 errors are retried and eventually succeed."""
        mock_response_fail = Mock()
        mock_response_fail.status_code = 429
        mock_response_fail.headers = {"Retry-After": "2"}

        # Successful responses (hourly then daily)
        mock_response_hourly = Mock()
        mock_response_hourly.status_code = 200
        mock_response_hourly.json.return_value = _mock_v4_hourly_response()

        mock_response_daily = Mock()
        mock_response_daily.status_code = 200
        mock_response_daily.json.return_value = _mock_v4_daily_response()

        # First hourly call returns 429, retry succeeds, then daily call succeeds
        mock_get.side_effect = [mock_response_fail, mock_response_hourly, mock_response_daily]

        # Mock sleep to avoid actual delays
        mock_sleep = Mock()

        result = fetch_forecast(
            "test_key",
            38.9,
            -77.0,
            retry_config=RetryConfig(max_retries=3, base_delay=0.1),
            sleep_func=mock_sleep,
        )

        assert result["daily"][0]["clouds"] == 0
        # 3 calls: first hourly (429), retry hourly (200), then daily (200)
        assert mock_get.call_count == 3
        # Sleep should have been called once between retries
        assert mock_sleep.call_count == 1

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_rate_limit_exhausted_retries(self, mock_get):
        """Test that 429 errors raise after retries exhausted."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_get.return_value = mock_response

        mock_sleep = Mock()

        with pytest.raises(OWMRateLimitError):
            fetch_forecast(
                "test_key",
                38.9,
                -77.0,
                retry_config=RetryConfig(max_retries=2, base_delay=0.1),
                sleep_func=mock_sleep,
            )

        # Should try: attempt 0, sleep, attempt 1, sleep, attempt 2
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_rate_limit_with_retry_after(self, mock_get):
        """Test that Retry-After header is parsed."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "5"}
        mock_get.return_value = mock_response

        with pytest.raises(OWMRateLimitError) as exc_info:
            fetch_forecast("test_key", 38.9, -77.0)

        assert exc_info.value.retry_after == 5


class TestFetchForecastServerError:
    """Test server error handling (with retry)."""

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_5xx_error_retry_success(self, mock_get):
        """Test that 5xx errors are retried."""
        # First call: hourly endpoint returns 502, then succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 502

        mock_response_hourly = Mock()
        mock_response_hourly.status_code = 200
        mock_response_hourly.json.return_value = _mock_v4_hourly_response()

        mock_response_daily = Mock()
        mock_response_daily.status_code = 200
        mock_response_daily.json.return_value = _mock_v4_daily_response()

        # Sequence: hourly fails (502), hourly retries (200), daily (200)
        mock_get.side_effect = [mock_response_fail, mock_response_hourly, mock_response_daily]
        mock_sleep = Mock()

        result = fetch_forecast(
            "test_key",
            38.9,
            -77.0,
            retry_config=RetryConfig(max_retries=3, base_delay=0.1),
            sleep_func=mock_sleep,
        )

        assert len(result["daily"]) > 0
        assert result["daily"][0]["clouds"] == 0  # First day from mock
        assert mock_get.call_count == 3  # fail, retry hourly, then daily
        assert mock_sleep.call_count == 1  # One sleep between retry

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_5xx_error_exhausted(self, mock_get):
        """Test that 5xx errors raise after retries exhausted."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response

        mock_sleep = Mock()

        with pytest.raises(OWMRequestError) as exc_info:
            fetch_forecast(
                "test_key",
                38.9,
                -77.0,
                retry_config=RetryConfig(max_retries=1, base_delay=0.1),
                sleep_func=mock_sleep,
            )

        assert "503" in str(exc_info.value)
        assert mock_get.call_count == 2  # 2 attempts (max_retries=1 means 0,1)
        assert mock_sleep.call_count == 1


class TestFetchForecastConnectionError:
    """Test connection error handling (with retry)."""

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_connection_timeout_retry(self, mock_get):
        """Test that timeouts are retried."""
        import requests

        mock_sleep = Mock()
        mock_response_hourly = Mock()
        mock_response_hourly.status_code = 200
        mock_response_hourly.json.return_value = _mock_v4_hourly_response()

        mock_response_daily = Mock()
        mock_response_daily.status_code = 200
        mock_response_daily.json.return_value = _mock_v4_daily_response()

        # Sequence: hourly timeout, hourly retry succeeds, daily succeeds
        mock_get.side_effect = [
            requests.Timeout("Connection timeout"),
            mock_response_hourly,
            mock_response_daily,
        ]

        result = fetch_forecast(
            "test_key",
            38.9,
            -77.0,
            retry_config=RetryConfig(max_retries=3, base_delay=0.1),
            sleep_func=mock_sleep,
        )

        assert len(result["daily"]) > 0
        assert result["daily"][0]["clouds"] == 0  # First day from mock
        assert mock_get.call_count == 3  # timeout, retry hourly, daily
        assert mock_sleep.call_count == 1

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_connection_error_retry(self, mock_get):
        """Test that connection errors are retried."""
        import requests

        mock_sleep = Mock()
        mock_response_hourly = Mock()
        mock_response_hourly.status_code = 200
        mock_response_hourly.json.return_value = _mock_v4_hourly_response()

        mock_response_daily = Mock()
        mock_response_daily.status_code = 200
        mock_response_daily.json.return_value = _mock_v4_daily_response()

        # Sequence: hourly connection error, hourly retry succeeds, daily succeeds
        mock_get.side_effect = [
            requests.ConnectionError("Connection refused"),
            mock_response_hourly,
            mock_response_daily,
        ]

        result = fetch_forecast(
            "test_key",
            38.9,
            -77.0,
            retry_config=RetryConfig(max_retries=2, base_delay=0.1),
            sleep_func=mock_sleep,
        )

        assert len(result["daily"]) > 0
        assert result["daily"][0]["clouds"] == 0  # First day from mock
        assert mock_get.call_count == 3  # error, retry hourly, daily


class TestFetchForecastClientError:
    """Test client error handling (not retried)."""

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_4xx_error_not_retried(self, mock_get):
        """Test that 4xx errors (other than 401) are not retried."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_get.return_value = mock_response

        mock_sleep = Mock()

        with pytest.raises(OWMRequestError) as exc_info:
            fetch_forecast(
                "test_key",
                38.9,
                -77.0,
                retry_config=RetryConfig(max_retries=3, base_delay=0.1),
                sleep_func=mock_sleep,
            )

        assert "404" in str(exc_info.value)
        # Should only try once (no retries for 4xx)
        assert mock_get.call_count == 1
        assert mock_sleep.call_count == 0

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_403_error_not_retried(self, mock_get):
        """Test that 403 forbidden is not retried."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_get.return_value = mock_response

        with pytest.raises(OWMRequestError):
            fetch_forecast("test_key", 38.9, -77.0)

        assert mock_get.call_count == 1


class TestFetchForecastInvalidJSON:
    """Test handling of invalid JSON responses."""

    @patch("sun_intensity_agent.owm_client.requests.get")
    def test_invalid_json_response(self, mock_get):
        """Test that invalid JSON raises error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        with pytest.raises(OWMRequestError) as exc_info:
            fetch_forecast("test_key", 38.9, -77.0)

        assert "Invalid JSON" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
