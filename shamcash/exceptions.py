"""
Exceptions for the ShamCash HTTP API (envelope ``code`` values).
"""

from __future__ import annotations

from typing import Any, Optional, Type


class ShamCashAPIError(Exception):
    """Base exception for all ShamCash API errors."""

    def __init__(self, message: str, code: Optional[str] = None, data: Any = None):
        self.message = message
        self.code = code
        self.data = data
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class ValidationError(ShamCashAPIError):
    """Malformed or conflicting query parameters (``VALIDATION_ERROR``)."""


class AuthMissingError(ShamCashAPIError):
    """Missing ``Authorization`` header or empty bearer token (``AUTH_MISSING``)."""


class AuthInvalidError(ShamCashAPIError):
    """Token is invalid, unknown, expired, or revoked (``AUTH_INVALID``)."""


class ForbiddenError(ShamCashAPIError):
    """Token is valid but not allowed to perform the action (``FORBIDDEN``)."""


class NotFoundError(ShamCashAPIError):
    """Generic not found (``NOT_FOUND``)."""


class AccountNotFoundError(ShamCashAPIError):
    """Linked account does not exist or does not belong to the user (``ACCOUNT_NOT_FOUND``)."""


class SubscriptionUnavailableError(ShamCashAPIError):
    """Account inactive, missing subscription, or subscription ended (``SUBSCRIPTION_UNAVAILABLE``)."""


class RateLimitExceededError(ShamCashAPIError):
    """Too many requests for the current rate limit window (``RATE_LIMIT_EXCEEDED``)."""


class FetchFailedError(ShamCashAPIError):
    """Upstream or internal data fetch failed (``FETCH_FAILED``)."""


class InternalError(ShamCashAPIError):
    """Unexpected server error (``INTERNAL_ERROR``)."""


class NetworkError(ShamCashAPIError):
    """Transport, non-JSON, or unexpected HTTP failure (client-side classification)."""


ERROR_MAP: dict[str, Type[ShamCashAPIError]] = {
    "VALIDATION_ERROR": ValidationError,
    "AUTH_MISSING": AuthMissingError,
    "AUTH_INVALID": AuthInvalidError,
    "FORBIDDEN": ForbiddenError,
    "NOT_FOUND": NotFoundError,
    "ACCOUNT_NOT_FOUND": AccountNotFoundError,
    "SUBSCRIPTION_UNAVAILABLE": SubscriptionUnavailableError,
    "RATE_LIMIT_EXCEEDED": RateLimitExceededError,
    "FETCH_FAILED": FetchFailedError,
    "INTERNAL_ERROR": InternalError,
}


def raise_for_envelope_code(
    code: str, message: Optional[str] = None, data: Any = None
) -> None:
    """Raise the appropriate exception for an API ``code`` string."""
    exc_type = ERROR_MAP.get(code, ShamCashAPIError)
    error_message = message or f"API error: {code}"
    raise exc_type(error_message, code=code, data=data)
