"""
Rate Limiting Middleware — In-Memory (Redis opsiyonel).
IP bazlı istek hız sınırlama.
"""
import time
from collections import defaultdict
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Basit sliding-window rate limiter.
    - Genel API: 60 istek / dakika
    - AI üretim endpoint'leri: 10 istek / dakika
    - Auth endpoint'leri: 20 istek / dakika
    """

    def __init__(self, app, general_limit: int = 60, ai_limit: int = 10, auth_limit: int = 20, window: int = 60):
        super().__init__(app)
        self.general_limit = general_limit
        self.ai_limit = ai_limit
        self.auth_limit = auth_limit
        self.window = window  # saniye
        # IP → [(timestamp, count)] şeklinde takip
        self._requests: Dict[str, list] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """İstemci IP adresini al (proxy arkasında da çalışır)."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_limit_for_path(self, path: str) -> Tuple[int, str]:
        """Endpoint'e göre limit belirle."""
        if "/chat/" in path or "/generate" in path:
            return self.ai_limit, "ai"
        elif "/auth/" in path:
            return self.auth_limit, "auth"
        return self.general_limit, "general"

    def _clean_old_requests(self, ip: str, now: float):
        """Zaman penceresi dışına çıkmış istekleri temizle."""
        cutoff = now - self.window
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]

    async def dispatch(self, request: Request, call_next):
        # Health check ve static dosyalar limitlenmez
        path = request.url.path
        if path in ("/health", "/", "/docs", "/openapi.json") or path.startswith("/_next"):
            return await call_next(request)

        # WebSocket limitlenmez
        if path.startswith("/ws/"):
            return await call_next(request)

        ip = self._get_client_ip(request)
        now = time.time()
        limit, category = self._get_limit_for_path(path)

        # Kategori bazlı key
        key = f"{ip}:{category}"
        self._clean_old_requests(key, now)

        current_count = len(self._requests[key])

        if current_count >= limit:
            retry_after = int(self.window - (now - self._requests[key][0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Çok fazla istek. Lütfen {retry_after} saniye sonra tekrar deneyin.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        self._requests[key].append(now)

        response = await call_next(request)

        # Rate limit bilgisini header'lara ekle
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current_count - 1))
        response.headers["X-RateLimit-Reset"] = str(int(now + self.window))

        return response
