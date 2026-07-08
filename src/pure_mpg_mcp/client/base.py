"""Base HTTP plumbing shared by every PureClient endpoint: init, retries."""

from __future__ import annotations

import asyncio
import os
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://pure.mpg.de/rest"
USER_AGENT = "pure-mpg-mcp/0.1 (+https://github.com/)"
DEFAULT_RETRIES = 3
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class BaseClient:
    """HTTP transport, retries, and lifecycle — no endpoint knowledge."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("PURE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "BaseClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _get(self, path: str, accept: str | None = None, **params: Any) -> httpx.Response:
        clean = {k: v for k, v in params.items() if v is not None}
        headers = {"Accept": accept} if accept else None
        return await self._send_with_retries(lambda: self._client.get(path, params=clean, headers=headers))

    async def _post_json(self, path: str, json_body: Any, **params: Any) -> httpx.Response:
        clean = {k: v for k, v in params.items() if v is not None}
        return await self._send_with_retries(lambda: self._client.post(path, params=clean, json=json_body))

    async def _send_with_retries(
        self,
        send: Callable[[], Awaitable[httpx.Response]],
        *,
        attempts: int = DEFAULT_RETRIES + 1,
        base_delay: float = 0.5,
    ) -> httpx.Response:
        """Issue a request, retrying 429/5xx and network errors with backoff.

        Applies uniformly to every GET/POST this client makes (via `_get` /
        `_post_json`) so no endpoint has to opt in individually.
        """
        for attempt in range(attempts):
            try:
                resp = await send()
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in RETRYABLE_STATUS_CODES or attempt == attempts - 1:
                    raise
                await self._sleep_before_retry(exc.response, attempt, base_delay)
            except httpx.HTTPError:
                if attempt == attempts - 1:
                    raise
                await self._sleep_before_retry(None, attempt, base_delay)
        raise AssertionError("unreachable")  # last attempt always returns or raises above

    @staticmethod
    async def _sleep_before_retry(response: httpx.Response | None, attempt: int, base_delay: float) -> None:
        retry_after = response.headers.get("Retry-After") if response is not None else None
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                delay = base_delay * (2**attempt)
        else:
            delay = base_delay * (2**attempt)
        delay += random.uniform(0, base_delay)
        await asyncio.sleep(delay)
