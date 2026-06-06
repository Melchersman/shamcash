"""Typed response models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, List, Optional, Union

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo  # type: ignore[import-not-found]

from .exceptions import ProtocolError


_DAMASCUS_TZ = ZoneInfo("Asia/Damascus")
_UTC = timezone.utc


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


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("empty timestamp")
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        dt = datetime.fromisoformat(text)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_DAMASCUS_TZ)
    return dt.astimezone(_UTC)


def _required_datetime(value: Any, field: str) -> datetime:
    if value in (None, ""):
        raise ProtocolError(
            f"missing timestamp field {field!r}",
            code="INVALID_PAYLOAD",
            data={field: value},
        )
    try:
        return _parse_datetime(value)
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
        return _parse_datetime(value)
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
    address: Optional[str] = None
    qr_payload: Optional[str] = None

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
            address=str(data["address"]) if data.get("address") is not None else None,
            qr_payload=str(data["qr_payload"]) if data.get("qr_payload") is not None else None,
        )

    def create_qr_code(
        self,
        path: Optional[Union[str, Path]] = None,
        *,
        size: int = 1024,
        border: int = 4,
        foreground: str = "#253C96",
        background: str = "#F1F3F7",
        canvas_background: str = "#FFFFFF",
        panel_border_color: str = "#C9D2E6",
        caption: Optional[str] = None,
        caption_color: Optional[str] = None,
        caption_font_size: Optional[int] = None,
        caption_max_lines: int = 2,
        caption_spacing: Optional[int] = None,
        logo_path: Optional[Union[str, Path]] = None,
        logo_enabled: bool = True,
        module_border_color: Optional[str] = None,
        module_border_width: int = 1,
    ) -> Any:
        """Create a QR code image for this account.

        Parameters:
            path:
                Optional output path. When provided, the image is saved to this path.

            size:
                Width of the QR image area in pixels. The final image may be taller when
                a caption is used.

            border:
                QR quiet-zone size in modules. Must be at least 4 for reliable scanning.

            foreground:
                QR module color as a 6-digit hex value.

            background:
                QR panel background color as a 6-digit hex value.

            canvas_background:
                Full image background color as a 6-digit hex value.

            panel_border_color:
                Border color around the QR panel and logo tab.

            caption:
                Optional text shown below the QR panel.

            caption_color:
                Caption text color. Uses the foreground color when omitted.

            caption_font_size:
                Optional caption font size in pixels.

            caption_max_lines:
                Maximum number of caption lines.

            caption_spacing:
                Space between the QR panel and the caption in pixels.

            logo_path:
                Optional path to a PNG, JPG, WEBP, or SVG logo. When omitted, the packaged
                ShamCash logo is used if available.

            logo_enabled:
                Whether to show the logo tab above the QR panel.

            module_border_color:
                Optional color for the thin lines between QR modules. A derived color is
                used when omitted.

            module_border_width:
                Width of the thin module border lines in pixels. Use 0 to disable them.

        Returns:
            A PIL Image. If path is provided, the image is saved before returning.
        """
        payload = (self.qr_payload or self.address or "").strip()
        if not payload:
            raise ValueError("account has no qr_payload or address")

        from .qr import create_qr_code

        return create_qr_code(
            payload,
            path=path,
            size=size,
            border=border,
            foreground=foreground,
            background=background,
            canvas_background=canvas_background,
            panel_border_color=panel_border_color,
            caption=caption,
            caption_color=caption_color,
            caption_font_size=caption_font_size,
            caption_max_lines=caption_max_lines,
            caption_spacing=caption_spacing,
            logo_path=logo_path,
            logo_enabled=logo_enabled,
            module_border_color=module_border_color,
            module_border_width=module_border_width,
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
