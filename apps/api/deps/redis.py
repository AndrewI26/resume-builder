from collections.abc import AsyncGenerator, Generator
from typing import Annotated

import redis
import redis.asyncio as aioredis
from arq import ArqRedis
from fastapi import Depends

from config import get_settings

settings = get_settings()

# compose starts redis with ``--requirepass``, so the password is not optional
# against the real instance; ``or None`` keeps a passwordless local one working.
redis_pool = redis.ConnectionPool(
    host="localhost",
    port=settings.redis_port,
    password=settings.redis_password or None,
    db=0,
)
redis_async_pool = aioredis.ConnectionPool(
    host="localhost",
    port=settings.redis_port,
    password=settings.redis_password or None,
    db=0,
)


def get_redis() -> Generator[redis.Redis, None, None]:
    """Yields a Redis client instance from the connection pool."""
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        client.close()


async def get_arq() -> AsyncGenerator[ArqRedis, None]:
    """Yields an ArqRedis client instance from the async connection pool."""
    client = ArqRedis(connection_pool=redis_async_pool)
    try:
        yield client
    finally:
        await client.close()


Redis = Annotated[redis.Redis, Depends(get_redis)]
RedisQueue = Annotated[ArqRedis, Depends(get_arq)]
