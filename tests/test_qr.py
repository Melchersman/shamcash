"""QR code helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from shamcash.models import Account
from shamcash.qr import create_qr_code


def _sample_account(**overrides: object) -> Account:
    data = {
        "id": "acc_x",
        "name": "Demo Store",
        "email": "e@example.com",
        "phone": "p",
        "address": "SHC_ADDRESS",
        "qr_payload": "SHC_ADDRESS",
        "status": "active",
        "subscription_expires_at": None,
    }
    data.update(overrides)
    return Account.from_dict(data)


def test_create_qr_code_returns_rgb_image() -> None:
    pytest.importorskip("qrcode")
    pytest.importorskip("PIL")

    image = create_qr_code("payload-value", logo_enabled=False, size=360)

    assert image.size[0] == 360
    assert image.size[1] >= 360
    assert image.mode == "RGB"


def test_create_qr_code_with_caption_increases_height() -> None:
    pytest.importorskip("qrcode")
    pytest.importorskip("PIL")

    without_caption = create_qr_code("payload-value", logo_enabled=False, size=360)
    with_caption = create_qr_code(
        "payload-value",
        logo_enabled=False,
        size=360,
        caption="Pay to Demo Store",
    )

    assert with_caption.size[0] == 360
    assert with_caption.size[1] > without_caption.size[1]


def test_create_qr_code_rejects_empty_payload() -> None:
    pytest.importorskip("qrcode")

    with pytest.raises(ValueError, match="payload must be a non-empty string"):
        create_qr_code("  ")


def test_create_qr_code_rejects_low_contrast_colors() -> None:
    pytest.importorskip("qrcode")
    pytest.importorskip("PIL")

    with pytest.raises(ValueError, match="enough contrast"):
        create_qr_code(
            "payload-value",
            logo_enabled=False,
            size=360,
            foreground="#CCCCCC",
            background="#DDDDDD",
        )


def test_create_qr_code_writes_file(tmp_path: Path) -> None:
    pytest.importorskip("qrcode")
    pytest.importorskip("PIL")

    out = tmp_path / "qr.png"
    create_qr_code("payload-value", out, logo_enabled=False, size=360)

    assert out.is_file()
    assert out.stat().st_size > 0


def test_account_create_qr_code_returns_image() -> None:
    pytest.importorskip("qrcode")
    pytest.importorskip("PIL")

    image = _sample_account().create_qr_code(size=360, logo_enabled=False)

    assert image.size[0] == 360
    assert image.size[1] > 360
    assert image.mode == "RGB"


def test_account_create_qr_code_requires_payload() -> None:
    pytest.importorskip("qrcode")

    account = _sample_account(address=None, qr_payload=None)

    with pytest.raises(ValueError, match="no qr_payload or address"):
        account.create_qr_code()
