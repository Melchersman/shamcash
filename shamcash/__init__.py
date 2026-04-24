"""
ShamCash API — Python client for ``https://api.shamcash-api.com/v1``.

Authenticate with a dashboard API token (``Authorization: Bearer``), then list
linked accounts, read balances, and query incoming transactions (with filters
and single-transaction lookup).
"""

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

__version__ = "1.1.0"

__all__ = [
    "ShamCashAPI",
    "ShamCashAPISync",
    "Account",
    "BalanceRow",
    "BalancesResult",
    "Currency",
    "IncomingTransaction",
    "TransactionsResult",
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
