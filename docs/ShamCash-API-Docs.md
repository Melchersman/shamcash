# ShamCash API

HTTP API for ShamCash accounts linked to a user of [shamcash-api.com](https://shamcash-api.com). After registering and obtaining an API token, an integration can create QR linking sessions, check linking results, retrieve or remove accounts, activate or renew subscriptions, read balances, and query incoming transactions.

**Base URL:** `https://api.shamcash-api.com/v1`

All paths below are relative to that base URL.

---

## Authentication

Every request must include a valid **API token** issued from your platform dashboard.

**Header**

```http
Authorization: Bearer <api_token>
```

Tokens are opaque strings. Treat them as secrets; do not embed them in client-side web code or public repositories.

If the token is missing, invalid, or revoked, the API returns `status: "error"` with an appropriate `code` and a human-readable `message` (see [Response envelope](#response-envelope)).

---

## Conventions

### Versioning

The `v1` path segment is the current major version. Incompatible changes will be introduced under `v2`, `v3`, and so on.

### Content type

Responses use `application/json`, except the linking QR download, which returns `image/png`. Send JSON request bodies with `Content-Type: application/json`.

### Time zones

For **`/transactions`** query parameters, **`start_at`** and **`end_at`** are interpreted in **`Asia/Damascus`** unless you pass a full ISO 8601 value with an explicit offset.

Transaction objects return **`occurred_at`** as an ISO 8601 timestamp **with offset** (for example `2026-04-16T01:22:21+03:00`).

### Account lifecycle

Account responses additionally include `subscription_type`, `auto_renew` and `provider_session_status`. The existing `/accounts?account_id=...` lookup remains supported.

Each item under **`/accounts`** is a ShamCash account linked to the token's owner, through either the dashboard or this API. It has a **`status`** (`active` | `inactive`) and optional **`subscription_expires_at`** describing when API access for that link ends. Linking does not activate or purchase a plan. Activate a trial or paid plan separately before calling **`/balances`** or **`/transactions`**; otherwise they return **`SUBSCRIPTION_UNAVAILABLE`**.

### Per-account rate limit

Account-specific reads are throttled at **6 requests per minute per linked ShamCash account**.

- The limit key is the linked ShamCash `account_id`, not the platform user id.
- The limiter currently applies to `GET /accounts/{account_id}`, `GET /balances?account_id=...`, and `GET /transactions?account_id=...`.
- When the limit is exceeded the API returns `429 RATE_LIMIT_EXCEEDED`.

---

## Response envelope

Every response uses the same top-level shape:

```json
{
  "status": "success",
  "code": "SUCCESS",
  "message": "Accounts retrieved successfully.",
  "data": {}
}
```

| Field     | Type   | Description |
|-----------|--------|-------------|
| `status`  | string | `"success"` or `"error"` |
| `code`    | string | Machine-readable outcome (see [Error codes](#error-codes)) |
| `message` | string | Human-readable summary: on success, a short confirmation; on error, what went wrong and what the user can do next |
| `data`    | mixed  | Payload on success; on error often `null` or `[]` depending on endpoint |

### Success

- `status` is `"success"`.
- `code` is `"SUCCESS"` or an endpoint-specific success code such as `LINK_SESSION_CREATED`, `LINK_PENDING`, `LINK_SUCCESS`, `TRIAL_STARTED`, `SUBSCRIPTION_ACTIVATED`, or `ACCOUNT_REMOVED`.
- `message` briefly describes the outcome (for example *"Balances retrieved successfully."*).
- `data` follows the schema described for each endpoint.

### Error

- `status` is `"error"`.
- `code` is one of the values in [Error codes](#error-codes).
- `message` **always** explains the failure in plain language (validation hint, auth hint, subscription hint, etc.).
- `data` is typically `null` or an empty array. Clients should use **`code`** for branching and **`message`** for display or logging.

---

## Error codes

| `code` | Typical HTTP | Meaning |
|--------|----------------|--------|
| `SUCCESS` | `200` | Request completed successfully. |
| `VALIDATION_ERROR` | `400` | Malformed or conflicting query parameters (e.g. invalid date format, invalid `coin_id`). |
| `AUTH_MISSING` | `401` | No `Authorization` header or empty token. |
| `AUTH_INVALID` | `401` | Token unknown, expired, or revoked. |
| `FORBIDDEN` | `403` | Token valid but not allowed to perform this action. |
| `NOT_FOUND` | `404` | Resource not found (generic). |
| `ACCOUNT_NOT_FOUND` | `404` | Unknown `account_id` for the authenticated user. |
| `SUBSCRIPTION_UNAVAILABLE` | `403` | This operation is not allowed because the account has **no active subscription**, the subscription **period has ended**, the ShamCash link is **inactive**, or subscription data is **missing**. The exact situation is described in **`message`**. |
| `RATE_LIMIT_EXCEEDED` | `429` | Too many requests; retry after the period indicated by `Retry-After` when present. |
| `FETCH_FAILED` | `502` | Upstream or internal data fetch failed; safe to retry with backoff. |
| `INTERNAL_ERROR` | `500` | Unexpected server error. |
| `LINK_EXPIRED` | `410` | The QR linking window or approved-session finalization window ended. Create a new linking session. |
| `LINK_FAILED` | `400` | Linking failed, the scanned account did not match a re-link target, or the linked account was removed. |
| `PLAN_NOT_FOUND` | `404` | The requested subscription plan does not exist or is inactive. |
| `INSUFFICIENT_BALANCE` | `400` | The platform USD wallet cannot cover the plan price. No purchase was made. |
| `SUBSCRIPTION_ALREADY_ACTIVE` | `409` | A trial cannot be started while a trial or paid subscription is active. Paid purchases extend existing time. |
| `TRIAL_ALREADY_USED` | `409` | This linked account has already used its trial. |
| `UPSTREAM_UNAVAILABLE` | `502` | A provider request could not complete. Retry with backoff while the linking session remains pending. |

| `API_MANAGEMENT_DISABLED` | 403 | Enable account management on the API-token page. |
| `IDEMPOTENCY_KEY_REQUIRED` | 400 | Subscription purchases require an Idempotency-Key header. |
| `IDEMPOTENCY_KEY_REUSED` | 409 | This purchase key was used with different parameters. |
| `LINK_QR_UNAVAILABLE` | 409 | This session no longer has an available scannable QR. |

Exact HTTP status for a given `code` may be tuned per deployment; use **`status`**, **`code`**, **`message`**, and **`data`** for client logic.

---

## Account management from your application

These endpoints are an optional alternative to managing ShamCash links and subscriptions in the platform dashboard. The user scans the QR in ShamCash; the remaining linking and subscription steps can run in your application.

Enable **account and subscription management** on the platform's API-token page first. Existing tokens retain read access while management is disabled; mutations and linking requests return `403 API_MANAGEMENT_DISABLED`. Accounts and charges belong to the token owner. Platform registration, API-token setup and wallet funding remain on the platform.

## QR account linking

All linking and account-management operations use the same Bearer API token as reads. Sessions and accounts belong to the token's platform user; another user's IDs return `404`. Keep the token on your server. Your frontend can display the QR image and receive sanitized session status from your server.

### `POST /link-sessions`

Create a login QR. No request body is required. To restore an existing account's expired provider session while preserving its platform ID and subscription, send:

```json
{"target_account_id": "acc_01hqy8k2example"}
```

Only that same ShamCash account can approve a targeted re-link. Omitting the target creates a normal linking attempt; scanning an account already linked to the same user refreshes its existing credentials and preserves its ID and plan.

```bash
curl -X POST "https://api.shamcash-api.com/v1/link-sessions" \
  -H "Authorization: Bearer <api_token>"
```

HTTP `201`, code `LINK_SESSION_CREATED`:

```json
{
  "status": "success",
  "code": "LINK_SESSION_CREATED",
  "message": "تم إنشاء جلسة الربط.",
  "data": {
    "link_session_id": "lnk_example",
    "state": "pending",
    "qr_payload": {"sessionId": "...", "publicKey": "...", "infoDevice": "..."},
    "qr_text": "{\"sessionId\":\"...\",\"publicKey\":\"...\",\"infoDevice\":\"...\"}",
    "qr_image": "data:image/png;base64,...",
    "expires_at": "2026-10-20T16:10:00+03:00",
    "remaining_seconds": 600,
    "approval_received": false,
    "poll_after_seconds": 3
  }
}
```

- Display `qr_image` directly in an image element, or generate a QR from **exactly `qr_text`**. `qr_payload` contains the equivalent JSON object.
- This login QR differs from the plain receiving-address `qr_payload` returned by `/accounts`.
- Ask the account owner to scan it in the ShamCash application. The scan window is **600 seconds**; use `expires_at` and `remaining_seconds` for the countdown.
- Then poll the returned `link_session_id`; scanning alone does not finalize the platform link.
- Linking responses include `Cache-Control: no-store`. Do not log or publicly cache login QR data. Provider login credentials are never returned.

### `GET /link-sessions/{link_session_id}`

Poll with the same owner's token. Wait at least `poll_after_seconds` (currently **3 seconds**) between completed requests, and keep at most one poll in flight per session. Allow for slow provider responses.

| State | HTTP | Code | Action |
|---|---|---|---|
| `pending` | `200` | `LINK_PENDING` | Keep polling. |
| `success` | `200` | `LINK_SUCCESS` | Store `data.account_id`; `data.account` is the same public account object returned by `/accounts`. |
| `expired` | `410` | `LINK_EXPIRED` | Stop polling and create a new QR session. |
| `failed` | `400` | `LINK_FAILED` | Stop polling. Correct the cause before creating another session. |

```bash
curl "https://api.shamcash-api.com/v1/link-sessions/lnk_example" \
  -H "Authorization: Bearer <api_token>"
```

Successful result (`data`):

```json
{
  "link_session_id": "lnk_example",
  "state": "success",
  "account_id": "acc_01hqy8k2example",
  "expires_at": "2026-10-20T16:10:00+03:00",
  "remaining_seconds": 480,
  "approval_received": true,
  "account": {
    "id": "acc_01hqy8k2example",
    "name": "Example",
    "email": "wallet@example.com",
    "phone": "...",
    "address": "SHM...",
    "qr_payload": "SHM...",
    "status": "inactive",
    "subscription_expires_at": null
  }
}
```

For `pending`, `account_id` is `null` and `poll_after_seconds` is present. An approval observed before expiry reserves up to **180 seconds** for profile verification; `approval_received: true` means polling should continue even if the scan countdown reaches zero. Terminal success remains readable after QR expiry without contacting ShamCash again. Removing the linked account invalidates the associated sessions.

`502 UPSTREAM_UNAVAILABLE` is a transport failure, not a terminal QR result: retry with backoff. `401` means the API token is invalid or a provider authentication error occurred; inspect `code`. `404 NOT_FOUND` means the session is unknown or belongs to another user.

### `GET /link-sessions/{link_session_id}/qr`

Return the pending session's QR as PNG bytes, using the same owner Bearer token. Responses use `Content-Type: image/png` and `Cache-Control: no-store`. The image encodes the complete payload returned by session creation; no image URL is needed.

```bash
curl --fail "https://api.shamcash-api.com/v1/link-sessions/lnk_example/qr" \
  -H "Authorization: Bearer <api_token>" --output link.png
```

Errors use the usual JSON envelope: `404 NOT_FOUND` for an unknown or other owner's session, `410 LINK_EXPIRED` after its scan deadline, or `409 LINK_QR_UNAVAILABLE` after approval/completion or for an old session without a stored QR.

## Plans and subscriptions

### Customer discounts

Plan `price_usd` is the authenticated owner's price after their subscription discount. `base_price_usd` is the catalog price and `discount_percent` is the owner's discount. Purchase receipts include the same fields. The discount applies to each purchased period and to automatic renewal; replaying a purchase key returns the original receipt.

### `GET /plans`

Returns `data.plans`, an array of active plans. Each contains `id`, `code`, `name`, `price_usd`, `base_price_usd`, `discount_percent`, `compare_price_usd` (nullable), and `duration_days`. Use the returned price and ID rather than hardcoding them.

### `POST /accounts/{account_id}/trial`

Starts the linked account's one-time free trial using the same eligibility and configured duration as the dashboard. No body and no wallet charge. Returns `200 TRIAL_STARTED` with `data.account`. Already-used trials return `409 TRIAL_ALREADY_USED`; an active subscription returns `409 SUBSCRIPTION_ALREADY_ACTIVE`.

### `POST /accounts/{account_id}/subscription`

Subscribe or extend prepaid time. One request charges `periods × price_usd` from the token owner's platform USD wallet. Purchased time starts at the later of now and the current expiry, preserving remaining paid or trial access.

| Field | Location | Required | Description |
|---|---|---|---|
| `Idempotency-Key` | header | yes | A unique purchase key, 1–128 letters, digits, dots, underscores, colons or hyphens. |
| `plan_id` | JSON | no | Plan ID from `/plans`; omit to use the current default plan. |
| `periods` | JSON | no | Integer from 1 to 120, default 1. Three periods of a 30-day plan purchase 90 days. |

```bash
curl -X POST "https://api.shamcash-api.com/v1/accounts/acc_example/subscription" \
  -H "Authorization: Bearer <api_token>" \
  -H "Idempotency-Key: <unique-purchase-key>" \
  -H "Content-Type: application/json" \
  -d '{"plan_id":"plan_example","periods":3}'
```

Returns `200 SUBSCRIPTION_ACTIVATED`, with the updated `account` and purchase details:

```json
{
  "account_id": "acc_example",
  "plan_id": "plan_example",
  "subscription_id": "sub_example",
  "periods": 3,
  "duration_days": 90,
  "price_usd": 2,
  "base_price_usd": 2,
  "discount_percent": 0,
  "charged_usd": 6,
  "wallet_balance_usd": 4,
  "subscription_expires_at": "2027-01-18T16:00:00+03:00",
  "remaining_seconds": 7776000,
  "auto_renew": true
}
```

Use a new key for each intentional purchase. Retry an uncertain purchase using the same key and body to receive its original receipt without another charge. Reusing a key with different account, plan or period parameters returns `409 IDEMPOTENCY_KEY_REUSED`. Missing keys return `400 IDEMPOTENCY_KEY_REQUIRED`; invalid fields return `422 VALIDATION_ERROR`. Purchase keys belong to the platform user and survive API-token rotation.

Insufficient funds return `400 INSUFFICIENT_BALANCE`; unavailable plans return `404 PLAN_NOT_FOUND`. Failed purchases leave wallet and expiry unchanged. Existing auto-renew preferences are preserved. When enabled, auto-renew buys one period using the most recently purchased plan only after all prepaid access expires.

### `PATCH /accounts/{account_id}/subscription`

Set the desired auto-renew value explicitly:

```json
{ "auto_renew": false }
```

Returns `200 AUTO_RENEW_UPDATED` with `account_id`, `auto_renew` and `subscription_expires_at`. Disabling renewal preserves all prepaid time; enabling it does not charge immediately. Repeating the same value is safe.

## Accounts

### `GET /accounts`

Returns every ShamCash account linked to the authenticated user on the platform.

#### Response when `status` is `"success"`

`data` is an **array** of account objects:

```json
{
  "status": "success",
  "code": "SUCCESS",
  "message": "Accounts retrieved successfully.",
  "data": [
    {
      "id": "acc_01hqy8k2example",
      "name": "string",
      "email": "string",
      "phone": "string",
      "address": "SHM...",
      "qr_payload": "SHM...",
      "status": "active",
      "subscription_expires_at": "2026-12-31T23:59:59+03:00"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Stable identifier for this linked account in the API |
| `name` | string | Display name |
| `email` | string | Email on file for this link |
| `phone` | string | Phone on file for this link |
| `address` | string \| null | Plain ShamCash account address. If missing locally, the API tries to fetch and cache it once from ShamCash settings. |
| `qr_payload` | string \| null | Exactly the same plain text value as `address`; never a JSON object. |
| `status` | string | `"active"` - link and subscription allow API use for data endpoints. `"inactive"` - link disabled or not entitled; **`/balances`** and **`/transactions`** return **`SUBSCRIPTION_UNAVAILABLE`** with details in **`message`**. |
| `subscription_expires_at` | string \| null | ISO 8601 instant when the current subscription period ends, in **`Asia/Damascus`** (with offset). `null` before a subscription is activated. |

**Recommended practice:** Treat `status !== "active"` or past `subscription_expires_at` as “cannot use balances/transactions for this account” until a plan is activated or renewed through the API or dashboard.

---

### `GET /accounts/{account_id}`

Returns a single linked account by id. Useful when the integration already knows the id it cares about and does not want to fetch the full list.

#### Response when `status` is `"success"`

`data` is the account object (same fields as in [`GET /accounts`](#get-accounts), returned directly, not wrapped in an array):

```json
{
  "status": "success",
  "code": "SUCCESS",
  "message": "Account retrieved successfully.",
  "data": {
    "id": "acc_01hqy8k2example",
    "name": "string",
    "email": "string",
    "phone": "string",
    "address": "SHM...",
    "qr_payload": "SHM...",
    "status": "active",
    "subscription_expires_at": "2026-12-31T23:59:59+03:00"
  }
}
```

#### Response when `status` is `"error"`

| Case | `code` | HTTP |
|------|--------|------|
| `account_id` is not linked to the authenticated user | `ACCOUNT_NOT_FOUND` | `404` |

```json
{
  "status": "error",
  "code": "ACCOUNT_NOT_FOUND",
  "message": "This account is not linked to your platform user.",
  "data": null
}
```

---

### `DELETE /accounts/{account_id}`

Remove the authenticated user's platform link, stored provider credentials and account cache, and stop future renewal. Billing records are retained. This does **not** delete their actual ShamCash wallet. Unused subscription time is not refunded, matching dashboard removal. Associated completed and pending re-link sessions become `failed`; subsequent account reads return `404 ACCOUNT_NOT_FOUND`.

```bash
curl -X DELETE "https://api.shamcash-api.com/v1/accounts/acc_01hqy8k2example" \
  -H "Authorization: Bearer <api_token>"
```

Returns `200 ACCOUNT_REMOVED` with `data: {"account_id":"acc_01hqy8k2example"}`. Missing or other users' accounts return `404 ACCOUNT_NOT_FOUND`.

## Balances

### `GET /balances`

Returns balance rows for **one** linked account (three currencies when all are present).

#### Query parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | string | **Yes** | Account `id` from `GET /accounts` |

#### Response when `status` is `"success"`

`data` is an object:

```json
{
  "status": "success",
  "code": "SUCCESS",
  "message": "Balances retrieved successfully.",
  "data": {
    "account_id": "acc_01hqy8k2example",
    "balances": [
      {
        "currency": { "id": 1, "code": "USD" },
        "available": 0.0,
        "blocked": 0.0
      }
    ]
  }
}
```

| Field | Description |
|-------|-------------|
| `account_id` | Echo of the requested id |
| `balances` | One entry per currency (`1` USD, `2` SYP, `3` EUR) |
| `balances[].available` | Amount available to spend |
| `balances[].blocked` | Amount blocked or held |

---

## Transactions

### `GET /transactions`

Returns **incoming** (received) transactions for a single linked account, with optional filters.

Query parameters are listed in **logical order** (the order you should document in client code and OpenAPI).

#### Query parameters

| # | Parameter | Type | Required | Description |
|---|-----------|------|----------|-------------|
| 1 | `account_id` | string | **Yes** | Linked account id from `GET /accounts` |
| 2 | `start_at` | string | No | Inclusive lower bound. Date `YYYY-MM-DD` or datetime; **Asia/Damascus** if no offset. |
| 3 | `end_at` | string | No | Inclusive upper bound; same rules as `start_at`. Date-only values include the entire day. Omit for the current time; future values are capped at the current time. |
| 4 | `transaction_ids` | string | No | Comma-separated list of numeric ids, **or** repeat the parameter (`transaction_ids=1&transaction_ids=2`). Only transactions whose ids appear in this list are returned, **after** applying `account_id`, date range, and `coin_id`. See [Lookup by transaction id](#lookup-by-transaction-id). |
| 5 | `coin_id` | integer | No | Currency filter: `1` = USD, `2` = SYP, `3` = EUR. Omit to include all currencies. |
| 6 | `limit` | integer | No | Maximum number of transactions to return. **Default: `20`**. Server may enforce a maximum (e.g. `200`). |

**Filtering behavior**

1. Scope is always the given **`account_id`** for the authenticated user.
2. If **`start_at`** / **`end_at`** are set, keep only rows whose **`occurred_at`** falls in that window (Damascus).
3. If **`coin_id`** is set, keep only that currency.
4. If **`transaction_ids`** is set, keep only rows whose id is in that set (intersection with the above). If **none** of the requested ids exist or match the filters, **`data.transactions`** is an **empty array** - still **`SUCCESS`**, not an error.
5. **`limit`** applies last (e.g. newest first within the filtered set).

Date-only `end_at` includes the entire day. Explicit offsets are converted to
Asia/Damascus before comparison. Invalid dates, reversed ranges, non-positive
transaction IDs, or more than 200 distinct IDs return `422 VALIDATION_ERROR`.
The provider rejected native ISO datetime bounds in live diagnostics; platform
timestamp selection is applied locally after requesting whole-date windows.

Date/ID lookups use the provider's filtered-log endpoint. Requests without
date/ID selection use recent history. If the provider advertises another page
without a usable cursor, repeats a page/cursor, returns an invalid response, or
the SDK traversal budget is exhausted, the API returns `502 UPSTREAM_UNAVAILABLE`
instead of presenting a partial search as successful. A completed search with
no match still returns `SUCCESS` with an empty array. API result limits and SDK
budgets are not claims about the provider's maximum.

#### Lookup by transaction id

When **`transaction_ids`** is provided, the service returns **only** matching incoming transactions that also satisfy `account_id`, dates, and `coin_id`. If **no** id matches, **`data.transactions`** is **`[]`**. This is expected for idempotent “check these ids” workflows.

#### Response when `status` is `"success"`

```json
{
  "status": "success",
  "code": "SUCCESS",
  "message": "Transactions retrieved successfully.",
  "data": {
    "account_id": "acc_01hqy8k2example",
    "transactions": [
      {
        "transaction_id": 184627893,
        "amount": 0.1,
        "currency": { "id": 1, "code": "USD" },
        "occurred_at": "2026-04-16T01:22:21+03:00",
        "receiver_name": "string",
        "sender_name": "string",
        "sender_address": "string",
        "note": ""
      }
    ]
  }
}
```

For **incoming** transfers, **`receiver_name`** is the display name of your linked ShamCash account (the account that received funds). **`sender_name`** is the display name of the other party, and **`sender_address`** is the opaque address identifier returned by the payment network for that party.

| Field | Type | Description |
|-------|------|-------------|
| `transaction_id` | integer | Unique transaction id |
| `amount` | number | Received amount |
| `currency` | object | `{ "id", "code" }` - same as balances |
| `occurred_at` | string | ISO 8601 with offset |
| `receiver_name` | string | Display name of the receiving (linked) account |
| `sender_name` | string | Display name of the sending party |
| `sender_address` | string | Opaque identifier for the sender account |
| `note` | string | Payment note; empty string if none |

---

## Error response example

```json
{
  "status": "error",
  "code": "SUBSCRIPTION_UNAVAILABLE",
  "message": "This account has no active subscription. Purchase or renew a plan on shamcash-api.com to use balances and transactions.",
  "data": null
}
```

Other examples of `message` for the same `code`:

- *"The subscription for this account ended on 2026-01-01. Renew on shamcash-api.com to continue."*
- *"This ShamCash link is inactive. Reactivate it in your dashboard to continue."*
- *"No subscription is associated with this account."*

---
