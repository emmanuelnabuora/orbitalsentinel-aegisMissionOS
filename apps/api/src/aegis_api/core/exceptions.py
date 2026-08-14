"""Domain exceptions. Routers never raise HTTPException for domain errors —
services raise these and global handlers map them to status codes."""


class DomainError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    """Resource does not exist -> 404."""


class ConflictError(DomainError):
    """State conflict (duplicate, already linked) -> 409."""


class AuthError(DomainError):
    """Authentication failed -> 401. Message is deliberately generic."""


class ValidationFailure(DomainError):
    """Domain rule violated -> 422."""


class RateLimitedError(DomainError):
    """Too many attempts; retry later."""
