from __future__ import annotations
import asyncio
import logging
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when upstream rate limit is exhausted after retries."""


class UpstreamError(Exception):
    """Raised when an upstream API returns an unrecoverable error."""


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))


class RateLimitedClient:
    """Async HTTP client with rate limiting and retry logic."""

    def __init__(
        self,
        base_url: str,
        rate_limit: float = 10.0,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self._limiter = AsyncLimiter(rate_limit, 1)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=default_headers or {},
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
        )

    async def __aenter__(self) -> "RateLimitedClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        async with self._limiter:
            try:
                response = await self._client.get(path, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    logger.warning("Rate limited by upstream: %s", path)
                    raise
                if exc.response.status_code >= 500:
                    logger.warning("Upstream server error %d: %s", exc.response.status_code, path)
                    raise
                raise UpstreamError(f"HTTP {exc.response.status_code} from {path}") from exc

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        async with self._limiter:
            try:
                response = await self._client.post(path, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    logger.warning("Rate limited by upstream: %s", path)
                    raise
                if exc.response.status_code >= 500:
                    raise
                raise UpstreamError(f"HTTP {exc.response.status_code} from {path}") from exc
