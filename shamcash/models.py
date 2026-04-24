"""Typed response models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional

from .exceptions import ProtocolError


def _decimal(value: Any, field: str) -> Decimal:
    if value is None:
        raise ProtocolError(
            f"missing numeric field {field!r}",
            code="INVALID_PAYLOAD",
            data={field: value},
        )
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProtocolError(
            f"invalid decimal for {field!r}",
            code="INVALID_PAYLOAD",
            data={field: value},
        ) from exc


def _decimal_or_zero(value: Any, field: str) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProtocolError(
            f"invalid decimal for {field!r}",
            code="INVALID_PAYLOAD",
            data={field: value},
        ) from exc


def _as_dict(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolError(
            f"{context} must be an object",
            code="INVALID_PAYLOAD",
            data=value,
        )
    return value


def _string(value: Any) -> str:
    return "" if value is None else str(value)


def _required_datetime(value: Any, field: str) -> datetime:
    if value in (None, ""):
        raise ProtocolError(
            f"missing timestamp field {field!r}",
            code="INVALID_PAYLOAD",
            data={field: value},
        )
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ProtocolError(
            f"invalid timestamp for {field!r}",
            code="INVALID_PAYLOAD",
            data={field: value},
        ) from exc


def _optional_datetime(value: Any, field: str) -> Optional[datetime]:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ProtocolError(
            f"invalid timestamp for {field!r}",
            code="INVALID_PAYLOAD",
            data={field: value},
        ) from exc


@dataclass(frozen=True)
class Currency:
    """Currency descriptor."""

    id: int
    code: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Currency":
        data = _as_dict(data, "currency")
        if "id" not in data or "code" not in data:
            raise ProtocolError("currency must include id and code", code="INVALID_PAYLOAD", data=data)
        try:
            return cls(id=int(data["id"]), code=str(data["code"]))
        except (TypeError, ValueError) as exc:
            raise ProtocolError("invalid currency payload", code="INVALID_PAYLOAD", data=data) from exc


@dataclass(frozen=True)
class Account:
    """Linked account."""

    id: str
    name: str
    email: str
    phone: str
    status: str
    subscription_expires_at: Optional[datetime]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Account":
        data = _as_dict(data, "account")
        for key in ("id", "name", "email", "phone", "status"):
            if key not in data:
                raise ProtocolError(f"account missing {key!r}", code="INVALID_PAYLOAD", data=data)
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            email=str(data["email"]),
            phone=str(data["phone"]),
            status=str(data["status"]),
            subscription_expires_at=_optional_datetime(
                data.get("subscription_expires_at"),
                "subscription_expires_at",
            ),
        )


@dataclass(frozen=True)
class BalanceRow:
    """Balance row."""

    currency: Currency
    available: Decimal
    blocked: Decimal

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BalanceRow":
        data = _as_dict(data, "balance row")
        return cls(
            currency=Currency.from_dict(_as_dict(data.get("currency"), "balance row currency")),
            available=_decimal_or_zero(data.get("available"), "available"),
            blocked=_decimal_or_zero(data.get("blocked"), "blocked"),
        )


@dataclass(frozen=True)
class BalancesResult:
    """Balances payload."""

    account_id: str
    balances: List[BalanceRow]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BalancesResult":
        data = _as_dict(data, "balances payload")
        if "account_id" not in data or "balances" not in data:
            raise ProtocolError("invalid balances payload", code="INVALID_PAYLOAD", data=data)
        rows = data["balances"]
        if not isinstance(rows, list):
            raise ProtocolError("balances must be an array", code="INVALID_PAYLOAD", data=rows)
        return cls(
            account_id=str(data["account_id"]),
            balances=[BalanceRow.from_dict(_as_dict(row, "balance row")) for row in rows],
        )


@dataclass(frozen=True)
class IncomingTransaction:
    """Incoming transaction."""

    transaction_id: int
    amount: Decimal
    currency: Currency
    occurred_at: datetime
    receiver_name: str
    sender_name: str
    sender_address: str
    note: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IncomingTransaction":
        data = _as_dict(data, "transaction")
        for key in ("transaction_id", "currency", "occurred_at"):
            if key not in data:
                raise ProtocolError(f"transaction missing {key!r}", code="INVALID_PAYLOAD", data=data)
        try:
            transaction_id = int(data["transaction_id"])
        except (TypeError, ValueError) as exc:
            raise ProtocolError("invalid transaction_id", code="INVALID_PAYLOAD", data=data) from exc
        return cls(
            transaction_id=transaction_id,
            amount=_decimal_or_zero(data.get("amount"), "amount"),
            currency=Currency.from_dict(_as_dict(data.get("currency"), "transaction currency")),
            occurred_at=_required_datetime(data.get("occurred_at"), "occurred_at"),
            receiver_name=_string(data.get("receiver_name")),
            sender_name=_string(data.get("sender_name")),
            sender_address=_string(data.get("sender_address")),
            note=_string(data.get("note")),
        )


@dataclass(frozen=True)
class TransactionsResult:
    """Transactions payload."""

    account_id: str
    transactions: List[IncomingTransaction]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransactionsResult":
        data = _as_dict(data, "transactions payload")
        if "account_id" not in data or "transactions" not in data:
            raise ProtocolError("invalid transactions payload", code="INVALID_PAYLOAD", data=data)
        items = data["transactions"]
        if not isinstance(items, list):
            raise ProtocolError("transactions must be an array", code="INVALID_PAYLOAD", data=items)
        return cls(
            account_id=str(data["account_id"]),
            transactions=[IncomingTransaction.from_dict(_as_dict(item, "transaction")) for item in items],
        )