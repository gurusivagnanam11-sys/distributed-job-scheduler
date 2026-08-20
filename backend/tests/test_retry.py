from app.services.retry import compute_delay

class MockPolicy:
    def __init__(self, strategy, base, max_sec):
        self.backoff_strategy = strategy
        self.backoff_base_seconds = base
        self.backoff_max_seconds = max_sec

def test_fixed_backoff():
    policy = MockPolicy("fixed", 5.0, 100.0)
    assert compute_delay(1, policy) == 5
    assert compute_delay(5, policy) == 5
    assert compute_delay(50, policy) == 5

def test_linear_backoff():
    policy = MockPolicy("linear", 2.0, 50.0)
    assert compute_delay(1, policy) == 2
    assert compute_delay(3, policy) == 6
    assert compute_delay(10, policy) == 20
    # Capped
    assert compute_delay(30, policy) == 50

def test_exponential_backoff():
    policy = MockPolicy("exponential", 2.0, 3600.0)
    assert compute_delay(1, policy) == 2
    assert compute_delay(2, policy) == 4
    assert compute_delay(3, policy) == 8
    assert compute_delay(4, policy) == 16
    assert compute_delay(10, policy) == 1024
    # Capped
    assert compute_delay(12, policy) == 3600  # 2^11 = 2048, 2^12 = 4096 (capped)

def test_exponential_backoff_overflow():
    policy = MockPolicy("exponential", 2.0, 10000.0)
    # Huge attempt number should just cap out without math overflow error
    assert compute_delay(10000, policy) == 10000
