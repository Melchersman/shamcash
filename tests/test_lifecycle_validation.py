"""Reject invalid purchase and session inputs before sending a request."""

from __future__ import annotations

import pytest

from test_lifecycle_http import sdk  # shared sync/async fixture


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "  ",
        True,
        12,
        "../account",
        "a/b",
        "a?b",
        "a#b",
        "a%2Fb",
        "a" * 41,
        "حساب",
    ],
)
@pytest.mark.parametrize(
    "method",
    [
        "get_link_session",
        "get_link_qr",
        "wait_for_link",
        "delete_account",
        "start_trial",
        "subscribe",
        "set_auto_renew",
    ],
)
async def test_invalid_resource_id_never_reaches_http(sdk, method, value):
    kwargs = {"idempotency_key": "order-42"} if method == "subscribe" else {}
    args = (value, True) if method == "set_auto_renew" else (value,)
    with pytest.raises(ValueError):
        await sdk.call(method, *args, **kwargs)
    assert sdk.requests == []


@pytest.mark.parametrize("value", ["", True, 5, "a/b", "a" * 41])
@pytest.mark.parametrize("field", ["plan_id", "target_account_id"])
async def test_invalid_optional_ids(sdk, field, value):
    with pytest.raises(ValueError):
        if field == "plan_id":
            await sdk.call(
                "subscribe", "acc_1", idempotency_key="order-42", plan_id=value
            )
        else:
            await sdk.call("create_link_session", target_account_id=value)
    assert sdk.requests == []


@pytest.mark.parametrize(
    "periods", [None, 0, -1, 121, True, False, 1.0, 2.5, "3", [], {}]
)
async def test_invalid_prepaid_periods(sdk, periods):
    with pytest.raises(ValueError):
        await sdk.call(
            "subscribe", "acc_1", idempotency_key="order-42", periods=periods
        )
    assert sdk.requests == []


@pytest.mark.parametrize(
    "key",
    [None, "", " ", "with space", "a\nb", "a\r\nb", "a/b", "a" * 129, "مفتاح", True, 4],
)
async def test_invalid_purchase_key(sdk, key):
    with pytest.raises(ValueError):
        await sdk.call("subscribe", "acc_1", idempotency_key=key)
    assert sdk.requests == []


async def test_purchase_requires_caller_key(sdk):
    with pytest.raises(TypeError):
        await sdk.call("subscribe", "acc_1")
    assert sdk.requests == []


@pytest.mark.parametrize("enabled", [None, 0, 1, "true", "false", [], {}])
async def test_auto_renew_is_not_truthiness_conversion(sdk, enabled):
    with pytest.raises(ValueError):
        await sdk.call("set_auto_renew", "acc_1", enabled)
    assert sdk.requests == []


@pytest.mark.parametrize(
    "value", [0, -1, float("nan"), float("inf"), float("-inf"), True, "3", None]
)
@pytest.mark.parametrize(
    "method,option",
    [
        ("get_link_session", "timeout"),
        ("wait_for_link", "timeout"),
        ("wait_for_link", "poll_interval"),
    ],
)
async def test_timeouts_and_intervals_must_be_finite_positive_numbers(
    sdk, method, option, value
):
    with pytest.raises(ValueError):
        await sdk.call(method, "link_1", **{option: value})
    assert sdk.requests == []
