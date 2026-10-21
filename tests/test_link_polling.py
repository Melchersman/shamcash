"""Polling uses one request at a time and honors server pacing and local deadlines."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

import shamcash.client as client_module
from shamcash import LinkExpiredError, LinkFailedError, RequestTimeoutError
from lifecycle_payloads import PENDING, SUCCESS
from test_lifecycle_http import sdk


class Clock:
    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    async def async_sleep(self, seconds):
        self.sleep(seconds)


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(
        client_module,
        "time",
        SimpleNamespace(monotonic=clock.monotonic, sleep=clock.sleep),
    )
    monkeypatch.setattr(
        client_module, "asyncio", SimpleNamespace(sleep=clock.async_sleep)
    )
    return clock


@pytest.mark.parametrize(
    "interval,server,expected", [(1, 3, 3), (8, 3, 8), (0.5, None, 0.5)]
)
async def test_server_and_caller_poll_intervals(sdk, clock, interval, server, expected):
    sdk.responses = [dict(PENDING, poll_after_seconds=server), SUCCESS]
    result = await sdk.call(
        "wait_for_link", "link_1", timeout=20, poll_interval=interval
    )
    assert result.state == "success"
    assert clock.sleeps == [expected]
    assert len(sdk.requests) == 2
    assert sdk.requests[0].extensions["timeout"]["read"] == 20
    assert sdk.requests[1].extensions["timeout"]["read"] == 20 - expected


async def test_deadline_bounds_sleep_and_each_request_timeout(sdk, clock):
    sdk.responses = [PENDING, PENDING]
    with pytest.raises(RequestTimeoutError) as error:
        await sdk.call("wait_for_link", "link_1", timeout=5, poll_interval=1)
    assert clock.sleeps == [3, 2]
    assert [r.extensions["timeout"]["read"] for r in sdk.requests] == [5, 2]
    assert error.value.data == {"link_session_id": "link_1"}


async def test_pending_request_time_counts_towards_deadline(sdk, clock):
    def slow_response(request):
        clock.now += 6
        from lifecycle_payloads import envelope

        return httpx.Response(200, json=envelope(PENDING))

    sdk.responses = [slow_response]
    with pytest.raises(RequestTimeoutError):
        await sdk.call("wait_for_link", "link_1", timeout=5)
    assert len(sdk.requests) == 1 and clock.sleeps == []


async def test_poll_timeout_allows_backend_long_poll(sdk, clock):
    sdk.responses = [SUCCESS]
    await sdk.call("wait_for_link", "link_1")
    assert sdk.requests[0].extensions["timeout"]["read"] == 120
    assert clock.sleeps == []


@pytest.mark.parametrize(
    "state,exception,status",
    [("expired", LinkExpiredError, 410), ("failed", LinkFailedError, 400)],
)
@pytest.mark.parametrize("as_error", [False, True])
async def test_terminal_states_stop_immediately(
    sdk, clock, state, exception, status, as_error
):
    if as_error:
        sdk.responses = [
            lambda req: httpx.Response(
                status,
                json={
                    "status": "error",
                    "code": "LINK_" + state.upper(),
                    "data": {"state": state},
                },
            )
        ]
    else:
        sdk.responses = [dict(PENDING, state=state)]
    with pytest.raises(exception):
        await sdk.call("wait_for_link", "link_1")
    assert len(sdk.requests) == 1 and clock.sleeps == []


async def test_transport_timeout_is_not_session_expiry(sdk, clock):
    sdk.responses = [httpx.ReadTimeout("upstream wait exceeded")]
    with pytest.raises(RequestTimeoutError):
        await sdk.call("wait_for_link", "link_1")
    assert len(sdk.requests) == 1 and clock.sleeps == []


async def test_async_cancellation_is_not_wrapped(sdk, clock):
    if not sdk.asynchronous:
        pytest.skip("Cancellation applies to the async client")

    def cancelled(request):
        raise asyncio.CancelledError()

    sdk.responses = [cancelled]
    with pytest.raises(asyncio.CancelledError):
        await sdk.call("wait_for_link", "link_1")
    assert len(sdk.requests) == 1 and clock.sleeps == []
