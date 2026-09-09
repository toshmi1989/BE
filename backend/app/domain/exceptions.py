class DomainError(Exception):
    """Base domain error."""

    def __init__(self, code: str, message: str, field: str | None = None, details: dict | None = None):
        self.code = code
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(message)


class NotFoundError(DomainError):
    def __init__(self, message: str = "Resource not found", field: str | None = None):
        super().__init__("NOT_FOUND", message, field=field)


class ConflictError(DomainError):
    def __init__(self, message: str, field: str | None = None, details: dict | None = None):
        super().__init__("CONFLICT", message, field=field, details=details)


class ProvenanceGuardError(DomainError):
    def __init__(self, message: str, field: str | None = "provenance.status"):
        super().__init__("PROVENANCE_GUARD", message, field=field)


class ValidationError(DomainError):
    def __init__(self, message: str, field: str | None = None, details: dict | None = None):
        super().__init__("VALIDATION_ERROR", message, field=field, details=details)
