"""
Async and sync HTTP clients for the ShamCash API.

See ``docs/ShamCash-API-Docs.md`` for endpoint behavior, filters, and error codes.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any, Dict, List, Optional, Union

import aiohttp

from .exceptions import (
    NetworkError,
    ProtocolError,
    RequestTimeoutError,
    parse_retry_after_header,
    raise_for_envelope_code,
)
from .models import Account, BalancesResult, IncomingTransaction, TransactionsResult


def _format_transaction_ids(transaction_ids: Union[int, Sequence[int], str]) -> str:
    """Build the ``transaction_ids`` query value (comma-separated numeric ids)."""
    if isinstance(transaction_ids, str):
        return transaction_ids
    if isinstance(transaction_ids, int):
        return str(transaction_ids)
    return ",".join(str(i) for i in transaction_ids)


def _retry_after_from_response(response: aiohttp.ClientResponse) -> Optional[int]:
    return parse_retry_after_header(response.headers.get("Retry-After"))


def _parse_json_envelope(
    text: str,
    http_status: int,
) -> dict[str, Any]:
    if not text.strip():
        raise ProtocolError(
            "empty response body",
            code="INVALID_PAYLOAD",
            data=None,
            http_status=http_status,
        )
    try:
        body: Any = json.loads(text)
    except json.JSONDecodeError as e:
        raise ProtocolError(
            f"response is not valid JSON: {e}",
            code="INVALID_PAYLOAD",
            data={"body_preview": text[:500]},
            http_status=http_status,
        ) from e
    if not isinstance(body, dict):
        raise ProtocolError(
            f"top-level JSON must be an object, got {type(body).__name__}",
            code="INVALID_PAYLOAD",
            data=body,
            http_status=http_status,
        )
    return body


def _handle_business_envelope(
    body: dict[str, Any],
    http_status: int,
    response: aiohttp.ClientResponse,
) -> Any:
    status = body.get("status")
    code = str(body.get("code", "") or "")
    message = str(body.get("message", "") or "")
    data = body.get("data")
    if status == "success":
        return data
    if status == "error":
        ra = _retry_after_from_response(response) if (code == "RATE_LIMIT_EXCEEDED" or http_status == 429) else None
        raise_for_envelope_code(
            code,
            message,
            data,
            http_status=http_status,
            retry_after=ra,
        )
    raise ProtocolError(
        message or "Unexpected envelope: missing or unknown status",
        code="INVALID_PAYLOAD",
        data=body,
        http_status=http_status,
    )


class ShamCashAPI:
    """
    Async client for ``https://api.shamcash-api.com/v1``.

    Every request sends ``Authorization: Bearer <token>``. Responses are parsed as
    JSON objects with envelope fields. On server ``status: error`` or malformed
    payloads, an exception is raised. Successful high-level methods return typed
    models. Use :meth:`fetch_json_envelope` to inspect the raw JSON object without
    mapping API error codes to exceptions.
    """

    def __init__(
        self,
        api_token: str,
        base_url: str = "https://api.shamcash-api.com/v1",
        timeout: int = 30,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        if not api_token or not str(api_token).strip():
            raise ValueError("api_token must be a non-empty string")
        self.api_token = str(api_token).strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session
        self._own_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed and self._own_session:
            await self._session.close()

    async def __aenter__(self) -> ShamCashAPI:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def fetch_json_envelope(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Union[str, int]]] = None,
    ) -> dict[str, Any]:
        """
        Perform one HTTP call and return the **full** parsed JSON object
        (``status``, ``code``, ``message``, ``data``). Does **not** raise for
        ``status: "error"``; callers should inspect ``status`` and ``code``.

        Still raises for transport failures, timeouts, and non-envelope JSON
        (:class:`NetworkError`, :class:`RequestTimeoutError`, :class:`ProtocolError`).
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
        try:
            session = await self._get_session()
            async with session.request(method, url, headers=headers, params=params) as response:
                text = await response.text()
                body = _parse_json_envelope(text, response.status)
                return body
        except (asyncio.TimeoutError, TimeoutError) as e:
            raise RequestTimeoutError(
                "Request timed out",
                data={"url": url},
            ) from e
        except aiohttp.ServerTimeoutError as e:
            raise RequestTimeoutError(
                f"Request timed out: {e}",
                data={"url": url},
            ) from e
        except aiohttp.ClientError as e:
            raise NetworkError(
                f"Network request failed: {e}",
                code="NETWORK_ERROR",
                data={"url": url},
            ) from e

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Union[str, int]]] = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
        try:
            session = await self._get_session()
            async with session.request(method, url, headers=headers, params=params) as response:
                text = await response.text()
                body = _parse_json_envelope(text, response.status)
                return _handle_business_envelope(body, response.status, response)
        except (asyncio.TimeoutError, TimeoutError) as e:
            raise RequestTimeoutError(
                "Request timed out",
                data={"url": url},
            ) from e
        except aiohttp.ServerTimeoutError as e:
            raise RequestTimeoutError(
                f"Request timed out: {e}",
                data={"url": url},
            ) from e
        except aiohttp.ClientError as e:
            raise NetworkError(
                f"Network request failed: {e}",
                code="NETWORK_ERROR",
                data={"url": url},
            ) from e

    async def list_accounts(self) -> List[Account]:
        """
        ``GET /accounts`` — all ShamCash accounts linked to the authenticated user.

        Raises:
            :class:`ProtocolError` if ``data`` is not a JSON array (per API docs).
        """
        raw = await self._request("GET", "/accounts")
        if raw is None:
            raise ProtocolError(
                "GET /accounts success payload must be a JSON array, got null",
                code="INVALID_PAYLOAD",
                data=raw,
            )
        if not isinstance(raw, list):
            raise ProtocolError(
                "GET /accounts success payload must be a JSON array",
                code="INVALID_PAYLOAD",
                data=raw,
            )
        out: List[Account] = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ProtocolError(
                    f"accounts[{i}] must be an object",
                    code="INVALID_PAYLOAD",
                    data=item,
                )
            out.append(Account.from_dict(item))
        return out

    async def get_account(self, account_id: str) -> Account:
        if not account_id:
            raise ValueError("account_id must be non-empty")
        raw = await self._request("GET", f"/accounts/{account_id}")
        if not isinstance(raw, dict):
            raise ProtocolError(
                "GET /accounts/{id} data must be a JSON object",
                code="INVALID_PAYLOAD",
                data=raw,
            )
        return Account.from_dict(raw)

    async def get_balances(self, account_id: str) -> BalancesResult:
        if not account_id:
            raise ValueError("account_id must be non-empty")
        raw = await self._request("GET", "/balances", params={"account_id": account_id})
        if not isinstance(raw, dict):
            raise ProtocolError(
                "GET /balances data must be a JSON object",
                code="INVALID_PAYLOAD",
                data=raw,
            )
        return BalancesResult.from_dict(raw)

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
        if not account_id:
            raise ValueError("account_id must be non-empty")
        params: Dict[str, Union[str, int]] = {"account_id": account_id}
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
        raw = await self._request("GET", "/transactions", params=params)
        if not isinstance(raw, dict):
            raise ProtocolError(
                "GET /transactions data must be a JSON object",
                code="INVALID_PAYLOAD",
                data=raw,
            )
        return TransactionsResult.from_dict(raw)

    async def get_transaction(
        self, account_id: str, transaction_id: int
    ) -> Optional[IncomingTransaction]:
        result = await self.list_transactions(
            account_id,
            transaction_ids=transaction_id,
            limit=1,
        )
        if not result.transactions:
            return None
        return result.transactions[0]


class ShamCashAPISync:
    """
    Synchronous wrapper with a dedicated event loop (created in ``__init__``,
    closed in :meth:`close`).

    Do not use from inside a running asyncio event loop; use :class:`ShamCashAPI`
    instead.
    """

    def __init__(
        self,
        api_token: str,
        base_url: str = "https://api.shamcash-api.com/v1",
        timeout: int = 30,
    ) -> None:
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._closed = False
        self._async_client = ShamCashAPI(
            api_token=api_token,
            base_url=base_url,
            timeout=timeout,
        )

    def _run(self, coro: Any) -> Any:
        if self._closed or self._loop.is_closed():
            raise RuntimeError("ShamCashAPISync is closed")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return self._loop.run_until_complete(coro)
        raise RuntimeError(
            "Cannot use ShamCashAPISync inside a running event loop; use ShamCashAPI instead."
        )

    def close(self) -> None:
        if self._closed or self._loop.is_closed():
            return
        self._run(self._async_client.close())
        self._loop.close()
        self._closed = True

    def __enter__(self) -> ShamCashAPISync:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def list_accounts(self) -> List[Account]:
        return self._run(self._async_client.list_accounts())

    def get_account(self, account_id: str) -> Account:
        return self._run(self._async_client.get_account(account_id))

    def get_balances(self, account_id: str) -> BalancesResult:
        return self._run(self._async_client.get_balances(account_id))

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
        return self._run(
            self._async_client.list_transactions(
                account_id,
                start_at=start_at,
                end_at=end_at,
                transaction_ids=transaction_ids,
                coin_id=coin_id,
                limit=limit,
            )
        )

    def get_transaction(
        self, account_id: str, transaction_id: int
    ) -> Optional[IncomingTransaction]:
        return self._run(self._async_client.get_transaction(account_id, transaction_id))

    def fetch_json_envelope(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Union[str, int]]] = None,
    ) -> dict[str, Any]:
        """Sync: :meth:`ShamCashAPI.fetch_json_envelope`."""
        return self._run(self._async_client.fetch_json_envelope(method, path, params=params))
