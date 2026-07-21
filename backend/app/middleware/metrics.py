"""
请求指标采集中间件
记录请求计数、响应时长等 Prometheus 指标
"""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# Prometheus 指标
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
)

ACTIVE_REQUESTS = Gauge(
    "http_requests_active",
    "Number of active HTTP requests",
    ["method"]
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """请求指标采集中间件"""

    async def dispatch(self, request: Request, call_next):
        # 跳过 metrics 端点自身以避免循环
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = request.url.path

        ACTIVE_REQUESTS.labels(method=method).inc()

        start_time = time.time()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            status_code = getattr(e, "status_code", 500)
            raise
        finally:
            duration = time.time() - start_time

            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status=status_code
            ).inc()

            REQUEST_DURATION.labels(
                method=method,
                endpoint=path
            ).observe(duration)

            ACTIVE_REQUESTS.labels(method=method).dec()
