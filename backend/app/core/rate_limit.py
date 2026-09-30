from fastapi import HTTPException, Request


async def enforce_rate_limit(request: Request, key: str, limit: int, window_seconds: int = 60) -> None:
    redis = request.app.state.redis
    redis_key = f"ratelimit:{key}"
    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, window_seconds)
    if count > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please retry shortly.")
