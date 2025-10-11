"""
Cache helper utilities for the Awning Management System.

This module provides reusable caching decorators and helper functions
to optimize database queries and expensive computations.

Usage:
    from utils.cache_helpers import cached_query, invalidate_customer_cache

    @cached_query(timeout=600)  # Cache for 10 minutes
    def get_all_sources():
        return Source.query.order_by(Source.SSource).all()
"""

from functools import wraps
from extensions import cache


def cached_query(timeout=300, key_prefix=None):
    """
    Decorator to cache database query results.

    Args:
        timeout (int): Cache timeout in seconds (default: 300 = 5 minutes)
        key_prefix (str): Optional custom cache key prefix
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Build cache key from function name and arguments
            if key_prefix:
                cache_key = f"{key_prefix}:{f.__name__}"
            else:
                cache_key = f"query:{f.__name__}"

            if args:
                cache_key += f":{':'.join(str(arg) for arg in args)}"
            if kwargs:
                cache_key += (
                    f":{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
                )

            result = cache.get(cache_key)
            if result is not None:
                return result

            result = f(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout)
            return result

        return decorated_function

    return decorator


def invalidate_cache_pattern(pattern):
    """
    Invalidate all cache keys matching a pattern.

    For SimpleCache (default in development), this is a no-op.
    For RedisCache (production), it deletes matching keys using Redis SCAN.

    Args:
        pattern (str): Pattern to match (e.g., "query:get_customer_*")
    """
    backend = getattr(cache, "_cache", None)

    # Redis-based backend
    if hasattr(backend, "scan_iter"):
        deleted = 0
        for key in backend.scan_iter(pattern):
            backend.delete(key)
            deleted += 1
        print(f"[CACHE] Deleted {deleted} keys matching pattern '{pattern}'")

    # SimpleCache fallback (no pattern support)
    else:
        print(
            f"[CACHE] Pattern invalidation not supported for backend {type(backend).__name__}"
        )


def invalidate_customer_cache():
    """
    Invalidate customer-related cache entries.
    Should be called when customer data is modified.
    """
    try:
        # Import lazily to avoid circular imports
        from blueprints.customers import get_customer_filter_options

        cache.delete_memoized(get_customer_filter_options)
    except Exception as e:
        print(f"[CACHE WARN] Could not delete memoized customer filters: {e}")

    cache.delete("query:get_all_customers")
    invalidate_cache_pattern("query:get_customer_*")


def invalidate_source_cache():
    """
    Invalidate source-related cache entries.
    Should be called when source data is modified.
    """
    try:
        from blueprints.sources import get_source_filter_options

        cache.delete_memoized(get_source_filter_options)
    except Exception as e:
        print(f"[CACHE WARN] Could not delete memoized source filters: {e}")

    cache.delete("query:get_all_sources")
    invalidate_cache_pattern("query:get_source_*")


def invalidate_work_order_cache(work_order_no=None):
    """
    Invalidate work order-related cache entries.
    Should be called when work order data is modified.
    """
    cache.delete("query:get_pending_work_orders")
    cache.delete("query:get_dashboard_metrics")

    if work_order_no:
        cache.delete(f"query:get_work_order:{work_order_no}")


def invalidate_repair_order_cache(repair_order_no=None):
    """
    Invalidate repair order-related cache entries.
    Should be called when repair order data is modified.
    """
    cache.delete("query:get_pending_repair_orders")
    cache.delete("query:get_dashboard_metrics")

    if repair_order_no:
        cache.delete(f"query:get_repair_order:{repair_order_no}")


def invalidate_analytics_cache():
    """
    Invalidate analytics-related cache entries.
    Should be called when underlying data changes significantly.
    """
    cache.delete("analytics_dashboard")
    cache.delete("analytics_api_data")
    cache.delete("analytics:revenue_chart")
    cache.delete("analytics:completion_trends")
    cache.delete("analytics:customer_stats")
    print("[CACHE] Invalidated analytics cache entries")


def clear_all_caches():
    """
    Clear all application caches.
    Use with caution - only in development or after major data migrations.
    """
    cache.clear()
    print("[CACHE] Cleared all cache entries")
