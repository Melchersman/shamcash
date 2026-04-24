"""Exception types for the ShamCash client."""

from __future__ import annotations

from typing import Any, Optional, Type


class ShamCashAPIError(Exception):
    """Base class for SDK and API errors."""

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
        super().__init__(message)

    def __str__(self) -> str:
        parts: list[str] = []
        if self.code:
            parts.append(f"[{self.code}]")
        parts.append(self.message)
        if self.http_status is not None:
            parts.append(f"(HTTP {self.http_status})")
        if self.retry_after is not None:
            parts.append(f"retry_after={self.retry_after}s")
        return " ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}({self.message!r}, code={self.code!r}, "
            f"http_status={self.http_status!r}, retry_after={self.retry_after!r}, data={self.data!r})"
        )


class ValidationError(ShamCashAPIError):
    """`VALIDATION_ERROR`."""


class AuthMissingError(ShamCashAPIError):
    """`AUTH_MISSING`."""


class AuthInvalidError(ShamCashAPIError):
    """`AUTH_INVALID`."""


class ForbiddenError(ShamCashAPIError):
    """`FORBIDDEN`."""


class NotFoundError(ShamCashAPIError):
    """`NOT_FOUND`."""


class AccountNotFoundError(ShamCashAPIError):
    """`ACCOUNT_NOT_FOUND`."""


class SubscriptionUnavailableError(ShamCashAPIError):
    """`SUBSCRIPTION_UNAVAILABLE`."""


class RateLimitExceededError(ShamCashAPIError):
    """`RATE_LIMIT_EXCEEDED`."""


class FetchFailedError(ShamCashAPIError):
    """`FETCH_FAILED`."""


class InternalError(ShamCashAPIError):
    """`INTERNAL_ERROR`."""


class NetworkError(ShamCashAPIError):
    """Network or transport failure."""


class RequestTimeoutError(ShamCashAPIError):
    """Request timeout."""

    def __init__(
        self,
        message: str = "Request timed out",
        code: str = "TIMEOUT",
        data: Any = None,
        http_status: Optional[int] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            data=data,
            http_status=http_status,
            retry_after=retry_after,
        )


class ProtocolError(ShamCashAPIError):
    """Invalid JSON or payload shape."""


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
    if not value:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def raise_for_envelope_code(
    code: str,
    message: Optional[str] = None,
    data: Any = None,
    http_status: Optional[int] = None,
    retry_after: Optional[int] = None,
) -> None:
    exc_type = ERROR_MAP.get(code, ShamCashAPIError)
    text = message or code
    raise exc_type(
        text,
        code=code,
        data=data,
        http_status=http_status,
        retry_after=retry_after if exc_type is RateLimitExceededError else None,
    )