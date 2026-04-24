"""
ShamCash API — Python client for ``https://api.shamcash-api.com/v1``.

Authenticate with a dashboard API token (``Authorization: Bearer``), then list
linked accounts, read balances, and query incoming transactions (with filters
and single-transaction lookup).
"""

from .client import ShamCashAPI, ShamCashAPISync
from .models import (
    Account,
    BalanceRow,
    BalancesResult,
    Currency,
    IncomingTransaction,
    TransactionsResult,
)
from .exceptions import (
    ShamCashAPIError,
    ValidationError,
    AuthMissingError,
    AuthInvalidError,
    ForbiddenError,
    NotFoundError,
    AccountNotFoundError,
    SubscriptionUnavailableError,
    RateLimitExceededError,
    FetchFailedError,
    InternalError,
    NetworkError,
)

__version__ = "1.0.0"

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
]
