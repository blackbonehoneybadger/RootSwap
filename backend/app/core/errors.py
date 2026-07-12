"""Domain errors mapped to HTTP responses in the API layer."""


class DomainError(Exception):
    code = "domain_error"
    http_status = 400

    def __init__(self, message: str = "", **details):
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details


class NotFoundError(DomainError):
    code = "not_found"
    http_status = 404


class AuthError(DomainError):
    code = "auth_error"
    http_status = 401


class ForbiddenError(DomainError):
    code = "forbidden"
    http_status = 403


class QuoteExpiredError(DomainError):
    code = "quote_expired"
    http_status = 409


class QuoteConsumedError(DomainError):
    code = "quote_consumed"
    http_status = 409


class InvalidTransitionError(DomainError):
    code = "invalid_transition"
    http_status = 409


class IdempotencyConflictError(DomainError):
    code = "idempotency_conflict"
    http_status = 409


class EmergencyStopError(DomainError):
    code = "emergency_stop_active"
    http_status = 503


class ValidationFailedError(DomainError):
    code = "validation_failed"
    http_status = 422


class PartnerUnavailableError(DomainError):
    code = "partner_unavailable"
    http_status = 502


class RateLimitedError(DomainError):
    code = "rate_limited"
    http_status = 429


class WebhookRejectedError(DomainError):
    code = "webhook_rejected"
    http_status = 400


class UnknownWebhookEventError(DomainError):
    """Unrecognized partner event_type — must not be treated as a processed no-op."""

    code = "unknown_webhook_event"
    http_status = 422
