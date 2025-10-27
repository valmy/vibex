"""
Configuration cache for the AI Trading Agent application.

Provides in-memory caching with TTL-based expiration for frequently accessed
configuration values, with statistics tracking and thread-safe access.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .logging import get_logger

logger = get_logger(__name__)


class CacheEntry:
    """Represents a cached configuration value."""

    def __init__(self, value: Any, ttl: int):
        """
        Initialize a cache entry.

        Args:
            value: The value to cache
            ttl: Time to live in seconds
        """
        self.value = value
        self.ttl = ttl
        self.created_at = datetime.utcnow()
        self.hits = 0
        self.misses = 0

    def is_expired(self) -> bool:
        """
        Check if the cache entry has expired.

        Returns:
            True if expired, False otherwise
        """
        expiration_time = self.created_at + timedelta(seconds=self.ttl)
        return datetime.utcnow() > expiration_time

    def get_expires_at(self) -> datetime:
        """
        Get the expiration time of this entry.

        Returns:
            Expiration datetime
        """
        return self.created_at + timedelta(seconds=self.ttl)


class CacheStats:
    """Statistics for the configuration cache."""

    def __init__(
        self,
        total_hits: int = 0,
        total_misses: int = 0,
        entries_count: int = 0,
        memory_usage: int = 0,
    ):
        """
        Initialize cache statistics.

        Args:
            total_hits: Total number of cache hits
            total_misses: Total number of cache misses
            entries_count: Number of entries in cache
            memory_usage: Approximate memory usage in bytes
        """
        self.total_hits = total_hits
        self.total_misses = total_misses
        self.entries_count = entries_count
        self.memory_usage = memory_usage

    @property
    def hit_rate(self) -> float:
        """
        Calculate cache hit rate.

        Returns:
            Hit rate as a percentage (0.0 to 1.0)
        """
        total = self.total_hits + self.total_misses
        if total == 0:
            return 0.0
        return self.total_hits / total

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert statistics to dictionary.

        Returns:
            Dictionary representation of statistics
        """
        return {
            "total_hits": self.total_hits,
            "total_misses": self.total_misses,
            "hit_rate": self.hit_rate,
            "entries_count": self.entries_count,
            "memory_usage_bytes": self.memory_usage,
        }


class ConfigCache:
    """In-memory cache for configuration values with TTL-based expiration."""

    def __init__(self, default_ttl: int = 3600):
        """
        Initialize the configuration cache.

        Args:
            default_ttl: Default time to live in seconds (default: 1 hour)
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._total_hits = 0
        self._total_misses = 0
        self._cleanup_task: Optional[asyncio.Task] = None

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the cache.

        Args:
            key: Cache key
            default: Default value if key not found or expired

        Returns:
            Cached value or default
        """
        async with self._lock:
            if key not in self._cache:
                self._total_misses += 1
                return default

            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._total_misses += 1
                return default

            entry.hits += 1
            self._total_hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if not specified)
        """
        async with self._lock:
            ttl = ttl or self.default_ttl
            self._cache[key] = CacheEntry(value, ttl)
            logger.debug(f"Cached configuration key '{key}' with TTL {ttl}s")

    async def invalidate(self, key: str) -> None:
        """
        Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Invalidated cache key '{key}'")

    async def invalidate_all(self) -> None:
        """Invalidate all cache entries."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Invalidated all {count} cache entries")

    async def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats object with current statistics
        """
        async with self._lock:
            memory_usage = self._estimate_memory_usage()
            return CacheStats(
                total_hits=self._total_hits,
                total_misses=self._total_misses,
                entries_count=len(self._cache),
                memory_usage=memory_usage,
            )

    async def is_expired(self, key: str) -> bool:
        """
        Check if a cache entry is expired.

        Args:
            key: Cache key

        Returns:
            True if expired or not found, False otherwise
        """
        async with self._lock:
            if key not in self._cache:
                return True
            return self._cache[key].is_expired()

    async def cleanup_expired(self) -> int:
        """
        Remove expired entries from the cache.

        Returns:
            Number of entries removed
        """
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

            return len(expired_keys)

    async def start_cleanup_task(self, interval: int = 300) -> None:
        """
        Start a background task to periodically clean up expired entries.

        Args:
            interval: Cleanup interval in seconds (default: 5 minutes)
        """
        if self._cleanup_task is not None:
            logger.warning("Cleanup task is already running")
            return

        async def cleanup_loop():
            try:
                while True:
                    await asyncio.sleep(interval)
                    await self.cleanup_expired()
            except asyncio.CancelledError:
                logger.info("Cache cleanup task cancelled")
                raise

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started cache cleanup task with {interval}s interval")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped cache cleanup task")

    def _estimate_memory_usage(self) -> int:
        """
        Estimate memory usage of cached values.

        Returns:
            Approximate memory usage in bytes
        """
        total_size = 0
        for entry in self._cache.values():
            total_size += sys.getsizeof(entry.value)
        return total_size

    async def get_entries_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed information about all cache entries.

        Returns:
            Dictionary with entry information
        """
        async with self._lock:
            entries_info = {}
            for key, entry in self._cache.items():
                entries_info[key] = {
                    "hits": entry.hits,
                    "misses": entry.misses,
                    "created_at": entry.created_at.isoformat(),
                    "expires_at": entry.get_expires_at().isoformat(),
                    "ttl_seconds": entry.ttl,
                    "is_expired": entry.is_expired(),
                }
            return entries_info

