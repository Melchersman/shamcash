"""API response fixtures shared by the lifecycle tests."""

from copy import deepcopy

ACCOUNT = {
    "id": "acc_1",
    "name": "Example",
    "email": "wallet@example.com",
    "phone": "123",
    "status": "active",
    "address": "SHM-ADDRESS",
    "qr_payload": "SHM-ADDRESS",
    "subscription_type": "paid",
    "auto_renew": False,
    "provider_session_status": "valid",
    "subscription_expires_at": "2026-12-31T23:00:00+03:00",
}
PLAN = {
    "id": "monthly",
    "code": "monthly",
    "name": "Monthly",
    "duration_days": 30,
    "price_usd": "1.50",
    "base_price_usd": "2.00",
    "discount_percent": "25.00",
    "compare_price_usd": None,
}
PENDING = {
    "link_session_id": "link_1",
    "state": "pending",
    "expires_at": "2026-10-21T12:10:00Z",
    "remaining_seconds": 600,
    "approval_received": False,
    "poll_after_seconds": 3,
}
CREATED = dict(
    PENDING,
    qr_payload={
        "sessionId": "provider-id",
        "publicKey": "public-key",
        "infoDevice": "browser",
    },
    qr_text='{"sessionId":"provider-id","publicKey":"public-key","infoDevice":"browser"}',
    qr_image="data:image/png;base64,cG5n",
)
SUCCESS = dict(
    PENDING,
    state="success",
    approval_received=True,
    account_id="acc_1",
    account=ACCOUNT,
    poll_after_seconds=None,
)
SETTINGS = {
    "account_id": "acc_1",
    "auto_renew": False,
    "subscription_expires_at": ACCOUNT["subscription_expires_at"],
}
RECEIPT = {
    "subscription_id": "sub_1",
    "account_id": "acc_1",
    "plan_id": "monthly",
    "account": ACCOUNT,
    "periods": 3,
    "duration_days": 90,
    "price_usd": "1.50",
    "charged_usd": "4.50",
    "wallet_balance_usd": "15.50",
    "subscription_expires_at": ACCOUNT["subscription_expires_at"],
    "remaining_seconds": 7776000,
    "auto_renew": False,
    "base_price_usd": "2",
    "discount_percent": "25",
}
# A complete 1x1 PNG, independent of optional QR dependencies.
import base64

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII="
)


def envelope(data):
    return {
        "status": "success",
        "code": "SUCCESS",
        "message": "ok",
        "data": deepcopy(data),
    }
