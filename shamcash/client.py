"""HTTP clients for the ShamCash API."""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from urllib.parse import quote
from collections.abc import Sequence
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

from .exceptions import (
    NetworkError,
    ProtocolError,
    RequestTimeoutError,
    parse_retry_after_header,
    raise_for_envelope_code,
)
from .models import Account, BalancesResult, IncomingTransaction, TransactionsResult
from .lifecycle import LinkSession, Plan, SubscriptionReceipt, SubscriptionSettings

Params = Dict[str, Union[str, int]]


def _params_with_optional_account(account_id: Optional[str] = None) -> Params:
    if account_id is None:
        return {}
    account_id = str(account_id).strip()
    if not account_id:
        raise ValueError("account_id must be non-empty when provided")
    return {"account_id": account_id}


def _format_transaction_ids(transaction_ids: Union[int, Sequence[int], str]) -> str:
    if isinstance(transaction_ids, str):
        return transaction_ids
    if isinstance(transaction_ids, int):
        return str(transaction_ids)
    return ",".join(str(value) for value in transaction_ids)


def _parse_json_envelope(response: httpx.Response) -> dict[str, Any]:
    text = response.text
    if not text.strip():
        raise ProtocolError(
            "empty response body",
            code="INVALID_PAYLOAD",
            http_status=response.status_code,
        )
    try:
        body: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError(
            "response is not valid JSON",
            code="INVALID_PAYLOAD",
            data={"body_preview": text[:500]},
            http_status=response.status_code,
        ) from exc
    if not isinstance(body, dict):
        raise ProtocolError(
            "top-level JSON must be an object",
            code="INVALID_PAYLOAD",
            data=body,
            http_status=response.status_code,
        )
    return body


def _unwrap_envelope(response: httpx.Response) -> Tuple[Any, int]:
    body = _parse_json_envelope(response)
    status = body.get("status")
    code = str(body.get("code", "") or "")
    message = str(body.get("message", "") or "")
    data = body.get("data")
    if status == "success" and response.is_success:
        return data, response.status_code
    if status == "error":
        raise_for_envelope_code(
            code,
            message,
            data,
            http_status=response.status_code,
            retry_after=parse_retry_after_header(response.headers.get("Retry-After")),
        )
    raise ProtocolError(
        "invalid response envelope",
        code="INVALID_PAYLOAD",
        data=body,
        http_status=response.status_code,
    )


def _expect_object(value: Any, context: str, http_status: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolError(
            f"{context} must be an object",
            code="INVALID_PAYLOAD",
            data=value,
            http_status=http_status,
        )
    return value


def _expect_array(value: Any, context: str, http_status: int) -> list[Any]:
    if not isinstance(value, list):
        raise ProtocolError(
            f"{context} must be an array",
            code="INVALID_PAYLOAD",
            data=value,
            http_status=http_status,
        )
    return value


def _request_error(exc: httpx.RequestError, url: str) -> NetworkError:
    return NetworkError(
        f"request failed: {exc}",
        code="NETWORK_ERROR",
        data={"url": url},
    )


def _timeout_error(exc: Exception, url: str) -> RequestTimeoutError:
    return RequestTimeoutError(
        "request timed out",
        data={"url": url, "detail": str(exc)},
    )


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,40}", value.strip()
    ):
        raise ValueError(f"{field} must be a non-empty platform ID")
    return quote(value.strip(), safe="")


def _seconds(value: float, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{field} must be a positive finite number")
    return float(value)


def _purchase_args(
    plan_id: Optional[str], periods: int, key: str
) -> Tuple[dict[str, Any], Dict[str, str]]:
    if type(periods) is not int or not 1 <= periods <= 120:
        raise ValueError("periods must be an integer from 1 to 120")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
        raise ValueError(
            "idempotency_key must contain 1–128 letters, digits, dots, underscores, colons or hyphens"
        )
    body: dict[str, Any] = {"periods": periods}
    if plan_id is not None:
        body["plan_id"] = _identifier(plan_id, "plan_id")
    return body, {"Idempotency-Key": key}


def _match_id(actual: str, expected: str) -> None:
    if actual != expected:
        raise ProtocolError(
            "response ID does not match the request", code="INVALID_PAYLOAD"
        )


def _png(response: httpx.Response) -> bytes:
    content_type = (
        response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    )
    if not response.is_success or content_type == "application/json":
        _unwrap_envelope(response)
        raise ProtocolError(
            "unexpected image response",
            code="INVALID_PAYLOAD",
            http_status=response.status_code,
        )
    if (
        content_type != "image/png"
        or not response.content.startswith(b"\x89PNG\r\n\x1a\n")
        or len(response.content) <= 8
    ):
        raise ProtocolError(
            "response is not a PNG image",
            code="INVALID_PAYLOAD",
            http_status=response.status_code,
        )
    return response.content


def _link_timeout(session_id: str) -> RequestTimeoutError:
    return RequestTimeoutError(
        "linking did not finish before the timeout",
        data={"link_session_id": session_id},
    )


class ShamCashAPI:
    """Async client."""

    def __init__(
        self,
        api_token: str,
        base_url: str = "https://api.shamcash-api.com/v1",
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
        session: Optional[httpx.AsyncClient] = None,
    ) -> None:
        if not api_token or not str(api_token).strip():
            raise ValueError("api_token must be a non-empty string")
        if client is not None and session is not None:
            raise ValueError("pass client or session, not both")
        self.api_token = str(api_token).strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client or session
        self._owns_client = self._client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "ShamCashAPI":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }

    async def _send(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = await self._get_client()
        options: dict[str, Any] = {
            "headers": {**self._headers(), **(headers or {})},
            "params": params,
        }
        if json is not None:
            options["json"] = json
        if timeout is not None:
            options["timeout"] = _seconds(timeout, "timeout")
        try:
            return await client.request(method, url, **options)
        except httpx.TimeoutException as exc:
            raise _timeout_error(exc, url) from exc
        except httpx.RequestError as exc:
            raise _request_error(exc, url) from exc

    async def fetch_json_envelope(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Return the raw JSON envelope, including API error envelopes."""
        return _parse_json_envelope(
            await self._send(method, path, params=params, json=json, headers=headers)
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[Any, int]:
        return _unwrap_envelope(
            await self._send(
                method, path, params=params, json=json, headers=headers, timeout=timeout
            )
        )

    async def list_accounts(self) -> List[Account]:
        """Return linked accounts."""
        data, http_status = await self._request("GET", "/accounts")
        return [
            Account.from_dict(_expect_object(item, "account", http_status))
            for item in _expect_array(data, "accounts", http_status)
        ]

    async def get_account(self, account_id: str) -> Account:
        """Return one linked account."""
        data, http_status = await self._request(
            "GET", "/accounts", params=_params_with_optional_account(account_id)
        )
        return Account.from_dict(_expect_object(data, "account", http_status))

    async def get_balances(self, account_id: Optional[str] = None) -> BalancesResult:
        """Return account balances."""
        data, http_status = await self._request(
            "GET", "/balances", params=_params_with_optional_account(account_id)
        )
        return BalancesResult.from_dict(_expect_object(data, "balances", http_status))

    async def list_transactions(
        self,
        account_id: Optional[str] = None,
        *,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        transaction_ids: Optional[Union[int, Sequence[int], str]] = None,
        coin_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> TransactionsResult:
        """Return incoming transactions."""
        params: Params = _params_with_optional_account(account_id)
        if start_at is not None:
            params["start_at"] = start_at
        if end_at is not None:
            params["end_at"] = end_at
        if transaction_ids is not None:
            params["transaction_ids"] = _format_transaction_ids(transaction_ids)
        if coin_id is not None:
            params["coin_id"] = int(coin_id)
        if limit is not None:
            params["limit"] = int(limit)
        data, http_status = await self._request("GET", "/transactions", params=params)
        return TransactionsResult.from_dict(
            _expect_object(data, "transactions", http_status)
        )

    async def get_transaction(
        self,
        account_id: Optional[Union[str, int]] = None,
        transaction_id: Optional[int] = None,
    ) -> Optional[IncomingTransaction]:
        """Return one transaction by id."""
        if transaction_id is None:
            if account_id is None:
                raise ValueError("transaction_id is required")
            transaction_id = int(account_id)
            account_id = None
        result = await self.list_transactions(
            str(account_id) if account_id is not None else None,
            transaction_ids=transaction_id,
            limit=1,
        )
        return result.transactions[0] if result.transactions else None

    async def create_link_session(
        self, *, target_account_id: Optional[str] = None
    ) -> LinkSession:
        """Create a login QR session, or re-link an existing account."""
        body = (
            {"target_account_id": _identifier(target_account_id, "target_account_id")}
            if target_account_id is not None
            else None
        )
        data, status = await self._request("POST", "/link-sessions", json=body)
        return LinkSession.from_dict(_expect_object(data, "link session", status))

    async def get_link_session(
        self, link_session_id: str, *, timeout: float = 120.0
    ) -> LinkSession:
        """Poll once. Expired and failed sessions raise their API exceptions."""
        session_id = _identifier(link_session_id, "link_session_id")
        data, status = await self._request(
            "GET", f"/link-sessions/{session_id}", timeout=_seconds(timeout, "timeout")
        )
        result = LinkSession.from_dict(_expect_object(data, "link session", status))
        _match_id(result.link_session_id, session_id)
        return result

    async def get_link_qr(self, link_session_id: str) -> bytes:
        """Download the pending session's login QR as PNG bytes."""
        session_id = _identifier(link_session_id, "link_session_id")
        return _png(
            await self._send(
                "GET",
                f"/link-sessions/{session_id}/qr",
                headers={"Accept": "image/png"},
            )
        )

    async def wait_for_link(
        self,
        link_session_id: str,
        *,
        timeout: float = 780.0,
        poll_interval: float = 3.0,
    ) -> LinkSession:
        """Wait for linking while respecting the server's polling interval."""
        session_id = _identifier(link_session_id, "link_session_id")
        deadline = time.monotonic() + _seconds(timeout, "timeout")
        interval = _seconds(poll_interval, "poll_interval")
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _link_timeout(session_id)
            result = await self.get_link_session(
                session_id, timeout=min(120.0, remaining)
            )
            if result.state == "success":
                return result
            if result.state in {"expired", "failed"}:
                raise_for_envelope_code(
                    "LINK_EXPIRED" if result.state == "expired" else "LINK_FAILED",
                    data={"link_session_id": session_id, "state": result.state},
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _link_timeout(session_id)
            await asyncio.sleep(
                min(max(interval, result.poll_after_seconds or 0), remaining)
            )

    async def list_plans(self) -> List[Plan]:
        """Return available plans at this token owner's discounted prices."""
        data, status = await self._request("GET", "/plans")
        data = _expect_object(data, "plans", status)
        return [
            Plan.from_dict(_expect_object(item, "plan", status))
            for item in _expect_array(data.get("plans"), "plans", status)
        ]

    async def subscribe(
        self,
        account_id: str,
        *,
        idempotency_key: str,
        plan_id: Optional[str] = None,
        periods: int = 1,
    ) -> SubscriptionReceipt:
        """Buy prepaid access. Reuse the purchase key only for the same purchase."""
        account = _identifier(account_id, "account_id")
        body, headers = _purchase_args(plan_id, periods, idempotency_key)
        data, status = await self._request(
            "POST", f"/accounts/{account}/subscription", json=body, headers=headers
        )
        result = SubscriptionReceipt.from_dict(
            _expect_object(data, "subscription receipt", status)
        )
        _match_id(result.account_id, account)
        return result

    async def set_auto_renew(
        self, account_id: str, enabled: bool
    ) -> SubscriptionSettings:
        """Enable or disable renewal without changing prepaid expiry."""
        account = _identifier(account_id, "account_id")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        data, status = await self._request(
            "PATCH", f"/accounts/{account}/subscription", json={"auto_renew": enabled}
        )
        result = SubscriptionSettings.from_dict(
            _expect_object(data, "subscription settings", status)
        )
        _match_id(result.account_id, account)
        return result

    async def start_trial(self, account_id: str) -> Account:
        """Activate the account's one-time free trial."""
        account = _identifier(account_id, "account_id")
        data, status = await self._request("POST", f"/accounts/{account}/trial")
        data = _expect_object(data, "trial", status)
        result = Account.from_dict(
            _expect_object(data.get("account"), "account", status)
        )
        _match_id(result.id, account)
        return result

    async def delete_account(self, account_id: str) -> str:
        """Unlink the platform account and return its deleted ID."""
        account = _identifier(account_id, "account_id")
        data, status = await self._request("DELETE", f"/accounts/{account}")
        data = _expect_object(data, "deleted account", status)
        _match_id(data.get("account_id"), account)
        return account


class ShamCashAPISync:
    """Sync client."""

    def __init__(
        self,
        api_token: str,
        base_url: str = "https://api.shamcash-api.com/v1",
        timeout: float = 30.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        if not api_token or not str(api_token).strip():
            raise ValueError("api_token must be a non-empty string")
        self.api_token = str(api_token).strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()

    def __enter__(self) -> "ShamCashAPISync":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = self._get_client()
        options: dict[str, Any] = {
            "headers": {**self._headers(), **(headers or {})},
            "params": params,
        }
        if json is not None:
            options["json"] = json
        if timeout is not None:
            options["timeout"] = _seconds(timeout, "timeout")
        try:
            return client.request(method, url, **options)
        except httpx.TimeoutException as exc:
            raise _timeout_error(exc, url) from exc
        except httpx.RequestError as exc:
            raise _request_error(exc, url) from exc

    def fetch_json_envelope(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Return the raw JSON envelope, including API error envelopes."""
        return _parse_json_envelope(
            self._send(method, path, params=params, json=json, headers=headers)
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[Any, int]:
        return _unwrap_envelope(
            self._send(
                method, path, params=params, json=json, headers=headers, timeout=timeout
            )
        )

    def list_accounts(self) -> List[Account]:
        """Return linked accounts."""
        data, http_status = self._request("GET", "/accounts")
        return [
            Account.from_dict(_expect_object(item, "account", http_status))
            for item in _expect_array(data, "accounts", http_status)
        ]

    def get_account(self, account_id: str) -> Account:
        """Return one linked account."""
        data, http_status = self._request(
            "GET", "/accounts", params=_params_with_optional_account(account_id)
        )
        return Account.from_dict(_expect_object(data, "account", http_status))

    def get_balances(self, account_id: Optional[str] = None) -> BalancesResult:
        """Return account balances."""
        data, http_status = self._request(
            "GET", "/balances", params=_params_with_optional_account(account_id)
        )
        return BalancesResult.from_dict(_expect_object(data, "balances", http_status))

    def list_transactions(
        self,
        account_id: Optional[str] = None,
        *,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        transaction_ids: Optional[Union[int, Sequence[int], str]] = None,
        coin_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> TransactionsResult:
        """Return incoming transactions."""
        params: Params = _params_with_optional_account(account_id)
        if start_at is not None:
            params["start_at"] = start_at
        if end_at is not None:
            params["end_at"] = end_at
        if transaction_ids is not None:
            params["transaction_ids"] = _format_transaction_ids(transaction_ids)
        if coin_id is not None:
            params["coin_id"] = int(coin_id)
        if limit is not None:
            params["limit"] = int(limit)
        data, http_status = self._request("GET", "/transactions", params=params)
        return TransactionsResult.from_dict(
            _expect_object(data, "transactions", http_status)
        )

    def get_transaction(
        self,
        account_id: Optional[Union[str, int]] = None,
        transaction_id: Optional[int] = None,
    ) -> Optional[IncomingTransaction]:
        """Return one transaction by id."""
        if transaction_id is None:
            if account_id is None:
                raise ValueError("transaction_id is required")
            transaction_id = int(account_id)
            account_id = None
        result = self.list_transactions(
            str(account_id) if account_id is not None else None,
            transaction_ids=transaction_id,
            limit=1,
        )
        return result.transactions[0] if result.transactions else None

    def create_link_session(
        self, *, target_account_id: Optional[str] = None
    ) -> LinkSession:
        """Create a login QR session, or re-link an existing account."""
        body = (
            {"target_account_id": _identifier(target_account_id, "target_account_id")}
            if target_account_id is not None
            else None
        )
        data, status = self._request("POST", "/link-sessions", json=body)
        return LinkSession.from_dict(_expect_object(data, "link session", status))

    def get_link_session(
        self, link_session_id: str, *, timeout: float = 120.0
    ) -> LinkSession:
        """Poll once. Expired and failed sessions raise their API exceptions."""
        session_id = _identifier(link_session_id, "link_session_id")
        data, status = self._request(
            "GET", f"/link-sessions/{session_id}", timeout=_seconds(timeout, "timeout")
        )
        result = LinkSession.from_dict(_expect_object(data, "link session", status))
        _match_id(result.link_session_id, session_id)
        return result

    def get_link_qr(self, link_session_id: str) -> bytes:
        """Download the pending session's login QR as PNG bytes."""
        session_id = _identifier(link_session_id, "link_session_id")
        return _png(
            self._send(
                "GET",
                f"/link-sessions/{session_id}/qr",
                headers={"Accept": "image/png"},
            )
        )

    def wait_for_link(
        self,
        link_session_id: str,
        *,
        timeout: float = 780.0,
        poll_interval: float = 3.0,
    ) -> LinkSession:
        """Wait for linking while respecting the server's polling interval."""
        session_id = _identifier(link_session_id, "link_session_id")
        deadline = time.monotonic() + _seconds(timeout, "timeout")
        interval = _seconds(poll_interval, "poll_interval")
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _link_timeout(session_id)
            result = self.get_link_session(session_id, timeout=min(120.0, remaining))
            if result.state == "success":
                return result
            if result.state in {"expired", "failed"}:
                raise_for_envelope_code(
                    "LINK_EXPIRED" if result.state == "expired" else "LINK_FAILED",
                    data={"link_session_id": session_id, "state": result.state},
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _link_timeout(session_id)
            time.sleep(min(max(interval, result.poll_after_seconds or 0), remaining))

    def list_plans(self) -> List[Plan]:
        """Return available plans at this token owner's discounted prices."""
        data, status = self._request("GET", "/plans")
        data = _expect_object(data, "plans", status)
        return [
            Plan.from_dict(_expect_object(item, "plan", status))
            for item in _expect_array(data.get("plans"), "plans", status)
        ]

    def subscribe(
        self,
        account_id: str,
        *,
        idempotency_key: str,
        plan_id: Optional[str] = None,
        periods: int = 1,
    ) -> SubscriptionReceipt:
        """Buy prepaid access. Reuse the purchase key only for the same purchase."""
        account = _identifier(account_id, "account_id")
        body, headers = _purchase_args(plan_id, periods, idempotency_key)
        data, status = self._request(
            "POST", f"/accounts/{account}/subscription", json=body, headers=headers
        )
        result = SubscriptionReceipt.from_dict(
            _expect_object(data, "subscription receipt", status)
        )
        _match_id(result.account_id, account)
        return result

    def set_auto_renew(self, account_id: str, enabled: bool) -> SubscriptionSettings:
        """Enable or disable renewal without changing prepaid expiry."""
        account = _identifier(account_id, "account_id")
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        data, status = self._request(
            "PATCH", f"/accounts/{account}/subscription", json={"auto_renew": enabled}
        )
        result = SubscriptionSettings.from_dict(
            _expect_object(data, "subscription settings", status)
        )
        _match_id(result.account_id, account)
        return result

    def start_trial(self, account_id: str) -> Account:
        """Activate the account's one-time free trial."""
        account = _identifier(account_id, "account_id")
        data, status = self._request("POST", f"/accounts/{account}/trial")
        data = _expect_object(data, "trial", status)
        result = Account.from_dict(
            _expect_object(data.get("account"), "account", status)
        )
        _match_id(result.id, account)
        return result

    def delete_account(self, account_id: str) -> str:
        """Unlink the platform account and return its deleted ID."""
        account = _identifier(account_id, "account_id")
        data, status = self._request("DELETE", f"/accounts/{account}")
        data = _expect_object(data, "deleted account", status)
        _match_id(data.get("account_id"), account)
        return account
