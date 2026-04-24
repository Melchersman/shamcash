"""
Typed models for ShamCash API ``data`` payloads.

Field names follow ``docs/ShamCash-API-Docs.md``. Monetary amounts use :class:`decimal.Decimal`.
Timestamps are parsed to timezone-aware :class:`datetime.datetime` when possible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional

from .exceptions import ProtocolError


def _dec_money(value: Any, field: str) -> Decimal:
    """Parse a JSON number for money: always via string to avoid float artifacts."""
    if value is None:
        raise ProtocolError(
            f"Missing required numeric field: {field}",
            code="INVALID_PAYLOAD",
            data={field: value},
        )
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise ProtocolError(
            f"Invalid decimal for {field}: {value!r}",
            code="INVALID_PAYLOAD",
            data={field: value},
        ) from e


def _require_dict(data: Any, what: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ProtocolError(
            f"expected JSON object for {what}, got {type(data).__name__}",
            code="INVALID_PAYLOAD",
            data=data,
        )
    return data


def _require_iso_datetime(value: Any, field: str) -> datetime:
    if value is None or value == "":
        raise ProtocolError(
            f"Missing required ISO 8601 field: {field}",
            code="INVALID_PAYLOAD",
            data={field: value},
        )
    s = str(value)
    try:
        # fromisoformat handles "+03:00" offsets (Python 3.7+)
        return datetime.fromisoformat(s)
    except ValueError as e:
        raise ProtocolError(
            f"Invalid ISO 8601 for {field}: {value!r}",
            code="INVALID_PAYLOAD",
            data={field: value},
        ) from e


def _optional_iso_datetime(value: Any, field: str) -> Optional[datetime]:
    if value is None or value == "":
        return None
    s = str(value)
    try:
        return datetime.fromisoformat(s)
    except ValueError as e:
        raise ProtocolError(
            f"Invalid ISO 8601 for {field}: {value!r}",
            code="INVALID_PAYLOAD",
            data={field: value},
        ) from e


@dataclass(frozen=True)
class Currency:
    """Currency descriptor: ``id`` (1 USD, 2 SYP, 3 EUR) and ``code``."""

    id: int
    code: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Currency:
        d = _require_dict(data, "currency")
        if "id" not in d or "code" not in d:
            raise ProtocolError(
                "currency must include id and code",
                code="INVALID_PAYLOAD",
                data=d,
            )
        try:
            return cls(id=int(d["id"]), code=str(d["code"]))
        except (TypeError, ValueError) as e:
            raise ProtocolError(
                f"Invalid currency id or code: {d!r}",
                code="INVALID_PAYLOAD",
                data=d,
            ) from e


@dataclass(frozen=True)
class Account:
    """Linked ShamCash account returned by ``GET /accounts`` and ``GET /accounts/{id}``."""

    id: str
    name: str
    email: str
    phone: str
    status: str
    subscription_expires_at: Optional[datetime]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Account:
        d = _require_dict(data, "account")
        for key in ("id", "name", "email", "phone", "status"):
            if key not in d:
                raise ProtocolError(
                    f"account object missing {key!r}",
                    code="INVALID_PAYLOAD",
                    data=d,
                )
        return cls(
            id=str(d["id"]),
            name=str(d["name"]),
            email=str(d["email"]),
            phone=str(d["phone"]),
            status=str(d["status"]),
            subscription_expires_at=_optional_iso_datetime(
                d.get("subscription_expires_at"), "subscription_expires_at"
            ),
        )


@dataclass(frozen=True)
class BalanceRow:
    """One balance row under ``BalancesResult.balances``."""

    currency: Currency
    available: Decimal
    blocked: Decimal

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalanceRow:
        d = _require_dict(data, "balance row")
        cur = d.get("currency")
        if not isinstance(cur, dict):
            raise ProtocolError(
                "balance row currency must be an object",
                code="INVALID_PAYLOAD",
                data=d,
            )
        return cls(
            currency=Currency.from_dict(cur),
            available=_dec_money(d.get("available"), "available"),
            blocked=_dec_money(d.get("blocked"), "blocked"),
        )


@dataclass(frozen=True)
class BalancesResult:
    """Payload for ``GET /balances``: ``account_id`` and per-currency balances."""

    account_id: str
    balances: List[BalanceRow]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalancesResult:
        d = _require_dict(data, "balances data")
        if "account_id" not in d:
            raise ProtocolError("balances data missing account_id", code="INVALID_PAYLOAD", data=d)
        if "balances" not in d:
            raise ProtocolError("balances data missing balances", code="INVALID_PAYLOAD", data=d)
        bal = d["balances"]
        if not isinstance(bal, list):
            raise ProtocolError(
                "balances must be a JSON array",
                code="INVALID_PAYLOAD",
                data=bal,
            )
        rows: list[BalanceRow] = []
        for i, item in enumerate(bal):
            if not isinstance(item, dict):
                raise ProtocolError(
                    f"balances[{i}] must be an object",
                    code="INVALID_PAYLOAD",
                    data=item,
                )
            rows.append(BalanceRow.from_dict(item))
        return cls(account_id=str(d["account_id"]), balances=rows)


@dataclass(frozen=True)
class IncomingTransaction:
    """One incoming transaction from ``GET /transactions``."""

    transaction_id: int
    amount: Decimal
    currency: Currency
    occurred_at: datetime
    receiver_name: str
    sender_name: str
    sender_address: str
    note: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IncomingTransaction:
        d = _require_dict(data, "transaction")
        required = (
            "transaction_id",
            "amount",
            "currency",
            "occurred_at",
            "receiver_name",
            "sender_name",
            "sender_address",
            "note",
        )
        for k in required:
            if k not in d:
                raise ProtocolError(
                    f"transaction missing {k!r}",
                    code="INVALID_PAYLOAD",
                    data=d,
                )
        cur = d.get("currency")
        if not isinstance(cur, dict):
            raise ProtocolError("transaction currency must be an object", code="INVALID_PAYLOAD", data=d)
        try:
            tx_id = int(d["transaction_id"])
        except (TypeError, ValueError) as e:
            raise ProtocolError(
                f"Invalid transaction_id: {d.get('transaction_id')!r}",
                code="INVALID_PAYLOAD",
                data=d,
            ) from e
        return cls(
            transaction_id=tx_id,
            amount=_dec_money(d.get("amount"), "amount"),
            currency=Currency.from_dict(cur),
            occurred_at=_require_iso_datetime(d.get("occurred_at"), "occurred_at"),
            receiver_name=str(d["receiver_name"]),
            sender_name=str(d["sender_name"]),
            sender_address=str(d["sender_address"]),
            note="" if d.get("note") is None else str(d["note"]),
        )


@dataclass(frozen=True)
class TransactionsResult:
    """Payload for ``GET /transactions``: ``account_id`` and matching transactions."""

    account_id: str
    transactions: List[IncomingTransaction]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransactionsResult:
        d = _require_dict(data, "transactions data")
        if "account_id" not in d:
            raise ProtocolError(
                "transactions data missing account_id",
                code="INVALID_PAYLOAD",
                data=d,
            )
        if "transactions" not in d:
            raise ProtocolError(
                "transactions data missing transactions",
                code="INVALID_PAYLOAD",
                data=d,
            )
        txs_raw = d["transactions"]
        if not isinstance(txs_raw, list):
            raise ProtocolError(
                "transactions must be a JSON array",
                code="INVALID_PAYLOAD",
                data=txs_raw,
            )
        txs: list[IncomingTransaction] = []
        for i, item in enumerate(txs_raw):
            if not isinstance(item, dict):
                raise ProtocolError(
                    f"transactions[{i}] must be an object",
                    code="INVALID_PAYLOAD",
                    data=item,
                )
            txs.append(IncomingTransaction.from_dict(item))
        return cls(account_id=str(d["account_id"]), transactions=txs)
