"""HTTP client behavior with mocked responses (no live API)."""

from __future__ import annotations

import re

import pytest
from aioresponses import aioresponses

from shamcash import ShamCashAPI
from shamcash.exceptions import AuthInvalidError, ProtocolError

_API = "https://api.test.local/v1"


@pytest.mark.asyncio
async def test_list_accounts_success_empty() -> None:
    with aioresponses() as m:
        m.get(
            f"{_API}/accounts",
            payload={
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": [],
            },
        )
        async with ShamCashAPI(api_token="tok", base_url=_API) as client:
            accounts = await client.list_accounts()
            assert accounts == []


@pytest.mark.asyncio
async def test_list_accounts_success_one() -> None:
    with aioresponses() as m:
        m.get(
            f"{_API}/accounts",
            payload={
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": [
                    {
                        "id": "acc_1",
                        "name": "a",
                        "email": "e",
                        "phone": "p",
                        "status": "active",
                        "subscription_expires_at": None,
                    }
                ],
            },
        )
        async with ShamCashAPI(api_token="tok", base_url=_API) as client:
            accounts = await client.list_accounts()
            assert len(accounts) == 1
            assert accounts[0].id == "acc_1"


@pytest.mark.asyncio
async def test_list_accounts_data_not_array_raises() -> None:
    with aioresponses() as m:
        m.get(
            f"{_API}/accounts",
            payload={
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": {},
            },
        )
        async with ShamCashAPI(api_token="tok", base_url=_API) as client:
            with pytest.raises(ProtocolError, match="JSON array"):
                await client.list_accounts()


@pytest.mark.asyncio
async def test_error_envelope_maps_to_exception() -> None:
    with aioresponses() as m:
        m.get(
            f"{_API}/accounts",
            payload={
                "status": "error",
                "code": "AUTH_INVALID",
                "message": "bad token",
                "data": None,
            },
        )
        async with ShamCashAPI(api_token="tok", base_url=_API) as client:
            with pytest.raises(AuthInvalidError) as ei:
                await client.list_accounts()
            assert ei.value.http_status == 200


@pytest.mark.asyncio
async def test_get_balances() -> None:
    with aioresponses() as m:
        m.get(
            re.compile(rf"^{re.escape(_API)}/balances\?account_id=acc_1"),
            payload={
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": {
                    "account_id": "acc_1",
                    "balances": [
                        {"currency": {"id": 1, "code": "USD"}, "available": None, "blocked": None}
                    ],
                },
            },
        )
        async with ShamCashAPI(api_token="tok", base_url=_API) as client:
            bal = await client.get_balances("acc_1")
            assert bal.account_id == "acc_1"
            assert len(bal.balances) == 1


@pytest.mark.asyncio
async def test_fetch_json_envelope_does_not_raise_on_error_status() -> None:
    with aioresponses() as m:
        m.get(
            f"{_API}/accounts",
            payload={
                "status": "error",
                "code": "AUTH_INVALID",
                "message": "x",
                "data": None,
            },
        )
        async with ShamCashAPI(api_token="tok", base_url=_API) as client:
            env = await client.fetch_json_envelope("GET", "/accounts")
            assert env["status"] == "error"
            assert env["code"] == "AUTH_INVALID"


