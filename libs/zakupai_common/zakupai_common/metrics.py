from prometheus_client import Counter, Gauge, Histogram

GOSZAKUP_ERRORS = Counter(
    "goszakup_request_errors_total",
    "Number of failed requests to Goszakup API",
    labelnames=("endpoint", "reason", "service"),
)

ANTI_DUMPING_PERCENT = Gauge(
    "anti_dumping_percent",
    "Current anti-dumping percentage for last analyzed lot",
    labelnames=("lot_id", "service"),
)

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests",
    labelnames=("service", "method", "endpoint", "status_code"),
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    labelnames=("service", "method", "endpoint"),
    buckets=(0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10),
)


def record_goszakup_error(service: str, endpoint: str, reason: str) -> None:
    GOSZAKUP_ERRORS.labels(endpoint=endpoint, reason=reason, service=service).inc()


def set_anti_dumping(service: str, lot_id: str, percent: float) -> None:
    ANTI_DUMPING_PERCENT.labels(lot_id=str(lot_id), service=service).set(percent)
