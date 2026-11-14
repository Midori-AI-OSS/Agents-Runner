from agents_runner.gh.rate_limiter import _TokenBucket


def test_shorter_pause_does_not_override_longer_pause(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("agents_runner.gh.rate_limiter._monotonic", lambda: now[0])
    bucket = _TokenBucket(2.0)
    bucket.pause(300.0)
    now[0] += 10.0
    bucket.pause(1.0)
    assert bucket._pause_until == 400.0
    bucket.pause(500.0)
    assert bucket._pause_until == 610.0
