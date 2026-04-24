"""HTTP client tests with `httpx.MockTransport`."""

from __future__ import annotations

from typing import Any, Callable

import httpx
import pytest

from shamcash import ShamCashAPI, ShamCashAPISync
from shamcash.exceptions import AuthInvalidError, ProtocolError, RateLimitExceededError

_API = "https://api.test.local/v1"


def _response(
    request: httpx.Request,
    body: dict[str, Any],
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(status_code, json=body, headers=headers, request=request)


@pytest.mark.asyncio
async def test_async_list_accounts_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tok"
        return _response(
            request,
            {
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

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with ShamCashAPI(api_token="tok", base_url=_API, client=http_client) as client:
            accounts = await client.list_accounts()

    assert len(accounts) == 1
    assert accounts[0].id == "acc_1"


@pytest.mark.asyncio
async def test_async_invalid_accounts_payload_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(
            request,
            {
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": {},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with ShamCashAPI(api_token="tok", base_url=_API, client=http_client) as client:
            with pytest.raises(ProtocolError, match="accounts must be an array"):
                await client.list_accounts()


@pytest.mark.asyncio
async def test_async_error_envelope_maps_to_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(
            request,
            {
                "status": "error",
                "code": "AUTH_INVALID",
                "message": "bad token",
                "data": None,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with ShamCashAPI(api_token="tok", base_url=_API, client=http_client) as client:
            with pytest.raises(AuthInvalidError) as exc_info:
                await client.list_accounts()

    assert exc_info.value.http_status == 200


@pytest.mark.asyncio
async def test_async_rate_limit_captures_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(
            request,
            {
                "status": "error",
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "slow down",
                "data": None,
            },
            status_code=429,
            headers={"Retry-After": "12"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with ShamCashAPI(api_token="tok", base_url=_API, client=http_client) as client:
            with pytest.raises(RateLimitExceededError) as exc_info:
                await client.list_accounts()

    assert exc_info.value.retry_after == 12


@pytest.mark.asyncio
async def test_async_get_balances() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["account_id"] == "acc_1"
        return _response(
            request,
            {
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": {
                    "account_id": "acc_1",
                    "balances": [
                        {
                            "currency": {"id": 1, "code": "USD"},
                            "available": None,
                            "blocked": None,
                        }
                    ],
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with ShamCashAPI(api_token="tok", base_url=_API, client=http_client) as client:
            balances = await client.get_balances("acc_1")

    assert balances.account_id == "acc_1"
    assert len(balances.balances) == 1


@pytest.mark.asyncio
async def test_async_fetch_json_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(
            request,
            {
                "status": "error",
                "code": "AUTH_INVALID",
                "message": "bad token",
                "data": None,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with ShamCashAPI(api_token="tok", base_url=_API, client=http_client) as client:
            envelope = await client.fetch_json_envelope("GET", "/accounts")

    assert envelope["status"] == "error"
    assert envelope["code"] == "AUTH_INVALID"


def test_sync_list_accounts_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(
            request,
            {
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": [],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with ShamCashAPISync(api_token="tok", base_url=_API, client=http_client) as client:
            assert client.list_accounts() == []


def test_sync_get_transaction_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(
            request,
            {
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": {
                    "account_id": "acc_1",
                    "transactions": [],
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with ShamCashAPISync(api_token="tok", base_url=_API, client=http_client) as client:
            assert client.get_transaction("acc_1", 1) is None


