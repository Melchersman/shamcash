"""
Exceptions for the ShamCash HTTP API (envelope ``code`` values) and client protocol errors.
"""

from __future__ import annotations

from typing import Any, Optional, Type


class ShamCashAPIError(Exception):
    """
    Base exception for ShamCash client and API errors.

    Attributes:
        message: Human-readable message.
        code: Machine code when applicable.
        data: Server ``data`` field or a small debug payload.
        http_status: HTTP status from the last response when available.
        retry_after: Seconds to wait when server sent ``Retry-After`` (e.g. 429).
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        data: Any = None,
        http_status: Optional[int] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        self.message = message
        self.code = code
        self.data = data
        self.http_status = http_status
        self.retry_after = retry_after
        super().__init__(self.message)

    def __str__(self) -> str:
        parts: list[str] = []
        if self.code:
            parts.append(f"[{self.code}]")
        parts.append(self.message)
        if self.http_status is not None:
            parts.append(f"(HTTP {self.http_status})")
        if self.retry_after is not None:
            parts.append(f"retry_after={self.retry_after}s")
        return " ".join(p for p in parts if p)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}({self.message!r}, code={self.code!r}, "
            f"http_status={self.http_status!r}, retry_after={self.retry_after!r}, data={self.data!r})"
        )


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
    """
    Transport failure: DNS, connection, TLS, and other :mod:`aiohttp` client errors
    that are not application-level JSON.
    """


class RequestTimeoutError(ShamCashAPIError):
    """Request exceeded the configured time limit (distinct from business errors)."""

    def __init__(
        self,
        message: str = "Request timed out",
        code: str = "TIMEOUT",
        data: Any = None,
        http_status: Optional[int] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        super().__init__(message, code=code, data=data, http_status=http_status, retry_after=retry_after)


class ProtocolError(ShamCashAPIError):
    """
    Response could not be parsed or did not match the expected JSON shape (envelope or documented ``data`` schema).
    This is a client-side classification; it is not a server business ``code``.
    """


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


def parse_retry_after_header(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    value = value.strip()
    # Retry-After can be a delay-seconds or an HTTP date; we only parse integer seconds
    try:
        return int(value)
    except ValueError:
        return None


def raise_for_envelope_code(
    code: str,
    message: Optional[str] = None,
    data: Any = None,
    http_status: Optional[int] = None,
    retry_after: Optional[int] = None,
) -> None:
    """Raise the appropriate exception for an API ``code`` string."""
    error_message = message or f"API error: {code}"
    exc_type = ERROR_MAP.get(code, ShamCashAPIError)
    if exc_type is RateLimitExceededError:
        raise exc_type(
            error_message,
            code=code,
            data=data,
            http_status=http_status,
            retry_after=retry_after,
        )
    raise exc_type(
        error_message,
        code=code,
        data=data,
        http_status=http_status,
        retry_after=None,
    )
