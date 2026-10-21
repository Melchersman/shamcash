"""HTTP client creation, context management, and the existing async session alias."""

from __future__ import annotations

import httpx
import pytest

import shamcash.client as client_module
from shamcash import ShamCashAPI, ShamCashAPISync


@pytest.mark.parametrize("cls", [ShamCashAPI, ShamCashAPISync])
@pytest.mark.parametrize("token", [None, "", "  ", False])
def test_empty_tokens_are_rejected(cls, token):
    with pytest.raises(ValueError):
        cls(token)


def test_sync_client_is_lazy_and_closes_owned_transport(monkeypatch):
    transport = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"status": "success", "data": []})
        )
    )
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return transport

    monkeypatch.setattr(client_module.httpx, "Client", factory)
    with ShamCashAPISync("token", timeout=23) as api:
        assert calls == []
        assert api.list_accounts() == []
        assert api.list_accounts() == []
        assert calls == [{"timeout": 23}]
    assert transport.is_closed


@pytest.mark.asyncio
async def test_async_client_is_lazy_and_closes_owned_transport(monkeypatch):
    transport = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"status": "success", "data": []})
        )
    )
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return transport

    monkeypatch.setattr(client_module.httpx, "AsyncClient", factory)
    async with ShamCashAPI("token", timeout=23) as api:
        assert calls == []
        assert await api.list_accounts() == []
        assert await api.list_accounts() == []
        assert calls == [{"timeout": 23}]
    assert transport.is_closed


@pytest.mark.asyncio
async def test_existing_session_alias_is_not_closed_and_conflicts_are_rejected():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"status": "success", "data": []})
        )
    ) as transport:
        async with ShamCashAPI("token", session=transport) as api:
            assert await api.list_accounts() == []
        assert not transport.is_closed
        with pytest.raises(ValueError, match="not both"):
            ShamCashAPI("token", client=transport, session=transport)
