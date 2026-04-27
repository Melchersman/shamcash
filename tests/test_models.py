"""Strict model parsing (no network)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo

import pytest

from shamcash.exceptions import ProtocolError
from shamcash.models import (
    Account,
    BalanceRow,
    BalancesResult,
    Currency,
    IncomingTransaction,
    TransactionsResult,
)


def test_balance_row_omitted_amounts_are_zero() -> None:
    row = BalanceRow.from_dict({"currency": {"id": 1, "code": "USD"}})
    assert row.available == Decimal("0")
    assert row.blocked == Decimal("0")


def test_balance_row_numeric_strings() -> None:
    row = BalanceRow.from_dict(
        {"currency": {"id": 2, "code": "SYP"}, "available": "1.5", "blocked": "0"}
    )
    assert row.available == Decimal("1.5")
    assert row.blocked == Decimal("0")


def test_balance_row_invalid_decimal() -> None:
    with pytest.raises(ProtocolError, match="invalid decimal"):
        BalanceRow.from_dict(
            {"currency": {"id": 1, "code": "USD"}, "available": "not-a-number"}
        )


def test_currency_requires_id_and_code() -> None:
    with pytest.raises(ProtocolError):
        Currency.from_dict({"id": 1})


def test_account_parses_subscription_datetime() -> None:
    acc = Account.from_dict(
        {
            "id": "acc_x",
            "name": "n",
            "email": "e",
            "phone": "p",
            "status": "active",
            "subscription_expires_at": "2026-05-23T10:35:03+03:00",
        }
    )
    assert acc.subscription_expires_at is not None
    assert acc.subscription_expires_at.tzinfo == timezone.utc
    assert acc.subscription_expires_at.isoformat() == "2026-05-23T07:35:03+00:00"


def test_account_naive_subscription_datetime_assumes_damascus() -> None:
    acc = Account.from_dict(
        {
            "id": "acc_x",
            "name": "n",
            "email": "e",
            "phone": "p",
            "status": "active",
            "subscription_expires_at": "2026-04-27 16:29:47",
        }
    )
    assert acc.subscription_expires_at is not None
    expected = datetime(
        2026, 4, 27, 16, 29, 47, tzinfo=ZoneInfo("Asia/Damascus")
    ).astimezone(timezone.utc).isoformat()
    assert acc.subscription_expires_at.isoformat() == expected


def test_incoming_transaction_optional_strings_and_amount() -> None:
    tx = IncomingTransaction.from_dict(
        {
            "transaction_id": 99,
            "currency": {"id": 1, "code": "USD"},
            "occurred_at": "2026-04-16T01:22:21+03:00",
        }
    )
    assert tx.amount == Decimal("0")
    assert tx.receiver_name == ""
    assert tx.note == ""
    assert tx.occurred_at.tzinfo == timezone.utc
    assert tx.occurred_at.isoformat() == "2026-04-15T22:22:21+00:00"


def test_transactions_result_empty_list() -> None:
    tr = TransactionsResult.from_dict(
        {"account_id": "acc_x", "transactions": []}
    )
    assert tr.account_id == "acc_x"
    assert tr.transactions == []


def test_balances_result_one_row() -> None:
    br = BalancesResult.from_dict(
        {
            "account_id": "acc_x",
            "balances": [
                {
                    "currency": {"id": 1, "code": "USD"},
                    "available": 0.1,
                    "blocked": 0,
                }
            ],
        }
    )
    assert br.balances[0].available == Decimal("0.1")
