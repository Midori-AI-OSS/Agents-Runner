import datetime
import time

from agents_runner.gh.rate_limiter import _parse_rate_limit_seconds


def test_rate_limit_timestamp_is_parsed_as_utc(monkeypatch):
    now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc).timestamp()
    monkeypatch.setattr(time, "time", lambda: now)
    try:
        with monkeypatch.context() as env:
            env.setenv("TZ", "America/Los_Angeles")
            if hasattr(time, "tzset"):
                time.tzset()
            assert _parse_rate_limit_seconds("API rate limit exceeded; resets at 2026-01-01T00:10:00Z", "") == 600
            assert _parse_rate_limit_seconds("API rate limit exceeded; resets at 2026-01-01 00:10:00", "") == 600
    finally:
        if hasattr(time, "tzset"):
            time.tzset()
