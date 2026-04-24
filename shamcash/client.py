"""
Async and sync HTTP clients for the ShamCash API.

See ``docs/ShamCash-API-Docs.md`` for endpoint behavior, filters, and error codes.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Sequence, Union, cast

import aiohttp

from .exceptions import NetworkError, ShamCashAPIError, raise_for_envelope_code
from .models import Account, BalancesResult, IncomingTransaction, TransactionsResult


def _format_transaction_ids(transaction_ids: Union[int, Sequence[int], str]) -> str:
    """Build the ``transaction_ids`` query value (comma-separated numeric ids)."""
    if isinstance(transaction_ids, str):
        return transaction_ids
    if isinstance(transaction_ids, int):
        return str(transaction_ids)
    return ",".join(str(i) for i in transaction_ids)


class ShamCashAPI:
    """
    Async client for ``https://api.shamcash-api.com/v1``.

    Every request sends ``Authorization: Bearer <token>``. Responses are parsed as
    JSON envelopes: ``status``, ``code``, ``message``, ``data``. On error, an
    exception from :mod:`shamcash.exceptions` is raised; successful calls return
    typed models from :mod:`shamcash.models`.

    Example::

        import asyncio
        from shamcash import ShamCashAPI

        async def main():
            async with ShamCashAPI(api_token="...") as client:
                accounts = await client.list_accounts()
                balances = await client.get_balances(accounts[0].id)

        asyncio.run(main())
    """

    def __init__(
        self,
        api_token: str,
        base_url: str = "https://api.shamcash-api.com/v1",
        timeout: int = 30,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """
        Args:
            api_token: Dashboard API token (Bearer).
            base_url: API root including ``/v1`` (trailing slash optional).
            timeout: Total request timeout in seconds.
            session: Optional shared :class:`aiohttp.ClientSession`.
        """
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
        """Close the client session if this client owns it."""
        if self._session and not self._session.closed and self._own_session:
            await self._session.close()

    async def __aenter__(self) -> ShamCashAPI:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Union[str, int]]] = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
        try:
            session = await self._get_session()
            async with session.request(method, url, headers=headers, params=params) as response:
                text = await response.text()
                try:
                    body: Any = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    raise NetworkError(
                        f"Invalid JSON response (HTTP {response.status})",
                        code="NETWORK_ERROR",
                        data={"http_status": response.status, "body_preview": text[:500]},
                    )

                if not isinstance(body, dict):
                    raise NetworkError(
                        "Response JSON was not an object",
                        code="NETWORK_ERROR",
                        data={"http_status": response.status},
                    )

                status = body.get("status")
                code = str(body.get("code", "") or "")
                message = str(body.get("message", "") or "")
                data = body.get("data")

                if status == "success":
                    return data
                if status == "error":
                    raise_for_envelope_code(code, message, data)

                raise ShamCashAPIError(
                    message or "Unexpected envelope: missing or unknown status",
                    code=code or "UNKNOWN_ENVELOPE",
                    data=body,
                )
        except aiohttp.ClientError as e:
            raise NetworkError(
                f"Network request failed: {e}",
                code="NETWORK_ERROR",
            ) from e

    async def list_accounts(self) -> List[Account]:
        """
        ``GET /accounts`` — all ShamCash accounts linked to the authenticated user.

        Returns:
            List of :class:`~shamcash.models.Account`.

        Raises:
            AuthMissingError, AuthInvalidError, RateLimitExceededError, FetchFailedError,
            InternalError, NetworkError, etc., per API ``code``.
        """
        raw = await self._request("GET", "/accounts")
        if raw is None:
            return []
        if not isinstance(raw, list):
            return []
        return [Account.from_dict(cast(Dict[str, Any], item)) for item in raw if isinstance(item, dict)]

    async def get_account(self, account_id: str) -> Account:
        """
        ``GET /accounts/{account_id}`` — one linked account by id.

        Args:
            account_id: Stable linked account id from :meth:`list_accounts`.

        Returns:
            :class:`~shamcash.models.Account`.

        Raises:
            AccountNotFoundError: If the account is missing or not linked to this token.
        """
        if not account_id:
            raise ValueError("account_id must be non-empty")
        raw = await self._request("GET", f"/accounts/{account_id}")
        if not isinstance(raw, dict):
            raise ShamCashAPIError("Unexpected accounts payload", code="UNKNOWN_ENVELOPE", data=raw)
        return Account.from_dict(raw)

    async def get_balances(self, account_id: str) -> BalancesResult:
        """
        ``GET /balances`` — balance rows for one linked account.

        Args:
            account_id: Required. Linked account id.

        Returns:
            :class:`~shamcash.models.BalancesResult` with ``account_id`` and ``balances``.

        Raises:
            SubscriptionUnavailableError: Inactive link or no active subscription.
            AccountNotFoundError: Unknown account for this user (if returned by API).
        """
        if not account_id:
            raise ValueError("account_id must be non-empty")
        raw = await self._request("GET", "/balances", params={"account_id": account_id})
        if not isinstance(raw, dict):
            raise ShamCashAPIError("Unexpected balances payload", code="UNKNOWN_ENVELOPE", data=raw)
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
        """
        ``GET /transactions`` — incoming transactions for one account with optional filters.

        Server-side filter order (per docs): ``account_id`` scope, ``start_at`` /
        ``end_at``, ``coin_id``, intersection with ``transaction_ids``, then ``limit``.

        Args:
            account_id: Required linked account id.
            start_at: Inclusive lower bound (``YYYY-MM-DD`` or datetime; Asia/Damascus
                if no offset in string).
            end_at: Inclusive upper bound; same rules as ``start_at``.
            transaction_ids: Comma-separated numeric ids as a string, a single int,
                or a sequence of ints. If none match, the API still succeeds with an
                empty ``transactions`` list.
            coin_id: Currency filter: ``1`` USD, ``2`` SYP, ``3`` EUR.
            limit: Max rows (default on server ``20``; server may cap e.g. ``200``).

        Returns:
            :class:`~shamcash.models.TransactionsResult`.

        Raises:
            SubscriptionUnavailableError: When the account cannot be used for this operation.
        """
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
            raise ShamCashAPIError("Unexpected transactions payload", code="UNKNOWN_ENVELOPE", data=raw)
        return TransactionsResult.from_dict(raw)

    async def get_transaction(self, account_id: str, transaction_id: int) -> Optional[IncomingTransaction]:
        """
        Fetch a single incoming transaction by id using the ``transaction_ids`` filter.

        This maps to ``GET /transactions`` with ``transaction_ids=<id>``. If the id
        does not exist for that account, the API returns success with an empty list;
        this method then returns ``None``.

        Args:
            account_id: Linked account id.
            transaction_id: Numeric ``transaction_id`` from the API.

        Returns:
            :class:`~shamcash.models.IncomingTransaction` or ``None`` if not found.
        """
        result = await self.list_transactions(
            account_id,
            transaction_ids=transaction_id,
            limit=1,
        )
        if not result.transactions:
            return None
        return result.transactions[0]

    @staticmethod
    def find_transaction_by_id(
        transactions: Sequence[IncomingTransaction],
        transaction_id: int,
    ) -> Optional[IncomingTransaction]:
        """
        Return the first transaction in ``transactions`` with the given ``transaction_id``.

        Useful for client-side lookups without an extra API call.
        """
        for tx in transactions:
            if tx.transaction_id == transaction_id:
                return tx
        return None


class ShamCashAPISync:
    """
    Synchronous wrapper around :class:`ShamCashAPI`.

    Do not use from inside a running asyncio event loop; use :class:`ShamCashAPI`
    instead.

    Example::

        from shamcash import ShamCashAPISync

        with ShamCashAPISync(api_token="...") as client:
            accounts = client.list_accounts()
    """

    def __init__(
        self,
        api_token: str,
        base_url: str = "https://api.shamcash-api.com/v1",
        timeout: int = 30,
    ) -> None:
        self._async_client = ShamCashAPI(
            api_token=api_token,
            base_url=base_url,
            timeout=timeout,
        )

    def _run(self, coro: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "Cannot use ShamCashAPISync inside a running event loop; use ShamCashAPI instead."
            )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(coro)

    def close(self) -> None:
        self._run(self._async_client.close())

    def __enter__(self) -> ShamCashAPISync:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def list_accounts(self) -> List[Account]:
        """Sync: :meth:`ShamCashAPI.list_accounts`."""
        return self._run(self._async_client.list_accounts())

    def get_account(self, account_id: str) -> Account:
        """Sync: :meth:`ShamCashAPI.get_account`."""
        return self._run(self._async_client.get_account(account_id))

    def get_balances(self, account_id: str) -> BalancesResult:
        """Sync: :meth:`ShamCashAPI.get_balances`."""
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
        """Sync: :meth:`ShamCashAPI.list_transactions`."""
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

    def get_transaction(self, account_id: str, transaction_id: int) -> Optional[IncomingTransaction]:
        """Sync: :meth:`ShamCashAPI.get_transaction`."""
        return self._run(self._async_client.get_transaction(account_id, transaction_id))

    @staticmethod
    def find_transaction_by_id(
        transactions: Sequence[IncomingTransaction],
        transaction_id: int,
    ) -> Optional[IncomingTransaction]:
        """Sync: :meth:`ShamCashAPI.find_transaction_by_id`."""
        return ShamCashAPI.find_transaction_by_id(transactions, transaction_id)
