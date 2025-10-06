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

    Usage:
        @cached_query(timeout=600)
        def get_filter_options():
            return Source.query.distinct().all()
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Build cache key from function name and arguments
            if key_prefix:
                cache_key = f"{key_prefix}:{f.__name__}"
            else:
                cache_key = f"query:{f.__name__}"

            # Add arguments to cache key for uniqueness
            if args:
                cache_key += f":{':'.join(str(arg) for arg in args)}"
            if kwargs:
                cache_key += f":{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"

            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Execute function and cache result
            result = f(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout)
            return result

        return decorated_function
    return decorator


def invalidate_cache_pattern(pattern):
    """
    Invalidate all cache keys matching a pattern.

    Args:
        pattern (str): Pattern to match (e.g., "query:get_customer_*")

    Note: This only works with cache backends that support pattern deletion.
          SimpleCache doesn't support this, so use specific invalidation instead.
    """
    # For SimpleCache, we need to clear all or use specific keys
    # This is a placeholder for future Redis implementation
    pass


def invalidate_customer_cache():
    """
    Invalidate customer-related cache entries.
    Should be called when customer data is modified.
    """
    cache.delete_memoized('get_customer_filter_options')
    cache.delete('query:get_all_customers')


def invalidate_source_cache():
    """
    Invalidate source-related cache entries.
    Should be called when source data is modified.
    """
    cache.delete_memoized('get_source_filter_options')
    cache.delete('query:get_all_sources')


def invalidate_work_order_cache(work_order_no=None):
    """
    Invalidate work order-related cache entries.
    Should be called when work order data is modified.

    Args:
        work_order_no (str): Specific work order number to invalidate
    """
    cache.delete('query:get_pending_work_orders')
    cache.delete('query:get_dashboard_metrics')

    if work_order_no:
        cache.delete(f'query:get_work_order:{work_order_no}')


def invalidate_repair_order_cache(repair_order_no=None):
    """
    Invalidate repair order-related cache entries.
    Should be called when repair order data is modified.

    Args:
        repair_order_no (str): Specific repair order number to invalidate
    """
    cache.delete('query:get_pending_repair_orders')
    cache.delete('query:get_dashboard_metrics')

    if repair_order_no:
        cache.delete(f'query:get_repair_order:{repair_order_no}')


def invalidate_analytics_cache():
    """
    Invalidate analytics-related cache entries.
    Should be called when underlying data changes significantly.
    """
    cache.delete('analytics:revenue_chart')
    cache.delete('analytics:completion_trends')
    cache.delete('analytics:customer_stats')


# Convenience function for clearing all caches
def clear_all_caches():
    """
    Clear all application caches.
    Use with caution - only in development or after major data migrations.
    """
    cache.clear()