"""
Unit tests for the configuration cache.

Tests caching operations, TTL expiration, statistics, and cleanup.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config_cache import CacheEntry, CacheStats, ConfigCache


@pytest.fixture
def cache():
    """Create a cache instance."""
    return ConfigCache(default_ttl=3600)


@pytest.mark.asyncio
async def test_cache_set_and_get(cache):
    """Test basic cache set and get operations."""
    await cache.set("key1", "value1")
    value = await cache.get("key1")
    assert value == "value1"


@pytest.mark.asyncio
async def test_cache_get_nonexistent_key(cache):
    """Test getting a non-existent key returns default."""
    value = await cache.get("nonexistent", default="default_value")
    assert value == "default_value"


@pytest.mark.asyncio
async def test_cache_get_none_default(cache):
    """Test getting a non-existent key with None default."""
    value = await cache.get("nonexistent")
    assert value is None


@pytest.mark.asyncio
async def test_cache_invalidate_single_key(cache):
    """Test invalidating a single cache entry."""
    await cache.set("key1", "value1")
    await cache.invalidate("key1")
    value = await cache.get("key1")
    assert value is None


@pytest.mark.asyncio
async def test_cache_invalidate_all(cache):
    """Test invalidating all cache entries."""
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.invalidate_all()

    assert await cache.get("key1") is None
    assert await cache.get("key2") is None


@pytest.mark.asyncio
async def test_cache_ttl_expiration(cache):
    """Test that cache entries expire after TTL."""
    # Create cache with short TTL
    short_ttl_cache = ConfigCache(default_ttl=1)
    await short_ttl_cache.set("key1", "value1", ttl=1)

    # Value should be available immediately
    value = await short_ttl_cache.get("key1")
    assert value == "value1"

    # Wait for expiration
    await asyncio.sleep(1.1)

    # Value should be expired
    value = await short_ttl_cache.get("key1")
    assert value is None


@pytest.mark.asyncio
async def test_cache_custom_ttl(cache):
    """Test setting custom TTL for entries."""
    await cache.set("key1", "value1", ttl=2)
    await cache.set("key2", "value2", ttl=10)

    # Both should be available
    assert await cache.get("key1") == "value1"
    assert await cache.get("key2") == "value2"


@pytest.mark.asyncio
async def test_cache_is_expired(cache):
    """Test checking if a cache entry is expired."""
    await cache.set("key1", "value1", ttl=1)

    # Should not be expired
    is_expired = await cache.is_expired("key1")
    assert not is_expired

    # Wait for expiration
    await asyncio.sleep(1.1)

    # Should be expired
    is_expired = await cache.is_expired("key1")
    assert is_expired


@pytest.mark.asyncio
async def test_cache_is_expired_nonexistent(cache):
    """Test checking if a non-existent key is expired."""
    is_expired = await cache.is_expired("nonexistent")
    assert is_expired


@pytest.mark.asyncio
async def test_cache_cleanup_expired(cache):
    """Test cleanup of expired entries."""
    await cache.set("key1", "value1", ttl=1)
    await cache.set("key2", "value2", ttl=10)

    # Wait for first entry to expire
    await asyncio.sleep(1.1)

    # Cleanup
    removed_count = await cache.cleanup_expired()
    assert removed_count == 1

    # key1 should be gone, key2 should remain
    assert await cache.get("key1") is None
    assert await cache.get("key2") == "value2"


@pytest.mark.asyncio
async def test_cache_stats_hit_rate(cache):
    """Test cache statistics and hit rate calculation."""
    await cache.set("key1", "value1")

    # Generate hits and misses
    await cache.get("key1")  # hit
    await cache.get("key1")  # hit
    await cache.get("nonexistent")  # miss

    stats = await cache.get_stats()
    assert stats.total_hits == 2
    assert stats.total_misses == 1
    assert stats.hit_rate == 2 / 3


@pytest.mark.asyncio
async def test_cache_stats_entries_count(cache):
    """Test cache statistics entries count."""
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")

    stats = await cache.get_stats()
    assert stats.entries_count == 2


@pytest.mark.asyncio
async def test_cache_stats_to_dict(cache):
    """Test converting cache stats to dictionary."""
    await cache.set("key1", "value1")
    await cache.get("key1")

    stats = await cache.get_stats()
    stats_dict = stats.to_dict()

    assert "total_hits" in stats_dict
    assert "total_misses" in stats_dict
    assert "hit_rate" in stats_dict
    assert "entries_count" in stats_dict
    assert "memory_usage_bytes" in stats_dict


@pytest.mark.asyncio
async def test_cache_cleanup_task(cache):
    """Test background cleanup task."""
    await cache.start_cleanup_task(interval=1)

    # Add entries with short TTL
    await cache.set("key1", "value1", ttl=1)
    await cache.set("key2", "value2", ttl=10)

    # Wait for expiration and cleanup
    await asyncio.sleep(2.5)

    # key1 should be cleaned up
    stats = await cache.get_stats()
    assert stats.entries_count == 1

    await cache.stop_cleanup_task()


@pytest.mark.asyncio
async def test_cache_get_entries_info(cache):
    """Test getting detailed information about cache entries."""
    await cache.set("key1", "value1")
    await cache.get("key1")

    entries_info = await cache.get_entries_info()
    assert "key1" in entries_info
    assert entries_info["key1"]["hits"] == 1
    assert "created_at" in entries_info["key1"]
    assert "expires_at" in entries_info["key1"]
    assert "ttl_seconds" in entries_info["key1"]


def test_cache_entry_is_expired():
    """Test CacheEntry expiration check."""
    entry = CacheEntry("value", ttl=1)

    # Should not be expired
    assert not entry.is_expired()

    # Manually set created_at to past
    entry.created_at = datetime.now(timezone.utc) - timedelta(seconds=2)

    # Should be expired
    assert entry.is_expired()


def test_cache_entry_get_expires_at():
    """Test getting expiration time of cache entry."""
    entry = CacheEntry("value", ttl=3600)
    expires_at = entry.get_expires_at()

    # Should be approximately 1 hour from now
    now = datetime.now(timezone.utc)
    diff = (expires_at - now).total_seconds()
    assert 3599 < diff < 3601


def test_cache_stats_hit_rate_zero():
    """Test cache stats hit rate when no accesses."""
    stats = CacheStats(total_hits=0, total_misses=0)
    assert stats.hit_rate == 0.0


def test_cache_stats_hit_rate_all_hits():
    """Test cache stats hit rate with all hits."""
    stats = CacheStats(total_hits=10, total_misses=0)
    assert stats.hit_rate == 1.0


def test_cache_stats_hit_rate_all_misses():
    """Test cache stats hit rate with all misses."""
    stats = CacheStats(total_hits=0, total_misses=10)
    assert stats.hit_rate == 0.0
