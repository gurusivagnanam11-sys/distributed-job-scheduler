import math
from typing import Protocol

class RetryPolicyLike(Protocol):
    backoff_strategy: str
    backoff_base_seconds: float
    backoff_max_seconds: float


def compute_delay(attempt_number: int, policy: RetryPolicyLike) -> int:
    """
    Compute the delay in seconds before the next retry attempt.
    
    :param attempt_number: The current retry attempt (1 for the first retry).
    :param policy: An object with backoff_strategy, backoff_base_seconds, and backoff_max_seconds.
    :return: The delay in seconds (capped at backoff_max_seconds), as an integer.
    """
    if attempt_number < 1:
        attempt_number = 1

    base = policy.backoff_base_seconds
    
    if policy.backoff_strategy == "fixed":
        delay = base
    elif policy.backoff_strategy == "linear":
        delay = base * attempt_number
    elif policy.backoff_strategy == "exponential":
        # Base 2 exponential: base * (2^(attempt-1))
        # e.g. base=2: 1->2, 2->4, 3->8
        try:
            delay = base * (2 ** (attempt_number - 1))
        except OverflowError:
            delay = policy.backoff_max_seconds
    else:
        # Fallback to fixed
        delay = base
        
    delay = min(delay, policy.backoff_max_seconds)
    
    return int(math.ceil(delay))
