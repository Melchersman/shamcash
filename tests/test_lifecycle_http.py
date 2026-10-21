"""Wire contracts and failure handling for both client implementations."""

from __future__ import annotations

import asyncio
import inspect
import json
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio

import shamcash
from shamcash import ShamCashAPI, ShamCashAPISync
from shamcash.exceptions import (
    ERROR_MAP,
    NetworkError,
    ProtocolError,
    RequestTimeoutError,
    ShamCashAPIError,
)
from lifecycle_payloads import (
    ACCOUNT,
    CREATED,
    PENDING,
    PLAN,
    PNG,
    RECEIPT,
    SETTINGS,
    SUCCESS,
    envelope,
)

BASE = "https://api.example.test/v1"


class Harness:
    def __init__(self, asynchronous):
        self.requests = []
        self.responses = []
        self.asynchronous = asynchronous
        cls = httpx.AsyncClient if asynchronous else httpx.Client
        self.http = cls(transport=httpx.MockTransport(self.handle), timeout=19)
        cls = ShamCashAPI if asynchronous else ShamCashAPISync
        self.api = cls(" tok ", base_url=BASE + "/", client=self.http)

    def handle(self, request):
        self.requests.append(request)
        assert request.headers["Authorization"] == "Bearer tok"
        if not self.responses:
            raise AssertionError("Unexpected extra request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return response(request)
        return httpx.Response(200, json=envelope(response), request=request)

    async def call(self, name, *args, **kwargs):
        result = getattr(self.api, name)(*args, **kwargs)
        return await result if inspect.isawaitable(result) else result


@pytest_asyncio.fixture(params=[False, True], ids=["sync", "async"])
async def sdk(request):
    harness = Harness(request.param)
    yield harness
    if harness.asynchronous:
        await harness.http.aclose()
    else:
        harness.http.close()


@pytest.mark.parametrize("target", [None, "acc_1"])
async def test_create_link_session(sdk, target):
    sdk.responses = [CREATED]
    result = await sdk.call("create_link_session", target_account_id=target)
    req = sdk.requests[0]
    assert (req.method, str(req.url)) == ("POST", BASE + "/link-sessions")
    assert (
        json.loads(req.content) == {"target_account_id": target}
        if target
        else not req.content
    )
    assert result.link_session_id == "link_1"
    assert result.qr_payload["sessionId"] == "provider-id"
    assert json.loads(result.qr_text) == result.qr_payload
    assert result.qr_image.startswith("data:image/png;base64,")


@pytest.mark.parametrize("payload", [PENDING, SUCCESS])
async def test_poll_returns_timing_and_account(sdk, payload):
    sdk.responses = [payload]
    result = await sdk.call("get_link_session", "link_1", timeout=47)
    req = sdk.requests[0]
    assert (req.method, req.url.path) == ("GET", "/v1/link-sessions/link_1")
    assert req.extensions["timeout"]["read"] == 47
    assert result.state == payload["state"]
    assert result.expires_at.utcoffset().total_seconds() == 0
    if result.account:
        assert result.account.id == "acc_1"
        assert result.account.qr_payload == "SHM-ADDRESS"


async def test_login_qr_returns_exact_png_without_qr_extra(sdk):
    sdk.responses = [
        lambda req: httpx.Response(
            200, content=PNG, headers={"Content-Type": "IMAGE/PNG; charset=binary"}
        )
    ]
    assert await sdk.call("get_link_qr", "link_1") == PNG
    assert sdk.requests[0].headers["Accept"] == "image/png"
    assert sdk.requests[0].url.path == "/v1/link-sessions/link_1/qr"


async def test_plans_include_owner_price_and_duration(sdk):
    sdk.responses = [{"plans": [PLAN]}]
    plans = await sdk.call("list_plans")
    assert sdk.requests[0].url.path == "/v1/plans"
    assert plans[0].price_usd == Decimal("1.50")
    assert plans[0].base_price_usd == Decimal("2")
    assert plans[0].discount_percent == 25
    assert plans[0].duration_days == 30
    assert sdk.requests[0].extensions["timeout"]["read"] == 19


@pytest.mark.parametrize(
    "periods,plan_id", [(1, None), (3, "monthly"), (120, "monthly")]
)
async def test_subscription_body_and_key(sdk, periods, plan_id):
    payload = dict(RECEIPT, periods=periods, duration_days=periods * 30)
    sdk.responses = [payload]
    result = await sdk.call(
        "subscribe",
        "acc_1",
        idempotency_key="checkout:order-42.v1",
        plan_id=plan_id,
        periods=periods,
    )
    req = sdk.requests[0]
    assert (req.method, req.url.path) == ("POST", "/v1/accounts/acc_1/subscription")
    expected = {"periods": periods}
    if plan_id:
        expected["plan_id"] = plan_id
    assert json.loads(req.content) == expected
    assert req.headers["Idempotency-Key"] == "checkout:order-42.v1"
    assert result.charged_usd == Decimal("4.50")
    assert result.account.auto_renew is False
    assert result.subscription_expires_at.isoformat() == "2026-12-31T20:00:00+00:00"


async def test_purchase_replay_preserves_key_body_and_receipt(sdk):
    sdk.responses = [RECEIPT, RECEIPT]
    first = await sdk.call("subscribe", "acc_1", idempotency_key="order-42", periods=3)
    second = await sdk.call("subscribe", "acc_1", idempotency_key="order-42", periods=3)
    assert first == second
    assert sdk.requests[0].content == sdk.requests[1].content
    assert (
        sdk.requests[0].headers["Idempotency-Key"]
        == sdk.requests[1].headers["Idempotency-Key"]
    )


@pytest.mark.parametrize("enabled", [False, True])
async def test_explicit_auto_renew_keeps_expiry(sdk, enabled):
    sdk.responses = [dict(SETTINGS, auto_renew=enabled)]
    result = await sdk.call("set_auto_renew", "acc_1", enabled)
    req = sdk.requests[0]
    assert (req.method, req.url.path) == ("PATCH", "/v1/accounts/acc_1/subscription")
    assert json.loads(req.content) == {"auto_renew": enabled}
    assert result.auto_renew is enabled
    assert result.subscription_expires_at.isoformat() == "2026-12-31T20:00:00+00:00"


async def test_start_trial_and_delete(sdk):
    sdk.responses = [
        {"account": dict(ACCOUNT, subscription_type="trial")},
        {"account_id": "acc_1"},
    ]
    trial = await sdk.call("start_trial", "acc_1")
    assert trial.subscription_type == "trial"
    assert await sdk.call("delete_account", "acc_1") == "acc_1"
    assert [(r.method, r.url.path) for r in sdk.requests] == [
        ("POST", "/v1/accounts/acc_1/trial"),
        ("DELETE", "/v1/accounts/acc_1"),
    ]


@pytest.mark.parametrize("code", sorted(ERROR_MAP) + ["FUTURE_ERROR"])
async def test_api_errors_preserve_details_and_type(sdk, code):
    body = {
        "status": "error",
        "code": code,
        "message": "Specific explanation",
        "data": {"state": "pending", "amount": "1.5"},
    }
    sdk.responses = [
        lambda req: httpx.Response(429, json=body, headers={"Retry-After": "7"})
    ]
    with pytest.raises(ERROR_MAP.get(code, ShamCashAPIError)) as error:
        await sdk.call("list_plans")
    assert type(error.value) is ERROR_MAP.get(code, ShamCashAPIError)
    assert (
        error.value.code,
        error.value.http_status,
        error.value.data,
        error.value.message,
    ) == (code, 429, body["data"], body["message"])
    assert error.value.retry_after == (7 if code == "RATE_LIMIT_EXCEEDED" else None)


@pytest.mark.parametrize("status", [200, 403, 410])
async def test_qr_error_envelopes_are_typed(sdk, status):
    sdk.responses = [
        lambda req: httpx.Response(
            status,
            json={
                "status": "error",
                "code": "LINK_EXPIRED",
                "data": {"state": "expired"},
            },
        )
    ]
    with pytest.raises(shamcash.LinkExpiredError) as error:
        await sdk.call("get_link_qr", "link_1")
    assert error.value.http_status == status


@pytest.mark.parametrize(
    "content_type,content",
    [
        ("image/png", b""),
        ("image/png", b"\x89PNG\r\n\x1a\n"),
        ("image/png", b"not-png"),
        ("image/jpeg", PNG),
        ("text/html", b"<html>error</html>"),
        ("", PNG),
    ],
)
async def test_invalid_qr_responses(sdk, content_type, content):
    sdk.responses = [
        lambda req: httpx.Response(
            200, content=content, headers={"Content-Type": content_type}
        )
    ]
    with pytest.raises(ProtocolError):
        await sdk.call("get_link_qr", "link_1")


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"  ",
        b"<html>gateway</html>",
        b"null",
        b"[]",
        b"true",
        b"1",
        b'{"status":"success"}',
    ],
)
async def test_invalid_json_and_envelopes(sdk, content):
    sdk.responses = [lambda req: httpx.Response(200, content=content)]
    with pytest.raises(ProtocolError):
        await sdk.call("list_plans")


@pytest.mark.parametrize("status", [301, 400, 401, 429, 500, 503])
async def test_http_failure_cannot_be_a_success(sdk, status):
    sdk.responses = [
        lambda req: httpx.Response(status, json=envelope({"plans": [PLAN]}))
    ]
    with pytest.raises(ProtocolError) as error:
        await sdk.call("list_plans")
    assert error.value.http_status == status


@pytest.mark.parametrize(
    "payload", [None, [], {"plans": None}, {"plans": {}}, {"plans": [None]}]
)
async def test_invalid_plan_lists(sdk, payload):
    sdk.responses = [payload]
    with pytest.raises(ProtocolError):
        await sdk.call("list_plans")


@pytest.mark.parametrize(
    "method,args,payload",
    [
        ("get_link_session", ("link_1",), dict(PENDING, link_session_id="other")),
        (
            "subscribe",
            ("acc_1",),
            dict(RECEIPT, account_id="other", account=dict(ACCOUNT, id="other")),
        ),
        ("set_auto_renew", ("acc_1", True), dict(SETTINGS, account_id="other")),
        ("start_trial", ("acc_1",), {"account": dict(ACCOUNT, id="other")}),
        ("delete_account", ("acc_1",), {"account_id": "other"}),
        ("delete_account", ("acc_1",), {}),
    ],
)
async def test_response_cannot_refer_to_another_resource(sdk, method, args, payload):
    sdk.responses = [payload]
    kwargs = {"idempotency_key": "order-42"} if method == "subscribe" else {}
    with pytest.raises(ProtocolError):
        await sdk.call(method, *args, **kwargs)


@pytest.mark.parametrize(
    "failure,exception",
    [
        (httpx.ConnectError("offline"), NetworkError),
        (httpx.ReadTimeout("timed out"), RequestTimeoutError),
        (httpx.ConnectTimeout("timed out"), RequestTimeoutError),
    ],
)
async def test_financial_requests_are_not_retried(sdk, failure, exception):
    sdk.responses = [failure]
    with pytest.raises(exception):
        await sdk.call("subscribe", "acc_1", idempotency_key="order-42")
    assert len(sdk.requests) == 1


async def test_raw_json_supports_post_and_returns_error_body(sdk):
    body = {
        "status": "error",
        "code": "IDEMPOTENCY_KEY_REUSED",
        "data": {"existing": True},
    }
    sdk.responses = [lambda req: httpx.Response(409, json=body)]
    result = await sdk.call(
        "fetch_json_envelope",
        "POST",
        "/accounts/acc_1/subscription",
        json={"periods": 2},
        headers={"Idempotency-Key": "order-42"},
    )
    assert result == body
    assert json.loads(sdk.requests[0].content) == {"periods": 2}
    assert sdk.requests[0].headers["Idempotency-Key"] == "order-42"


async def test_injected_http_client_is_not_closed_by_sdk(sdk):
    await sdk.call("close")
    assert not sdk.http.is_closed
