# shamcash

Python client for the ShamCash HTTP API.

## Installation

```bash
pip install shamcash
```

## Quick start

```python
from shamcash import ShamCashAPISync

with ShamCashAPISync(api_token="...") as client:
    account = client.list_accounts()[0]
    balances = client.get_balances(account.id)
```

## Async

```python
import asyncio

from shamcash import ShamCashAPI


async def main() -> None:
    async with ShamCashAPI(api_token="...") as client:
        account = (await client.list_accounts())[0]
        balances = await client.get_balances(account.id)
        transactions = await client.list_transactions(account.id, limit=20)


asyncio.run(main())
```

## Sync

```python
from shamcash import ShamCashAPISync

with ShamCashAPISync(api_token="...") as client:
    account = client.list_accounts()[0]
    balances = client.get_balances(account.id)
    transaction = client.get_transaction(account.id, 184627893)
```

## Errors

- API envelope codes map to typed exceptions such as `AuthInvalidError`, `AccountNotFoundError`, `SubscriptionUnavailableError`, and `RateLimitExceededError`.
- Transport failures raise `NetworkError`.
- Timeouts raise `RequestTimeoutError`.
- Invalid JSON or schema mismatches raise `ProtocolError`.

## Capabilities

- `list_accounts()`
- `get_account(account_id)`
- `get_balances(account_id)`
- `list_transactions(account_id, *, start_at=None, end_at=None, transaction_ids=None, coin_id=None, limit=None)`
- `get_transaction(account_id, transaction_id)`
- `fetch_json_envelope(method, path, params=None)`

## Models and typing

- Account, balance, and transaction payloads are exposed as typed dataclasses.
- Money fields use `Decimal`.
- Timestamps use timezone-aware UTC `datetime`.
- Naive ShamCash timestamps are interpreted as `Asia/Damascus` and normalized to UTC.

## Compatibility

- Python 3.8+