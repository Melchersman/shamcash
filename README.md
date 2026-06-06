# shamcash

Python client for the ShamCash API.

The package provides sync and async clients for reading linked accounts, balances, and incoming transactions from the ShamCash public API.

## Installation

```bash
pip install shamcash
```

QR code generation is optional:

```bash
pip install "shamcash[qr]"
```

## Quick start

```python
from shamcash import ShamCashAPISync

with ShamCashAPISync(api_token="...") as client:
    accounts = client.list_accounts()
    account = accounts[0]

    balances = client.get_balances(account.id)
    transactions = client.list_transactions(account.id, limit=20)
```

## Async client

```python
import asyncio

from shamcash import ShamCashAPI


async def main() -> None:
    async with ShamCashAPI(api_token="...") as client:
        accounts = await client.list_accounts()
        account = accounts[0]

        balances = await client.get_balances(account.id)
        transactions = await client.list_transactions(account.id, limit=20)


asyncio.run(main())
```

## Sync client

```python
from shamcash import ShamCashAPISync

with ShamCashAPISync(api_token="...") as client:
    accounts = client.list_accounts()
    account = accounts[0]

    balances = client.get_balances(account.id)
    transactions = client.list_transactions(account.id, limit=20)
```

## Accounts

```python
accounts = client.list_accounts()

for account in accounts:
    print(account.id)
    print(account.name)
    print(account.phone)
    print(account.status)
```

Fetch a single linked account by ID:

```python
account = client.get_account("account_id")
```

Use this when you already know the account ID and do not need the full list from `list_accounts()`.

## Balances

```python
balances = client.get_balances(account_id="account_id")

for row in balances.balances:
    print(row.currency.code)
    print(row.available)
    print(row.blocked)
```

If the API token has exactly one linked account, `account_id` can be omitted:

```python
balances = client.get_balances()
```

Money values are returned as `Decimal`.

## Transactions

```python
transactions = client.list_transactions(
    account_id="account_id",
    limit=20,
)

for tx in transactions.transactions:
    print(tx.transaction_id)
    print(tx.amount)
    print(tx.currency.code)
    print(tx.occurred_at)
    print(tx.sender_name)
    print(tx.note)
```

Available filters:

```python
transactions = client.list_transactions(
    account_id="account_id",
    start_at="2026-01-01T00:00:00",
    end_at="2026-01-31T23:59:59",
    transaction_ids=[184627893, 184627894],
    coin_id=1,
    limit=50,
)
```

You can fetch one transaction by ID:

```python
transaction = client.get_transaction(184627893)
```

Or with an account ID:

```python
transaction = client.get_transaction("account_id", 184627893)
```

The method returns `None` when the transaction is not found.

## QR code generation

Install the QR extra first:

```bash
pip install "shamcash[qr]"
```

The default style uses ShamCash brand colors, a logo tab above the QR card, square modules with thin borders, and an optional caption below the card. The packaged logo is used automatically.

Generate a QR code from an account:

```python
from shamcash import ShamCashAPISync

with ShamCashAPISync(api_token="...") as client:
    account = client.list_accounts()[0]

    account.create_qr_code(
        "receiving-address.png",
        size=1024,
        caption="Pay to Melchersman",
    )
```

You can also generate a QR code directly from a payload:

```python
from shamcash.qr import create_qr_code

create_qr_code(
    "SC_ADDRESS_OR_QR_PAYLOAD",
    "qr.png",
    caption="ShamCash payment address",
)
```

Optional styling parameters include `foreground`, `background`, `caption_color`, `logo_path`, `logo_enabled`, and `module_border_width`.

Pass an SVG path to `logo_path` when `cairosvg` is installed. Otherwise use a PNG logo or rely on the packaged default logo.

`create_qr_code()` returns a PIL Image. If `path` is provided, the image is saved.

## Raw API envelopes

Use `fetch_json_envelope()` when you need the original API envelope instead of typed models:

```python
envelope = client.fetch_json_envelope("GET", "/accounts")
```

The returned value is the decoded JSON object returned by the API.

## Errors

API errors are mapped to typed exceptions.

Common exceptions include:

* `AuthInvalidError`
* `AccountNotFoundError`
* `SubscriptionUnavailableError`
* `RateLimitExceededError`
* `NetworkError`
* `RequestTimeoutError`
* `ProtocolError`

Transport failures raise `NetworkError`.

Timeouts raise `RequestTimeoutError`.

Invalid JSON responses or unexpected response shapes raise `ProtocolError`.

## Main methods

### Sync

```python
client.list_accounts()
client.get_account(account_id)
client.get_balances(account_id=None)
client.list_transactions(
    account_id=None,
    *,
    start_at=None,
    end_at=None,
    transaction_ids=None,
    coin_id=None,
    limit=None,
)
client.get_transaction(account_id, transaction_id)
client.get_transaction(transaction_id)
client.fetch_json_envelope(method, path, params=None)
```

### Async

```python
await client.list_accounts()
await client.get_account(account_id)
await client.get_balances(account_id=None)
await client.list_transactions(
    account_id=None,
    start_at=None,
    end_at=None,
    transaction_ids=None,
    coin_id=None,
    limit=None,
)
await client.get_transaction(account_id, transaction_id)
await client.get_transaction(transaction_id)
await client.fetch_json_envelope(method, path, params=None)
```

## Models

The package exposes typed dataclasses for API responses.

Main models:

* `Account`
* `Currency`
* `BalanceRow`
* `BalancesResult`
* `IncomingTransaction`
* `TransactionsResult`

`Account` includes:

* `id`
* `name`
* `email`
* `phone`
* `status`
* `subscription_expires_at`
* `address`
* `qr_payload`

`IncomingTransaction` includes:

* `transaction_id`
* `amount`
* `currency`
* `occurred_at`
* `receiver_name`
* `sender_name`
* `sender_address`
* `note`

## Time handling

Timestamps are returned as timezone-aware UTC `datetime` objects.

Naive ShamCash timestamps are interpreted as `Asia/Damascus` and then converted to UTC.

## Compatibility

Python 3.8+ is supported.
