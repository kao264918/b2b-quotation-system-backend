import time
from dataclasses import dataclass
from threading import Lock
import logging

from app.config import settings

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None

logger = logging.getLogger(__name__)


@dataclass
class RateLimitState:
    count: int
    reset_at: float


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter.
    NOTE: This is per-process. In production with multiple instances,
    use a shared store (e.g., Redis) for accurate limits.
    """

    def __init__(self) -> None:
        self._store: dict[str, RateLimitState] = {}
        self._lock = Lock()

    def check_and_increment(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        with self._lock:
            state = self._store.get(key)
            if not state or state.reset_at <= now:
                self._store[key] = RateLimitState(count=1, reset_at=now + window_seconds)
                return True

            if state.count >= limit:
                return False

            state.count += 1
            return True


class RedisRateLimiter:
    """
    Redis-backed rate limiter with automatic fallback to in-memory on failure.
    """

    def __init__(self, redis_url: str) -> None:
        if not redis:
            raise RuntimeError("redis package is not installed")
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        # Keep an in-memory fallback for when Redis is temporarily unavailable
        self._fallback = InMemoryRateLimiter()

    def check_and_increment(self, key: str, limit: int, window_seconds: int) -> bool:
        try:
            full_key = f"rate:{key}"
            pipe = self._client.pipeline()
            pipe.incr(full_key)
            pipe.expire(full_key, window_seconds, nx=True)
            count, _ = pipe.execute()
            return int(count) <= limit
        except Exception as exc:
            # Fall back to in-memory instead of blindly allowing the request
            logger.warning(
                "Redis rate limit failed, falling back to in-memory limiter. error=%s",
                str(exc),
            )
            return self._fallback.check_and_increment(key, limit, window_seconds)


def build_rate_limiter():
    if settings.REDIS_URL:
        try:
            return RedisRateLimiter(settings.REDIS_URL)
        except Exception as exc:
            logger.warning("Redis rate limiter unavailable, falling back to in-memory. error=%s", str(exc))
            return InMemoryRateLimiter()
    return InMemoryRateLimiter()


rate_limiter = build_rate_limiter()
