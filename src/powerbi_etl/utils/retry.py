"""
Retry utilities with exponential backoff for resilient operations.
"""

import time
import random
from typing import Callable, Type, Tuple, Any, Optional
from functools import wraps
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    should_retry: Optional[Callable[[Exception], bool]] = None

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (0-indexed)."""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        if self.jitter:
            # Add jitter to prevent thundering herd
            jitter_range = delay * self.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)
        return max(0, delay)


def retry(policy: RetryPolicy = None) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.
    
    Usage:
        @retry(RetryPolicy(max_attempts=3, base_delay=1.0))
        def flaky_operation():
            ...
    """
    policy = policy or RetryPolicy()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(policy.max_attempts):
                try:
                    return func(*args, **kwargs)
                except policy.retry_exceptions as e:
                    last_exception = e
                    
                    # Check custom retry condition
                    if policy.should_retry and not policy.should_retry(e):
                        logger.debug("Exception not retryable", exception=str(e))
                        raise
                    
                    if attempt < policy.max_attempts - 1:
                        delay = policy.get_delay(attempt)
                        logger.warning(
                            "Operation failed, retrying",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=policy.max_attempts,
                            delay=f"{delay:.2f}s",
                            error=str(e),
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "Operation failed after all retries",
                            function=func.__name__,
                            attempts=policy.max_attempts,
                            error=str(e),
                        )
                        raise
            
            # Should not reach here, but just in case
            raise last_exception
        
        return wrapper
    return decorator


class AsyncRetryPolicy(RetryPolicy):
    """Retry policy for async functions."""
    pass


def async_retry(policy: AsyncRetryPolicy = None) -> Callable:
    """Decorator for retrying async functions."""
    policy = policy or AsyncRetryPolicy()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            import asyncio
            last_exception = None
            
            for attempt in range(policy.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except policy.retry_exceptions as e:
                    last_exception = e
                    
                    if policy.should_retry and not policy.should_retry(e):
                        raise
                    
                    if attempt < policy.max_attempts - 1:
                        delay = policy.get_delay(attempt)
                        logger.warning(
                            "Async operation failed, retrying",
                            function=func.__name__,
                            attempt=attempt + 1,
                            delay=f"{delay:.2f}s",
                            error=str(e),
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "Async operation failed after all retries",
                            function=func.__name__,
                            attempts=policy.max_attempts,
                            error=str(e),
                        )
                        raise
            
            raise last_exception
        
        return wrapper
    return decorator


# Pre-defined policies for common scenarios
DATABASE_RETRY = RetryPolicy(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    retry_exceptions=(ConnectionError, TimeoutError, IOError),
)

HTTP_RETRY = RetryPolicy(
    max_attempts=3,
    base_delay=1.0,
    max_delay=60.0,
    retry_exceptions=(ConnectionError, TimeoutError),
    should_retry=lambda e: not hasattr(e, 'response') or e.response.status_code >= 500,
)

FILE_RETRY = RetryPolicy(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    retry_exceptions=(IOError, OSError, PermissionError),
)