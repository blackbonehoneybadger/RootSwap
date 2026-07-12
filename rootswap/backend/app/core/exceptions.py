class DomainError(Exception):
    def __init__(self, message: str, code: str = "domain_error") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(DomainError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, "not_found")


class ForbiddenError(DomainError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, "forbidden")


class UnauthorizedError(DomainError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, "unauthorized")


class ValidationError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "validation_error")


class ConflictError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "conflict")


class EmergencyStopError(DomainError):
    def __init__(self, message: str = "Emergency stop is active") -> None:
        super().__init__(message, "emergency_stop")


class InvalidTransitionError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "invalid_transition")
