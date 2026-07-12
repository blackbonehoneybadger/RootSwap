from prometheus_client import Counter, Gauge, generate_latest

REQUESTS_TOTAL = Counter("rootswap_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
WEBHOOK_EVENTS = Counter("rootswap_webhook_events_total", "Webhook events", ["partner", "status"])
EMERGENCY_STOP = Gauge("rootswap_emergency_stop", "Emergency stop active (1=yes)")


def metrics_response() -> bytes:
    return generate_latest()
