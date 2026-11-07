import asyncio
import json
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any


class RequestGuardMiddleware:
    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        max_body_bytes: int,
        window_seconds: int,
        auth_limit: int,
        search_limit: int,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.window_seconds = window_seconds
        self.limits = {
            "/auth/register": auth_limit,
            "/auth/login": auth_limit,
            "/auth/token": auth_limit,
            "/matching/search": search_limit,
        }
        self.requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()
        self.request_count = 0

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Awaitable[Any]], send: Callable[..., Awaitable[None]]) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                await self._respond(send, 400, {"detail": "Invalid Content-Length"})
                return
            if declared_size > self.max_body_bytes:
                await self._respond(send, 413, {"detail": "Request body is too large"})
                return

        path = scope.get("path", "")
        limit = self.limits.get(path)
        if limit is not None:
            client = scope.get("client")
            remote = client[0] if client else "unknown"
            if not await self._allowed(path, remote, limit):
                await self._respond(
                    send,
                    429,
                    {"detail": "Too many requests; try again later"},
                    [(b"retry-after", str(self.window_seconds).encode())],
                )
                return

        messages: list[dict[str, Any]] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            messages.append(message)
            size += len(message.get("body", b""))
            if size > self.max_body_bytes:
                await self._respond(send, 413, {"detail": "Request body is too large"})
                return
            if not message.get("more_body", False):
                break

        async def replay_receive() -> dict[str, Any]:
            if messages:
                return messages.pop(0)
            return await receive()

        await self.app(scope, replay_receive, send)

    async def _allowed(self, path: str, remote: str, limit: int) -> bool:
        now = time.monotonic()
        async with self.lock:
            bucket = self.requests[(path, remote)]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            allowed = len(bucket) < limit
            if allowed:
                bucket.append(now)
            self.request_count += 1
            if self.request_count % 256 == 0:
                expired = [
                    key
                    for key, entries in self.requests.items()
                    if not entries or entries[-1] <= cutoff
                ]
                for key in expired:
                    self.requests.pop(key, None)
            return allowed

    @staticmethod
    async def _respond(
        send: Callable[..., Awaitable[None]],
        status_code: int,
        payload: dict[str, str],
        headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        body = json.dumps(payload).encode()
        response_headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ]
        if headers:
            response_headers.extend(headers)
        await send({"type": "http.response.start", "status": status_code, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})
