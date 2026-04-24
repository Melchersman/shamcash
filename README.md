# shamcash

Python client for the [ShamCash HTTP API](https://api.shamcash-api.com/v1) (accounts linked on [shamcash-api.com](https://shamcash-api.com)).

## Installation

```bash
pip install shamcash
```

## Usage

### Async

```python
import asyncio
from shamcash import ShamCashAPI

async def main():
    async with ShamCashAPI(api_token="your_token") as client:
        accounts = await client.list_accounts()
        acc_id = accounts[0].id

        one = await client.get_account(acc_id)
        balances = await client.get_balances(acc_id)

        txs = await client.list_transactions(
            acc_id,
            start_at="2026-01-01",
            end_at="2026-12-31",
            coin_id=1,
            limit=50,
        )

        single = await client.get_transaction(acc_id, 184627893)

asyncio.run(main())
```

### Sync

```python
from shamcash import ShamCashAPISync

with ShamCashAPISync(api_token="your_token") as client:
    accounts = client.list_accounts()
    balances = client.get_balances(accounts[0].id)
    txs = client.list_transactions(accounts[0].id, limit=20)
```

### Filters (`GET /transactions`)

Optional keyword arguments on `list_transactions` / `list_transactions` (sync):

| Parameter | Description |
|-----------|-------------|
| `start_at` | Inclusive lower bound (`YYYY-MM-DD` or datetime; Asia/Damascus if no offset) |
| `end_at` | Inclusive upper bound |
| `transaction_ids` | Comma-separated string, one `int`, or sequence of ids |
| `coin_id` | `1` USD, `2` SYP, `3` EUR |
| `limit` | Max rows (server default 20; server may cap e.g. 200) |

Use `get_transaction(account_id, transaction_id)` to resolve a single incoming transfer by numeric id (uses the `transaction_ids` filter).

## API

### ShamCashAPI / ShamCashAPISync

| Method | Returns | Description |
|--------|---------|-------------|
| `list_accounts()` | `List[Account]` | All linked accounts |
| `get_account(account_id)` | `Account` | One account by id |
| `get_balances(account_id)` | `BalancesResult` | Per-currency balances |
| `list_transactions(account_id, **filters)` | `TransactionsResult` | Incoming transactions |
| `get_transaction(account_id, transaction_id)` | `IncomingTransaction \| None` | One transaction by id |
| `fetch_json_envelope(method, path, params=...)` | `dict` | Full JSON object (`status`, `code`, `message`, `data`); no exception on `status: "error"` |

### Models

- **Money:** `BalanceRow.available`, `BalanceRow.blocked`, and `IncomingTransaction.amount` are `Decimal` (parsed via string to avoid float rounding).
- **Time:** `Account.subscription_expires_at` and `IncomingTransaction.occurred_at` are timezone-aware `datetime` objects (ISO 8601 from the API). Raw strings are not kept on the models.

### Error handling

- API business errors: envelope `code` → typed subclasses of `ShamCashAPIError` (e.g. `AuthInvalidError`, `AccountNotFoundError`, `RateLimitExceededError`). Each carries `http_status` when available; rate limits may set `retry_after` (seconds) from the `Retry-After` header.
- **Transport** problems → `NetworkError` (e.g. connection failures).
- **Timeouts** (total request time) → `RequestTimeoutError` (`code="TIMEOUT"`).
- **Malformed JSON or shapes that do not match the documented schema** → `ProtocolError` (`code="INVALID_PAYLOAD"`). The high-level methods do not return empty lists/objects to mask server drift; they raise instead.

For debugging or custom handling, `fetch_json_envelope(...)` returns the parsed top-level object even when `status` is `"error"`, and does not map codes to exceptions.

## Rate limits

Per linked account: **6 requests per minute** for `GET /accounts/{id}`, `GET /balances`, and `GET /transactions` (see API documentation).

## Development & testing

```bash
cd shamcash
python -m pip install -e ".[dev]"
# Fast tests (no live API):
pytest -m "not integration" -v
# Optional: put SHAMCASH_API_TOKEN in a local `.env` file at the repo root (never commit it).
# Full suite including live API:
pytest -v
```

**Do not** commit `.env` or paste API tokens into the repository. On GitHub, use **Settings → Secrets and variables → Actions** for `PYPI_API_TOKEN` and `SHAMCASH_API_TOKEN`.

## Releasing (maintainers)

PyPI uploads run only after **tests pass** (unit/mocked tests plus **integration** tests against the live API).

1. Bump `version` in `pyproject.toml` and `__version__` in `shamcash/__init__.py` (match the tag without the leading `v`).
2. Commit and push to your default branch.
3. Push a tag: e.g. `git tag v1.1.2` then `git push origin v1.1.2`.

**Repository secrets (Actions):**

- **`PYPI_API_TOKEN`** — required to upload to PyPI.
- **`SHAMCASH_API_TOKEN`** — required so the publish workflow can run live API smoke tests before upload.

Every push to `master` / `main` also runs **CI** (unit + mocked tests only).

## License

MIT
