"""Business metrics for risk-engine service."""

import os
from prometheus_client import Counter, Gauge, start_http_server

# ===========================================
# Business Metrics
# ===========================================

# Anti-dumping violations ratio
anti_dumping_ratio = Gauge(
    "anti_dumping_ratio",
    "Anti-dumping violations detected per 100 analyzed lots",
)

# Goszakup API errors
goszakup_errors_total = Counter(
    "goszakup_errors_total",
    "Total errors from Goszakup API",
    ["error_type"],
)

# Risk assessments performed
risk_assessments_total = Counter(
    "risk_assessments_total",
    "Total risk assessments performed",
    ["risk_level"],
)

# RNU validation results
rnu_validations_total = Counter(
    "rnu_validations_total",
    "Total RNU validations performed",
    ["result"],
)


# ===========================================
# Metrics HTTP Server
# ===========================================

def init_metrics_server(port: int = 9102):
    """
    Start Prometheus metrics HTTP server on specified port.

    Args:
        port: Port to expose metrics endpoint (default: 9102)
    """
    try:
        start_http_server(port)
        print(f"✅ Prometheus metrics server started on port {port}")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"⚠️  Metrics server already running on port {port}")
        else:
            raise


# Auto-start metrics server if METRICS_PORT is set
if os.getenv("METRICS_PORT"):
    init_metrics_server(int(os.getenv("METRICS_PORT", "9102")))
