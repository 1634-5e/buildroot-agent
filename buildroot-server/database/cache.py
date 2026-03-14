#!/usr/bin/env python3
"""
Buildroot Agent Server - Simple Memory Cache
内存缓存层，用于缓存设备列表等常用数据
"""

import asyncio
import logging
import time
from typing import Optional, Any, Dict
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""

    value: Any
    expires_at: float


class MemoryCache:
    """内存缓存"""

    def __init__(self, default_ttl: float = 60.0):
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            if entry.expires_at < time.time():
                del self._cache[key]
                return None

            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """设置缓存值"""
        if ttl is None:
            ttl = self._default_ttl

        expires_at = time.time() + ttl

        async with self._lock:
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    async def delete(self, key: str) -> None:
        """删除缓存值"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache deleted: {key}")

    async def clear(self) -> None:
        """清空所有缓存"""
        async with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")

    async def cleanup_expired(self) -> None:
        """清理过期缓存"""
        now = time.time()
        expired_keys = []

        async with self._lock:
            for key, entry in self._cache.items():
                if entry.expires_at < now:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


def cached(ttl: float = 60.0):
    """缓存装饰器"""

    def decorator(func):
        cache = MemoryCache(default_ttl=ttl)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}_{str(args)}_{str(kwargs)}"
            cached_value = await cache.get(cache_key)

            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            logger.debug(f"Cache miss: {cache_key}")
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)

            return result

        wrapper.cache = cache
        return wrapper

    return decorator


device_list_cache = MemoryCache(default_ttl=30.0)
device_detail_cache = MemoryCache(default_ttl=60.0)
