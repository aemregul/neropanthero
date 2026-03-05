"""
Monitoring & Error Tracking Middleware.
Yapılandırılmış hata loglama + API performans izleme.
Sentry gibi harici servise gerek kalmadan çalışır.
"""
import time
import traceback
import logging
from collections import defaultdict
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Yapılandırılmış logger
logger = logging.getLogger("pepper_monitor")
logger.setLevel(logging.INFO)

# Console handler (Railway loglarına düşer)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    "[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(handler)


class MonitoringMiddleware(BaseHTTPMiddleware):
    """
    API Monitoring:
    - İstek süresi ölçme
    - Hata yakalama ve loglama
    - Yavaş endpoint uyarıları
    - Endpoint bazlı istatistikler
    """

    def __init__(self, app, slow_threshold_ms: int = 5000):
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms
        # Endpoint istatistikleri (in-memory, restart'ta sıfırlanır)
        self._stats: dict = defaultdict(lambda: {
            "count": 0,
            "errors": 0,
            "total_ms": 0,
            "max_ms": 0,
            "last_error": None,
        })

    async def dispatch(self, request: Request, call_next):
        # Static/health endpoint'leri izleme
        path = request.url.path
        if path in ("/health", "/", "/docs", "/openapi.json") or path.startswith("/_next"):
            return await call_next(request)

        start = time.time()
        method = request.method

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start) * 1000

            # İstatistik güncelle
            key = f"{method} {path}"
            self._stats[key]["count"] += 1
            self._stats[key]["total_ms"] += duration_ms
            self._stats[key]["max_ms"] = max(self._stats[key]["max_ms"], duration_ms)

            # Yavaş endpoint uyarısı
            if duration_ms > self.slow_threshold_ms:
                logger.warning(
                    f"🐌 YAVAŞ {method} {path} — {duration_ms:.0f}ms (eşik: {self.slow_threshold_ms}ms)"
                )

            # 5xx hataları logla
            if response.status_code >= 500:
                self._stats[key]["errors"] += 1
                self._stats[key]["last_error"] = datetime.now(timezone.utc).isoformat()
                logger.error(
                    f"❌ {response.status_code} {method} {path} — {duration_ms:.0f}ms"
                )

            # Response header'a süreyi ekle
            response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"

            return response

        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            key = f"{method} {path}"
            self._stats[key]["count"] += 1
            self._stats[key]["errors"] += 1
            self._stats[key]["last_error"] = datetime.now(timezone.utc).isoformat()

            # Detaylı hata logu
            logger.error(
                f"💥 HATA {method} {path} — {duration_ms:.0f}ms\n"
                f"   Hata: {type(exc).__name__}: {exc}\n"
                f"   Traceback:\n{traceback.format_exc()}"
            )

            return JSONResponse(
                status_code=500,
                content={"detail": "Sunucu hatası. Lütfen tekrar deneyin."},
            )

    def get_stats(self) -> dict:
        """Monitoring istatistiklerini döndür (admin endpoint için)."""
        stats = {}
        for key, data in self._stats.items():
            avg_ms = data["total_ms"] / data["count"] if data["count"] else 0
            stats[key] = {
                "requests": data["count"],
                "errors": data["errors"],
                "avg_ms": round(avg_ms, 1),
                "max_ms": round(data["max_ms"], 1),
                "error_rate": f"{(data['errors'] / data['count'] * 100):.1f}%" if data["count"] else "0%",
                "last_error": data["last_error"],
            }
        # En çok hata veren endpoint'leri üste koy
        return dict(sorted(stats.items(), key=lambda x: x[1]["errors"], reverse=True))
