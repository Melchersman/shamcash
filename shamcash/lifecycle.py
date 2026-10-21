"""Linking and subscription response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from .exceptions import ProtocolError
from .models import Account, _as_dict, _decimal, _optional_datetime, _required_datetime


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"missing or invalid {key}", code="INVALID_PAYLOAD")
    return value


def _int(data: dict[str, Any], key: str, minimum: int = 0) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ProtocolError(f"invalid integer for {key}", code="INVALID_PAYLOAD")
    return value


def _bool(data: dict[str, Any], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ProtocolError(f"invalid boolean for {key}", code="INVALID_PAYLOAD")
    return value


def _money(data: dict[str, Any], key: str) -> Decimal:
    value = _decimal(data.get(key), key)
    if not value.is_finite() or value < 0:
        raise ProtocolError(f"invalid amount for {key}", code="INVALID_PAYLOAD")
    return value


def _discount(data: dict[str, Any]) -> Decimal:
    value = _money(
        {"discount_percent": data.get("discount_percent", 0)}, "discount_percent"
    )
    if value > 100:
        raise ProtocolError("invalid discount_percent", code="INVALID_PAYLOAD")
    return value


@dataclass(frozen=True)
class Plan:
    id: str
    code: str
    name: str
    price_usd: Decimal
    duration_days: int
    base_price_usd: Optional[Decimal] = None
    discount_percent: Decimal = Decimal("0")
    compare_price_usd: Optional[Decimal] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        data = _as_dict(data, "plan")
        return cls(
            id=_text(data, "id"),
            code=_text(data, "code"),
            name=_text(data, "name"),
            price_usd=_money(data, "price_usd"),
            duration_days=_int(data, "duration_days", 1),
            base_price_usd=(
                _money(data, "base_price_usd")
                if data.get("base_price_usd") is not None
                else None
            ),
            discount_percent=_discount(data),
            compare_price_usd=(
                _money(data, "compare_price_usd")
                if data.get("compare_price_usd") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class LinkSession:
    link_session_id: str
    state: str
    expires_at: Optional[datetime]
    remaining_seconds: int
    approval_received: bool
    poll_after_seconds: Optional[int] = None
    account_id: Optional[str] = None
    account: Optional[Account] = None
    qr_payload: Optional[dict[str, Any]] = field(default=None, repr=False)
    qr_text: Optional[str] = field(default=None, repr=False)
    qr_image: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LinkSession":
        data = _as_dict(data, "link session")
        state = _text(data, "state")
        if state not in {"pending", "success", "expired", "failed"}:
            raise ProtocolError("invalid linking state", code="INVALID_PAYLOAD")
        account = (
            Account.from_dict(_as_dict(data["account"], "account"))
            if data.get("account") is not None
            else None
        )
        account_id = data.get("account_id")
        if account_id is not None and (
            not isinstance(account_id, str) or not account_id
        ):
            raise ProtocolError("invalid account_id", code="INVALID_PAYLOAD")
        if state == "success" and (account is None or account.id != account_id):
            raise ProtocolError(
                "successful link must include the matching account",
                code="INVALID_PAYLOAD",
            )
        payload = data.get("qr_payload")
        if payload is not None:
            payload = _as_dict(payload, "qr_payload")
        for field in ("qr_text", "qr_image"):
            if data.get(field) is not None and not isinstance(data[field], str):
                raise ProtocolError(f"invalid {field}", code="INVALID_PAYLOAD")
        return cls(
            link_session_id=_text(data, "link_session_id"),
            state=state,
            expires_at=_optional_datetime(data.get("expires_at"), "expires_at"),
            remaining_seconds=_int(data, "remaining_seconds"),
            approval_received=_bool(data, "approval_received"),
            poll_after_seconds=(
                _int(data, "poll_after_seconds", 1)
                if data.get("poll_after_seconds") is not None
                else None
            ),
            account_id=account_id,
            account=account,
            qr_payload=payload,
            qr_text=data.get("qr_text"),
            qr_image=data.get("qr_image"),
        )


@dataclass(frozen=True)
class SubscriptionSettings:
    account_id: str
    auto_renew: bool
    subscription_expires_at: Optional[datetime]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubscriptionSettings":
        data = _as_dict(data, "subscription settings")
        return cls(
            account_id=_text(data, "account_id"),
            auto_renew=_bool(data, "auto_renew"),
            subscription_expires_at=_optional_datetime(
                data.get("subscription_expires_at"), "subscription_expires_at"
            ),
        )


@dataclass(frozen=True)
class SubscriptionReceipt:
    subscription_id: str
    account_id: str
    plan_id: str
    account: Account
    periods: int
    duration_days: int
    price_usd: Decimal
    charged_usd: Decimal
    wallet_balance_usd: Decimal
    subscription_expires_at: datetime
    remaining_seconds: int
    auto_renew: bool
    base_price_usd: Optional[Decimal] = None
    discount_percent: Decimal = Decimal("0")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubscriptionReceipt":
        data = _as_dict(data, "subscription receipt")
        account = Account.from_dict(_as_dict(data.get("account"), "account"))
        account_id = _text(data, "account_id")
        if account.id != account_id:
            raise ProtocolError(
                "receipt account_id does not match account", code="INVALID_PAYLOAD"
            )
        return cls(
            subscription_id=_text(data, "subscription_id"),
            account_id=account_id,
            plan_id=_text(data, "plan_id"),
            account=account,
            periods=_int(data, "periods", 1),
            duration_days=_int(data, "duration_days", 1),
            price_usd=_money(data, "price_usd"),
            charged_usd=_money(data, "charged_usd"),
            wallet_balance_usd=_money(data, "wallet_balance_usd"),
            subscription_expires_at=_required_datetime(
                data.get("subscription_expires_at"), "subscription_expires_at"
            ),
            remaining_seconds=_int(data, "remaining_seconds"),
            auto_renew=_bool(data, "auto_renew"),
            base_price_usd=(
                _money(data, "base_price_usd")
                if data.get("base_price_usd") is not None
                else None
            ),
            discount_percent=_discount(data),
        )
