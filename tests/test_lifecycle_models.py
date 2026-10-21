"""Parsing prices, dates, and state-specific lifecycle response fields."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import timezone
from decimal import Decimal

import pytest

from shamcash import (
    Account,
    LinkSession,
    Plan,
    ProtocolError,
    SubscriptionReceipt,
    SubscriptionSettings,
)
from lifecycle_payloads import (
    ACCOUNT,
    CREATED,
    PENDING,
    PLAN,
    RECEIPT,
    SETTINGS,
    SUCCESS,
)


@pytest.mark.parametrize(
    "model,payload",
    [
        (Plan, PLAN),
        (LinkSession, CREATED),
        (SubscriptionReceipt, RECEIPT),
        (SubscriptionSettings, SETTINGS),
    ],
)
@pytest.mark.parametrize("value", [None, [], "text", True, 2])
def test_models_require_objects(model, payload, value):
    with pytest.raises(ProtocolError):
        model.from_dict(value)


@pytest.mark.parametrize("field", ["price_usd", "base_price_usd", "compare_price_usd"])
@pytest.mark.parametrize(
    "value", ["NaN", "sNaN", "Infinity", "-Infinity", "-0.01", True, "money", {}, []]
)
def test_plan_rejects_invalid_prices(field, value):
    with pytest.raises(ProtocolError):
        Plan.from_dict(dict(PLAN, **{field: value}))


@pytest.mark.parametrize(
    "field", ["charged_usd", "price_usd", "wallet_balance_usd", "base_price_usd"]
)
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", True, "bad"])
def test_receipt_rejects_invalid_prices(field, value):
    with pytest.raises(ProtocolError):
        SubscriptionReceipt.from_dict(dict(RECEIPT, **{field: value}))


@pytest.mark.parametrize(
    "model,payload", [(Plan, PLAN), (SubscriptionReceipt, RECEIPT)]
)
@pytest.mark.parametrize("value", [-1, 100.01, "NaN", "Infinity", None, True])
def test_discount_bounds(model, payload, value):
    with pytest.raises(ProtocolError):
        model.from_dict(dict(payload, discount_percent=value))


@pytest.mark.parametrize("value", [0, 25, "12.50", 100])
def test_discount_is_decimal_and_can_be_free(value):
    plan = Plan.from_dict(dict(PLAN, discount_percent=value, price_usd="0"))
    assert plan.discount_percent == Decimal(str(value))
    assert plan.price_usd == 0


@pytest.mark.parametrize(
    "model,payload,field",
    [
        (Plan, PLAN, "duration_days"),
        (SubscriptionReceipt, RECEIPT, "duration_days"),
        (SubscriptionReceipt, RECEIPT, "periods"),
        (LinkSession, PENDING, "poll_after_seconds"),
    ],
)
@pytest.mark.parametrize("value", [0, -1, True, 1.5, "3"])
def test_positive_integer_fields(model, payload, field, value):
    with pytest.raises(ProtocolError):
        model.from_dict(dict(payload, **{field: value}))


@pytest.mark.parametrize(
    "model,payload", [(LinkSession, PENDING), (SubscriptionReceipt, RECEIPT)]
)
@pytest.mark.parametrize("value", [-1, True, 1.5, "3", None])
def test_remaining_seconds_is_nonnegative_integer(model, payload, value):
    with pytest.raises(ProtocolError):
        model.from_dict(dict(payload, remaining_seconds=value))


@pytest.mark.parametrize(
    "model,payload,field",
    [
        (LinkSession, PENDING, "approval_received"),
        (SubscriptionReceipt, RECEIPT, "auto_renew"),
        (SubscriptionSettings, SETTINGS, "auto_renew"),
        (Account, ACCOUNT, "auto_renew"),
    ],
)
@pytest.mark.parametrize("value", [0, 1, "false", [], {}])
def test_boolean_fields_are_strict(model, payload, field, value):
    with pytest.raises(ProtocolError):
        model.from_dict(dict(payload, **{field: value}))


@pytest.mark.parametrize(
    "model,payload,field",
    [
        (Plan, PLAN, "id"),
        (Plan, PLAN, "name"),
        (Plan, PLAN, "code"),
        (LinkSession, PENDING, "link_session_id"),
        (SubscriptionReceipt, RECEIPT, "subscription_id"),
        (SubscriptionReceipt, RECEIPT, "plan_id"),
        (SubscriptionSettings, SETTINGS, "account_id"),
    ],
)
@pytest.mark.parametrize("value", [None, "", " ", True, 3])
def test_required_string_fields(model, payload, field, value):
    with pytest.raises(ProtocolError):
        model.from_dict(dict(payload, **{field: value}))


@pytest.mark.parametrize("state", ["linked", "unknown", "", None, 1])
def test_unknown_link_state_is_not_treated_as_pending(state):
    with pytest.raises(ProtocolError):
        LinkSession.from_dict(dict(PENDING, state=state))


@pytest.mark.parametrize(
    "field,value",
    [("account", None), ("account", {}), ("account_id", None), ("account_id", "other")],
)
def test_link_success_requires_matching_account(field, value):
    with pytest.raises(ProtocolError):
        LinkSession.from_dict(dict(SUCCESS, **{field: value}))


def test_receipt_rejects_account_mismatch():
    with pytest.raises(ProtocolError):
        SubscriptionReceipt.from_dict(dict(RECEIPT, account_id="other"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("qr_payload", []),
        ("qr_payload", "login-text"),
        ("qr_text", {}),
        ("qr_image", True),
        ("expires_at", "not-a-date"),
        ("account_id", True),
    ],
)
def test_invalid_optional_session_fields(field, value):
    with pytest.raises(ProtocolError):
        LinkSession.from_dict(dict(CREATED, **{field: value}))


def test_old_plan_and_account_payloads_remain_usable():
    plan = Plan.from_dict(
        {
            k: v
            for k, v in PLAN.items()
            if k not in {"base_price_usd", "discount_percent", "compare_price_usd"}
        }
    )
    account = Account.from_dict(
        {
            k: v
            for k, v in ACCOUNT.items()
            if k not in {"auto_renew", "subscription_type", "provider_session_status"}
        }
    )
    assert plan.discount_percent == 0 and plan.base_price_usd is None
    assert account.auto_renew is None and account.subscription_type is None


def test_exact_money_and_utc_dates():
    receipt = SubscriptionReceipt.from_dict(
        dict(RECEIPT, charged_usd="0.12345678", remaining_seconds=0)
    )
    assert receipt.charged_usd == Decimal("0.12345678")
    assert receipt.subscription_expires_at.tzinfo is timezone.utc
    assert receipt.account.subscription_expires_at == receipt.subscription_expires_at


@pytest.mark.parametrize(
    "model,payload",
    [
        (Plan, PLAN),
        (LinkSession, CREATED),
        (SubscriptionReceipt, RECEIPT),
        (SubscriptionSettings, SETTINGS),
    ],
)
def test_unknown_fields_are_forward_compatible_and_models_are_frozen(model, payload):
    original = deepcopy(payload)
    result = model.from_dict(dict(payload, future_field={"nested": True}))
    assert payload == original
    field = next(iter(result.__dataclass_fields__))
    with pytest.raises(FrozenInstanceError):
        setattr(result, field, "changed")


@pytest.mark.parametrize(
    "model,payload,fields",
    [
        (Plan, PLAN, ["id", "code", "name", "price_usd", "duration_days"]),
        (
            LinkSession,
            PENDING,
            ["link_session_id", "state", "remaining_seconds", "approval_received"],
        ),
        (
            SubscriptionReceipt,
            RECEIPT,
            [
                "subscription_id",
                "account_id",
                "plan_id",
                "account",
                "periods",
                "duration_days",
                "price_usd",
                "charged_usd",
                "wallet_balance_usd",
                "subscription_expires_at",
                "remaining_seconds",
                "auto_renew",
            ],
        ),
    ],
)
def test_missing_required_fields_do_not_become_zero_or_empty(model, payload, fields):
    for field in fields:
        data = dict(payload)
        del data[field]
        with pytest.raises(ProtocolError):
            model.from_dict(data)
