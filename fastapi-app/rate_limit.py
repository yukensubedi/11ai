import os
import time
from typing import Tuple
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def daily_counter_key(user_id: str) -> str:
    # resets every UTC day
    day = time.strftime("%Y-%m-%d", time.gmtime())
    return f"usage:{user_id}:{day}"

def incr_usage(user_id: str, limit: int) -> Tuple[int, int]:
    """
    Increment today's usage for user; return (current, limit).
    Raises RateLimitExceeded if over limit.
    """
    key = daily_counter_key(user_id)
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 60 * 60 * 24 + 60)  # 24h + small buffer
    current, _ = pipe.execute()
    if limit and current > limit:
        raise RateLimitExceeded(f"Daily quota exceeded: {current}/{limit}")
    return current, limit
