from app.core.ratelimit import RateLimiter


def test_allows_up_to_the_limit_per_key_then_blocks():
    now = [0.0]
    limiter = RateLimiter(2, 60, clock=lambda: now[0])
    assert limiter.hit("a") and limiter.hit("a")
    assert not limiter.hit("a")
    assert limiter.hit("b")  # keys are independent


def test_window_rolls_forward():
    now = [0.0]
    limiter = RateLimiter(2, 60, clock=lambda: now[0])
    limiter.hit("a")
    now[0] = 30.0
    limiter.hit("a")
    now[0] = 60.5  # the first hit has left the window
    assert limiter.hit("a")
    assert not limiter.hit("a")


def test_reset_clears_all_keys():
    limiter = RateLimiter(1, 60)
    limiter.hit("a")
    limiter.reset()
    assert limiter.hit("a")
