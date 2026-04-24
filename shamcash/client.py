"""HTTP clients for the ShamCash API."""

from __future__ import annotations

import json
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

Params = Dict[str, Union[str, int]]


def _format_transaction_ids(transaction_ids: Union[int, Sequence[int], str]) -> str:
    if isinstance(transaction_ids, str):
        return transaction_ids
    if isinstance(transaction_ids, int):
        return str(transaction_ids)
    return ",".join(str(value) for value in transaction_ids)


def _parse_json_envelope(response: httpx.Response) -> dict[str, Any]:
    text = response.text
    if not text.strip():
        raise ProtocolError("empty response body", code="INVALID_PAYLOAD", http_status=response.status_code)
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
    if status == "success":
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

    async def fetch_json_envelope(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
    ) -> dict[str, Any]:
        """Return the raw JSON envelope."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = await self._get_client()
        try:
            response = await client.request(method, url, headers=self._headers(), params=params)
        except httpx.TimeoutException as exc:
            raise _timeout_error(exc, url) from exc
        except httpx.RequestError as exc:
            raise _request_error(exc, url) from exc
        return _parse_json_envelope(response)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
    ) -> Tuple[Any, int]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = await self._get_client()
        try:
            response = await client.request(method, url, headers=self._headers(), params=params)
        except httpx.TimeoutException as exc:
            raise _timeout_error(exc, url) from exc
        except httpx.RequestError as exc:
            raise _request_error(exc, url) from exc
        return _unwrap_envelope(response)

    async def list_accounts(self) -> List[Account]:
        """Return linked accounts."""
        data, http_status = await self._request("GET", "/accounts")
        return [Account.from_dict(_expect_object(item, "account", http_status)) for item in _expect_array(data, "accounts", http_status)]

    async def get_account(self, account_id: str) -> Account:
        """Return one linked account."""
        if not account_id:
            raise ValueError("account_id must be non-empty")
        data, http_status = await self._request("GET", f"/accounts/{account_id}")
        return Account.from_dict(_expect_object(data, "account", http_status))

    async def get_balances(self, account_id: str) -> BalancesResult:
        """Return balances for one account."""
        if not account_id:
            raise ValueError("account_id must be non-empty")
        data, http_status = await self._request("GET", "/balances", params={"account_id": account_id})
        return BalancesResult.from_dict(_expect_object(data, "balances", http_status))

    async def list_transactions(
        self,
        account_id: str,
        *,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        transaction_ids: Optional[Union[int, Sequence[int], str]] = None,
        coin_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> TransactionsResult:
        """Return incoming transactions for one account."""
        if not account_id:
            raise ValueError("account_id must be non-empty")
        params: Params = {"account_id": account_id}
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
        return TransactionsResult.from_dict(_expect_object(data, "transactions", http_status))

    async def get_transaction(
        self,
        account_id: str,
        transaction_id: int,
    ) -> Optional[IncomingTransaction]:
        """Return one transaction by id."""
        result = await self.list_transactions(
            account_id,
            transaction_ids=transaction_id,
            limit=1,
        )
        return result.transactions[0] if result.transactions else None


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

    def fetch_json_envelope(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
    ) -> dict[str, Any]:
        """Return the raw JSON envelope."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = self._get_client()
        try:
            response = client.request(method, url, headers=self._headers(), params=params)
        except httpx.TimeoutException as exc:
            raise _timeout_error(exc, url) from exc
        except httpx.RequestError as exc:
            raise _request_error(exc, url) from exc
        return _parse_json_envelope(response)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
    ) -> Tuple[Any, int]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        client = self._get_client()
        try:
            response = client.request(method, url, headers=self._headers(), params=params)
        except httpx.TimeoutException as exc:
            raise _timeout_error(exc, url) from exc
        except httpx.RequestError as exc:
            raise _request_error(exc, url) from exc
        return _unwrap_envelope(response)

    def list_accounts(self) -> List[Account]:
        """Return linked accounts."""
        data, http_status = self._request("GET", "/accounts")
        return [Account.from_dict(_expect_object(item, "account", http_status)) for item in _expect_array(data, "accounts", http_status)]

    def get_account(self, account_id: str) -> Account:
        """Return one linked account."""
        if not account_id:
            raise ValueError("account_id must be non-empty")
        data, http_status = self._request("GET", f"/accounts/{account_id}")
        return Account.from_dict(_expect_object(data, "account", http_status))

    def get_balances(self, account_id: str) -> BalancesResult:
        """Return balances for one account."""
        if not account_id:
            raise ValueError("account_id must be non-empty")
        data, http_status = self._request("GET", "/balances", params={"account_id": account_id})
        return BalancesResult.from_dict(_expect_object(data, "balances", http_status))

    def list_transactions(
        self,
        account_id: str,
        *,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        transaction_ids: Optional[Union[int, Sequence[int], str]] = None,
        coin_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> TransactionsResult:
        """Return incoming transactions for one account."""
        if not account_id:
            raise ValueError("account_id must be non-empty")
        params: Params = {"account_id": account_id}
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
        return TransactionsResult.from_dict(_expect_object(data, "transactions", http_status))

    def get_transaction(
        self,
        account_id: str,
        transaction_id: int,
    ) -> Optional[IncomingTransaction]:
        """Return one transaction by id."""
        result = self.list_transactions(account_id, transaction_ids=transaction_id, limit=1)
        return result.transactions[0] if result.transactions else None