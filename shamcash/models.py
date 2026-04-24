"""
Typed models for ShamCash API ``data`` payloads.

Field names match the JSON documented in ``docs/ShamCash-API-Docs.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass(frozen=True)
class Currency:
    """Currency descriptor: ``id`` (1 USD, 2 SYP, 3 EUR) and ``code``."""

    id: int
    code: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Currency:
        return cls(id=int(data.get("id", 0)), code=str(data.get("code", "")))


@dataclass(frozen=True)
class Account:
    """Linked ShamCash account returned by ``GET /accounts`` and ``GET /accounts/{id}``."""

    id: str
    name: str
    email: str
    phone: str
    status: str
    subscription_expires_at: Optional[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Account:
        expires = data.get("subscription_expires_at")
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            email=str(data.get("email", "")),
            phone=str(data.get("phone", "")),
            status=str(data.get("status", "")),
            subscription_expires_at=str(expires) if expires is not None else None,
        )


@dataclass(frozen=True)
class BalanceRow:
    """One balance row under ``BalancesResult.balances``."""

    currency: Currency
    available: float
    blocked: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalanceRow:
        cur = data.get("currency") or {}
        if not isinstance(cur, dict):
            cur = {}
        return cls(
            currency=Currency.from_dict(cur),
            available=float(data.get("available", 0)),
            blocked=float(data.get("blocked", 0)),
        )


@dataclass(frozen=True)
class BalancesResult:
    """Payload for ``GET /balances``: ``account_id`` and per-currency balances."""

    account_id: str
    balances: List[BalanceRow]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalancesResult:
        rows = data.get("balances") or []
        if not isinstance(rows, list):
            rows = []
        return cls(
            account_id=str(data.get("account_id", "")),
            balances=[BalanceRow.from_dict(r) for r in rows if isinstance(r, dict)],
        )


@dataclass(frozen=True)
class IncomingTransaction:
    """One incoming transaction from ``GET /transactions``."""

    transaction_id: int
    amount: float
    currency: Currency
    occurred_at: str
    receiver_name: str
    sender_name: str
    sender_address: str
    note: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IncomingTransaction:
        cur = data.get("currency") or {}
        if not isinstance(cur, dict):
            cur = {}
        return cls(
            transaction_id=int(data.get("transaction_id", 0)),
            amount=float(data.get("amount", 0)),
            currency=Currency.from_dict(cur),
            occurred_at=str(data.get("occurred_at", "")),
            receiver_name=str(data.get("receiver_name", "")),
            sender_name=str(data.get("sender_name", "")),
            sender_address=str(data.get("sender_address", "")),
            note=str(data.get("note", "")),
        )


@dataclass(frozen=True)
class TransactionsResult:
    """Payload for ``GET /transactions``: ``account_id`` and matching transactions."""

    account_id: str
    transactions: List[IncomingTransaction]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransactionsResult:
        txs = data.get("transactions") or []
        if not isinstance(txs, list):
            txs = []
        return cls(
            account_id=str(data.get("account_id", "")),
            transactions=[IncomingTransaction.from_dict(t) for t in txs if isinstance(t, dict)],
        )
