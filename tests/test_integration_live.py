"""
Live API smoke tests. Marked ``integration`` — requires ``SHAMCASH_API_TOKEN``.

On GitHub Actions, add repository secret ``SHAMCASH_API_TOKEN`` (same value as local ``.env``).
Never commit real tokens to the repository.
"""

from __future__ import annotations

import os

import pytest

from shamcash import ShamCashAPI

pytestmark = pytest.mark.integration


def _token() -> str:
    return os.environ.get("SHAMCASH_API_TOKEN", "").strip()


@pytest.fixture
def require_token() -> str:
    t = _token()
    if not t:
        pytest.skip("SHAMCASH_API_TOKEN not set")
    return t


@pytest.mark.asyncio
async def test_live_list_accounts(require_token: str) -> None:
    async with ShamCashAPI(api_token=require_token) as client:
        accounts = await client.list_accounts()
        assert isinstance(accounts, list)


@pytest.mark.asyncio
async def test_live_balances_and_transactions(require_token: str) -> None:
    async with ShamCashAPI(api_token=require_token) as client:
        accounts = await client.list_accounts()
        if not accounts:
            pytest.skip("no linked accounts on this token")
        acc_id = accounts[0].id
        await client.get_account(acc_id)
        balances = await client.get_balances(acc_id)
        assert balances.account_id == acc_id
        txs = await client.list_transactions(acc_id, limit=3)
        assert txs.account_id == acc_id
        if txs.transactions:
            tid = txs.transactions[0].transaction_id
            one = await client.get_transaction(acc_id, tid)
            assert one is not None
            assert one.transaction_id == tid
