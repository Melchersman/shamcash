# ShamCash API Python SDK

Python client for the [ShamCash API](https://shamcash-api.com), with sync and async clients for account linking, subscriptions, balances, and incoming transactions.

This package is maintained for **shamcash-api.com**, an independent developer platform. It is not the official ShamCash app or a library published by the ShamCash wallet operator.

[Platform](https://shamcash-api.com) · [API documentation](https://shamcash-api.com/en/docs) · [Python quick start](https://shamcash-api.com/en/python) · [PyPI package](https://pypi.org/project/shamcash/) · [Payment integration](https://shamcash-api.com/en/integration)

مكتبة بايثون لمنصة شام كاش البرمجية المستقلة، لربط الحسابات وقراءة الأرصدة والحوالات الواردة وإدارة الاشتراكات.

[دليل بايثون بالعربية](https://shamcash-api.com/python) · [الوثائق البرمجية بالعربية](https://shamcash-api.com/ar/docs) · [دليل ربط المدفوعات](https://shamcash-api.com/integration)

```bash
pip install shamcash
```

Python 3.8+ is supported. Money is returned as `Decimal`; timestamps are timezone-aware UTC `datetime` objects. Naive provider timestamps are interpreted in `Asia/Damascus` before conversion.

## Read an account

```python
from shamcash import ShamCashAPISync

with ShamCashAPISync(api_token="...") as client:
    accounts = client.list_accounts()
    account = client.get_account("account_id")
    balances = client.get_balances(account.id)
    transactions = client.list_transactions(account.id, limit=20)
```

When the token has exactly one linked account, `account_id` can be omitted from balance and transaction requests.

```python
transactions = client.list_transactions(
    account_id="account_id",
    start_at="2026-01-01T00:00:00",
    end_at="2026-01-31T23:59:59",
    transaction_ids=[184627893, 184627894],
    coin_id=1,
    limit=50,
)

for tx in transactions.transactions:
    print(tx.transaction_id, tx.amount, tx.currency.code, tx.occurred_at)

transaction = client.get_transaction("account_id", 184627893)
# With one linked account:
transaction = client.get_transaction(184627893)
```

`get_transaction()` returns `None` when the transaction is absent.

## Link accounts from your application

Enable account management for the API token in the platform before creating sessions or changing accounts and subscriptions. Reading accounts, balances, transactions, and plans does not require this permission. A token without it receives `APIManagementDisabledError`.

```python
from pathlib import Path
from shamcash import ShamCashAPISync

with ShamCashAPISync(api_token="...") as client:
    session = client.create_link_session()
    Path("link.png").write_bytes(client.get_link_qr(session.link_session_id))

    # Display link.png for the user to scan in ShamCash.
    linked = client.wait_for_link(session.link_session_id)
    account = linked.account
    print(account.id, account.name)
```

Creation returns `qr_payload`, the exact `qr_text`, and a `qr_image` PNG data URI. `get_link_qr()` downloads PNG bytes and needs no optional image dependencies. These are login credentials for the pending session; keep them private and avoid logging them.

For your own polling loop, call `get_link_session(session_id)`. A pending result includes `remaining_seconds`, `approval_received`, and `poll_after_seconds`. Keep one poll in flight per session and respect the returned interval. `wait_for_link()` handles this pacing, returns a successful `LinkSession`, and raises `LinkExpiredError` or `LinkFailedError` for terminal failures. Its default local deadline is 780 seconds, allowing approval received before QR expiry to finish during the server's completion window. A local or transport timeout raises `RequestTimeoutError`; it does not establish that the session expired.

Re-link an existing account with `create_link_session(target_account_id="account_id")`. This replaces its provider session while preserving its platform account ID and subscription. It must be approved by the same ShamCash identity.

## Plans and prepaid subscriptions

`list_plans()` returns each plan's `duration_days` and USD price for the token owner. `price_usd` includes the owner's discount; `base_price_usd` and `discount_percent` describe that discount. Prices are checked again when a purchase is made.

```python
plans = client.list_plans()
plan = plans[0]
print(plan.duration_days, plan.price_usd, plan.discount_percent)

receipt = client.subscribe(
    "account_id",
    plan_id=plan.id,
    periods=3,
    idempotency_key="checkout-order-42",
)
print(receipt.charged_usd, receipt.subscription_expires_at)
```

The same method starts or renews paid access. `periods` accepts 1–120 plan periods and charges the platform USD wallet once. A 30-day plan purchased for three periods adds 90 days after existing access, or from now if it has expired. `plan_id=None` selects the server's default paid plan.

Choose a stable key for each intentional purchase. After a timeout or uncertain response, repeat the same account, plan, periods, and key to retrieve the original receipt without another charge. Use a new key for another purchase. Changed parameters with an existing key raise `IdempotencyKeyReusedError`. The client never retries a charge automatically or creates purchase keys for you.

Receipts include `subscription_id`, the account snapshot, purchased duration, unit and total prices, wallet balance, expiry, `remaining_seconds`, and auto-renew status. A replay returns the original snapshot, including its original discount and remaining time.

```python
settings = client.set_auto_renew("account_id", False)
settings = client.set_auto_renew("account_id", True)
trial_account = client.start_trial("account_id")
deleted_id = client.delete_account("account_id")
```

Auto-renew is set explicitly and leaves prepaid expiry unchanged. Deleting removes the platform link and its subscription; it does not delete the ShamCash wallet or refund unused time. A free trial can be activated once per eligible account.

## Async client

`ShamCashAPI` has the same methods and arguments as `ShamCashAPISync`:

```python
import asyncio
from shamcash import ShamCashAPI

async def main():
    async with ShamCashAPI(api_token="...") as client:
        session = await client.create_link_session()
        png = await client.get_link_qr(session.link_session_id)
        # Display png to the user before waiting for approval.
        linked = await client.wait_for_link(session.link_session_id)
        print(linked.account_id)

asyncio.run(main())
```

Both clients accept an injected `httpx` client; the caller remains responsible for closing it. The async client's existing `session=` alias is also supported. Polling uses a per-request timeout of up to 120 seconds; ordinary requests use the configured HTTP client timeout, 30 seconds by default.

## Methods and results

| Method | Result |
| --- | --- |
| `list_accounts()` | `list[Account]` |
| `get_account(account_id)` | `Account` |
| `get_balances(account_id=None)` | `BalancesResult` |
| `list_transactions(account_id=None, ...)` | `TransactionsResult` |
| `get_transaction(account_id, transaction_id)` | `IncomingTransaction` or `None` |
| `create_link_session(target_account_id=None)` | `LinkSession` with login QR data |
| `get_link_session(session_id, timeout=120)` | `LinkSession` |
| `get_link_qr(session_id)` | PNG `bytes` |
| `wait_for_link(session_id, timeout=780, poll_interval=3)` | Successful `LinkSession` |
| `list_plans()` | `list[Plan]` |
| `subscribe(account_id, idempotency_key=..., plan_id=None, periods=1)` | `SubscriptionReceipt` |
| `set_auto_renew(account_id, enabled)` | `SubscriptionSettings` |
| `start_trial(account_id)` | `Account` |
| `delete_account(account_id)` | Deleted account ID |
| `fetch_json_envelope(method, path, params=None, json=None, headers=None)` | Original JSON envelope, including API errors |

Optional method arguments shown after the resource ID are keyword-only, except `enabled`.

## Errors

All SDK exceptions inherit from `ShamCashAPIError` and expose `code`, `message`, `data`, `http_status`, and `retry_after`. Unknown API codes retain these fields in the base exception. `RateLimitExceededError.retry_after` contains the server's delay in seconds when supplied.

| API code | Exception |
| --- | --- |
| `API_MANAGEMENT_DISABLED` | `APIManagementDisabledError` |
| `LINK_EXPIRED` | `LinkExpiredError` |
| `LINK_FAILED` | `LinkFailedError` |
| `LINK_QR_UNAVAILABLE` | `LinkQRUnavailableError` |
| `PLAN_NOT_FOUND` | `PlanNotFoundError` |
| `INSUFFICIENT_BALANCE` | `InsufficientBalanceError` |
| `TRIAL_ALREADY_USED` | `TrialAlreadyUsedError` |
| `SUBSCRIPTION_ALREADY_ACTIVE` | `SubscriptionAlreadyActiveError` |
| `IDEMPOTENCY_KEY_REQUIRED` | `IdempotencyKeyRequiredError` |
| `IDEMPOTENCY_KEY_REUSED` | `IdempotencyKeyReusedError` |
| `SHAMCASH_SESSION_EXPIRED` | `ShamCashSessionExpiredError` |
| `UPSTREAM_UNAVAILABLE` | `UpstreamUnavailableError` |

Existing authentication, account, subscription, rate-limit, and fetch exceptions remain available. Transport failures raise `NetworkError`; timeouts raise `RequestTimeoutError`. Invalid JSON or response shapes raise `ProtocolError`. Invalid local method arguments raise `ValueError` before a request is sent.

The [HTTP API reference](docs/ShamCash-API-Docs.md) lists status codes, response fields, and endpoint behavior.

## Receiving-address QR generation

Account `address` and `qr_payload` describe the receiving address. To render that QR locally, install the optional extra:

```bash
pip install "shamcash[qr]"
```

```python
account.create_qr_code("receiving-address.png", size=1024, caption="ShamCash payment address")

from shamcash import create_qr_code
image = create_qr_code("SHM-ADDRESS", "qr.png", caption="Payment address")
```

The renderer returns a PIL Image and saves it when a path is supplied. Styling options include `foreground`, `background`, `caption_color`, `logo_path`, `logo_enabled`, and `module_border_width`. SVG logos require CairoSVG; the packaged logo is included by default.

## Development

```bash
pip install -e ".[dev]"
pytest -q
python -m build
python -m twine check dist/*
```

Tests use HTTP fixtures and do not require a platform token. CI runs the suite on Python 3.8–3.14 and checks the built distribution before publishing.
