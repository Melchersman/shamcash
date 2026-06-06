"""Python client for the ShamCash API."""

from .client import ShamCashAPI, ShamCashAPISync
from .exceptions import (
    AccountNotFoundError,
    AuthInvalidError,
    AuthMissingError,
    FetchFailedError,
    ForbiddenError,
    InternalError,
    NetworkError,
    NotFoundError,
    ProtocolError,
    RateLimitExceededError,
    RequestTimeoutError,
    ShamCashAPIError,
    SubscriptionUnavailableError,
    ValidationError,
    parse_retry_after_header,
)
from .models import (
    Account,
    BalanceRow,
    BalancesResult,
    Currency,
    IncomingTransaction,
    TransactionsResult,
)
from .qr import create_qr_code

__version__ = "1.2.0"

__all__ = [
    "ShamCashAPI",
    "ShamCashAPISync",
    "Account",
    "BalanceRow",
    "BalancesResult",
    "Currency",
    "IncomingTransaction",
    "TransactionsResult",
    "create_qr_code",
    "ShamCashAPIError",
    "ValidationError",
    "AuthMissingError",
    "AuthInvalidError",
    "ForbiddenError",
    "NotFoundError",
    "AccountNotFoundError",
    "SubscriptionUnavailableError",
    "RateLimitExceededError",
    "FetchFailedError",
    "InternalError",
    "NetworkError",
    "ProtocolError",
    "RequestTimeoutError",
    "parse_retry_after_header",
]
