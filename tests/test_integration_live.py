"""End-to-end flows with mocked HTTP responses."""

from __future__ import annotations

from datetime import timezone

import httpx
import pytest

from shamcash import ShamCashAPI, ShamCashAPISync

_API = "https://api.test.local/v1"


def _response(request: httpx.Request, payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload, request=request)


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/accounts") and request.method == "GET":
        return _response(
            request,
            {
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": [
                    {
                        "id": "acc_1",
                        "name": "demo",
                        "email": "demo@example.com",
                        "phone": "0999999999",
                        "status": "active",
                        "subscription_expires_at": "2026-12-31T23:59:59+03:00",
                    }
                ],
            },
        )
    if path.endswith("/accounts/acc_1") and request.method == "GET":
        return _response(
            request,
            {
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": {
                    "id": "acc_1",
                    "name": "demo",
                    "email": "demo@example.com",
                    "phone": "0999999999",
                    "status": "active",
                    "subscription_expires_at": "2026-12-31T23:59:59+03:00",
                },
            },
        )
    if path.endswith("/balances") and request.method == "GET":
        account_id = request.url.params.get("account_id")
        return _response(
            request,
            {
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": {
                    "account_id": account_id,
                    "balances": [
                        {
                            "currency": {"id": 1, "code": "USD"},
                            "available": "12.5",
                            "blocked": "0",
                        }
                    ],
                },
            },
        )
    if path.endswith("/transactions") and request.method == "GET":
        account_id = request.url.params.get("account_id")
        return _response(
            request,
            {
                "status": "success",
                "code": "SUCCESS",
                "message": "ok",
                "data": {
                    "account_id": account_id,
                    "transactions": [
                        {
                            "transaction_id": 123,
                            "amount": "3.2",
                            "currency": {"id": 1, "code": "USD"},
                            "occurred_at": "2026-04-16T01:22:21+03:00",
                            "receiver_name": "receiver",
                            "sender_name": "sender",
                            "sender_address": "sender-addr",
                            "note": "",
                        }
                    ],
                },
            },
        )
    return httpx.Response(404, json={"status": "error", "code": "NOT_FOUND", "message": "x", "data": None}, request=request)


@pytest.mark.asyncio
async def test_mocked_async_flow() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as http_client:
        async with ShamCashAPI(api_token="tok", base_url=_API, client=http_client) as client:
            accounts = await client.list_accounts()
            assert len(accounts) == 1
            account = await client.get_account(accounts[0].id)
            assert account.id == "acc_1"
            balances = await client.get_balances(account.id)
            assert balances.account_id == "acc_1"
            txs = await client.list_transactions(account.id, limit=3)
            assert txs.account_id == "acc_1"
            assert txs.transactions[0].occurred_at.tzinfo == timezone.utc
            tx = await client.get_transaction(account.id, txs.transactions[0].transaction_id)
            assert tx is not None
            assert tx.transaction_id == 123


def test_mocked_sync_flow() -> None:
    with httpx.Client(transport=httpx.MockTransport(_handler)) as http_client:
        with ShamCashAPISync(api_token="tok", base_url=_API, client=http_client) as client:
            accounts = client.list_accounts()
            assert len(accounts) == 1
            account = client.get_account(accounts[0].id)
            assert account.id == "acc_1"
            balances = client.get_balances(account.id)
            assert balances.account_id == "acc_1"
            txs = client.list_transactions(account.id, limit=3)
            assert txs.transactions[0].transaction_id == 123
            assert txs.transactions[0].occurred_at.tzinfo == timezone.utc
