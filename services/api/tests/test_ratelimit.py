from app.core.ratelimit import RateLimiter, rate_limit_key


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


def test_expired_keys_are_forgotten_once_over_the_key_cap():
    now = [0.0]
    limiter = RateLimiter(2, 60, clock=lambda: now[0], max_keys=10)
    for i in range(100):
        limiter.hit(f"ip{i}")
    assert len(limiter) == 100  # all still inside the window
    now[0] = 61.0
    limiter.hit("fresh")
    assert len(limiter) == 1


def test_ipv6_clients_share_a_bucket_per_64():
    assert rate_limit_key("2001:db8:1:2:aaaa::1") == rate_limit_key("2001:db8:1:2:bbbb::9")
    assert rate_limit_key("2001:db8:1:2::1") != rate_limit_key("2001:db8:1:3::1")


def test_ipv4_and_unparseable_keys_are_unchanged():
    assert rate_limit_key("203.0.113.7") == "203.0.113.7"
    assert rate_limit_key("::ffff:203.0.113.7") == "203.0.113.7"
    assert rate_limit_key("unknown") == "unknown"
