#!/usr/bin/env python3
"""
Test script to demonstrate retry functionality with exponential backoff.
This script simulates various failure scenarios to test the retry logic.
"""

import asyncio
import logging
import random
from typing import Optional

from src.utils.constants import LOG_FORMAT
from src.utils.utils import retry_async, calculate_retry_delay

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class SimulatedAPIError(Exception):
    """Simulated API error for testing."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


async def simulate_api_call(failure_rate: float = 0.7, transient_only: bool = True) -> str:
    """Simulate an API call that might fail.
    
    Args:
        failure_rate: Probability of failure (0.0 = never fail, 1.0 = always fail)
        transient_only: If True, only throw transient errors (5xx), else mix with 4xx
        
    Returns:
        Success message if the call succeeds
        
    Raises:
        SimulatedAPIError: If the call fails
    """
    if random.random() < failure_rate:
        if transient_only:
            status_codes = [500, 502, 503, 504]
            messages = [
                "Internal Server Error",
                "Bad Gateway", 
                "Service Unavailable",
                "Gateway Timeout"
            ]
        else:
            status_codes = [400, 401, 403, 404, 500, 502, 503, 504]
            messages = [
                "Bad Request",
                "Unauthorized",
                "Forbidden", 
                "Not Found",
                "Internal Server Error",
                "Bad Gateway",
                "Service Unavailable", 
                "Gateway Timeout"
            ]
        
        status_code = random.choice(status_codes)
        message = messages[status_codes.index(status_code)]
        
        logging.warning(f"Simulating API failure: {status_code} {message}")
        raise SimulatedAPIError(status_code, message)
    
    return "API call successful!"


async def test_basic_retry():
    """Test basic retry functionality with a flaky API."""
    logging.info("=== Testing Basic Retry ===")
    
    try:
        result = await retry_async(
            simulate_api_call,
            failure_rate=0.8,  # High failure rate
            transient_only=True,
            max_attempts=3,
            retryable_exceptions=(SimulatedAPIError,)
        )
        logging.info(f"✅ Success: {result}")
    except Exception as e:
        logging.error(f"❌ Final failure: {e}")


async def test_exponential_backoff():
    """Test exponential backoff timing."""
    logging.info("=== Testing Exponential Backoff Timing ===")
    
    for attempt in range(4):
        delay = calculate_retry_delay(attempt, jitter=False)
        delay_with_jitter = calculate_retry_delay(attempt, jitter=True)
        logging.info(f"Attempt {attempt}: {delay:.2f}s (without jitter), {delay_with_jitter:.2f}s (with jitter)")


async def test_non_retryable_errors():
    """Test that non-retryable errors are not retried."""
    logging.info("=== Testing Non-Retryable Errors ===")
    
    try:
        result = await retry_async(
            simulate_api_call,
            failure_rate=1.0,  # Always fail
            transient_only=False,  # Mix 4xx and 5xx errors
            max_attempts=3,
            retryable_exceptions=(SimulatedAPIError,)
        )
        logging.info(f"✅ Success: {result}")
    except SimulatedAPIError as e:
        if e.status_code >= 500:
            logging.error(f"❌ Failed after retries (transient error): {e}")
        else:
            logging.info(f"✅ Correctly failed immediately (non-retryable error): {e}")
    except Exception as e:
        logging.error(f"❌ Unexpected error: {e}")


async def test_eventual_success():
    """Test that the function eventually succeeds after a few retries."""
    logging.info("=== Testing Eventual Success ===")
    
    # Simulate an API that fails the first 2 times but succeeds on the 3rd
    call_count = 0
    
    async def flaky_api():
        nonlocal call_count
        call_count += 1
        
        if call_count <= 2:
            raise SimulatedAPIError(503, "Service Unavailable")
        return f"Success on attempt {call_count}!"
    
    try:
        result = await retry_async(
            flaky_api,
            max_attempts=5,
            retryable_exceptions=(SimulatedAPIError,)
        )
        logging.info(f"✅ Success: {result}")
    except Exception as e:
        logging.error(f"❌ Final failure: {e}")


async def main():
    """Run all retry tests."""
    logging.info("🧪 Starting Retry Functionality Tests")
    logging.info("=" * 50)
    
    await test_exponential_backoff()
    print()
    
    await test_basic_retry()
    print()
    
    await test_eventual_success()
    print()
    
    await test_non_retryable_errors()
    print()
    
    logging.info("=" * 50)
    logging.info("🎉 Retry tests completed!")


if __name__ == "__main__":
    asyncio.run(main()) 