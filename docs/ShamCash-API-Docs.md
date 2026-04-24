# ShamCash API

HTTP API for ShamCash accounts that users link on [shamcash-api.com](https://shamcash-api.com). A user registers on the platform, links one or more ShamCash accounts to their profile, then uses this API to list those accounts, inspect subscription status, read balances, and query incoming transactions.

**Base URL:** `https://api.shamcash-api.com/v1`

All paths below are relative to that base URL.

---

## Authentication

Every request must include a valid **API token** issued from the platform dashboard.

### Header

```http
Authorization: Bearer <api_token>
```

Tokens are opaque secrets. Treat them like passwords. Do not expose them in client side web code, mobile apps, or public repositories.

If the token is missing, invalid, expired, or revoked, the API returns `status: "error"` with an appropriate `code` and a human readable `message`.

---

## Conventions

### Versioning

The `v1` path segment is the current major version. Breaking changes will be introduced under a new version such as `v2`.

### Content type

Responses use:

```http
Content-Type: application/json; charset=utf-8
```

If request bodies are added to future endpoints, they should use the same content type unless documented otherwise.

### Time zones

For `/transactions`, query parameters such as `start_at` and `end_at` are interpreted in **Asia/Damascus** unless the client sends a full ISO 8601 datetime with an explicit UTC offset.

Transaction objects return `occurred_at` as an ISO 8601 timestamp **with offset**, for example:

```text
2026-04-16T01:22:21+03:00
```

### Account lifecycle

Each item returned by `/accounts` represents a ShamCash account linked to the authenticated platform user.

Each linked account has:

- a `status` of `active` or `inactive`
- an optional `subscription_expires_at`

If the user calls `/balances` or `/transactions` for an account that is inactive, missing a subscription, or past its subscription period, the API returns `SUBSCRIPTION_UNAVAILABLE`.

### Per account rate limit

Account specific read operations are throttled at **6 requests per minute per linked ShamCash account**.

This limit currently applies to:

- `GET /accounts/{account_id}`
- `GET /balances?account_id=...`
- `GET /transactions?account_id=...`

Notes:

- the limit key is the linked ShamCash `account_id`, not the platform user id
- if the limit is exceeded, the API returns `429 RATE_LIMIT_EXCEEDED`
- clients should avoid unnecessary polling and should batch reads sensibly

---

## Response envelope

Every response uses the same top level shape:

```json
{
  "status": "success",
  "code": "SUCCESS",
  "message": "Accounts retrieved successfully.",
  "data": {}
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | `"success"` or `"error"` |
| `code` | string | Machine readable outcome code |
| `message` | string | Human readable summary |
| `data` | mixed | Payload on success, usually `null` on error |

### Success responses

- `status` is `"success"`
- `code` is usually `"SUCCESS"` unless otherwise documented
- `message` briefly describes the successful outcome
- `data` follows the schema documented for that endpoint

### Error responses

- `status` is `"error"`
- `code` is one of the values documented in [Error codes](#error-codes)
- `message` explains the failure in plain language
- `data` is typically `null`

Clients should branch primarily on `code`, use `status` as a coarse success or error signal, and treat `message` as display and logging text.

---

## Error codes

| Code | Typical HTTP | Meaning |
|---|---:|---|
| `SUCCESS` | `200` | Request completed successfully |
| `VALIDATION_ERROR` | `400` | Malformed or conflicting query parameters |
| `AUTH_MISSING` | `401` | Missing `Authorization` header or empty bearer token |
| `AUTH_INVALID` | `401` | Token is invalid, unknown, expired, or revoked |
| `FORBIDDEN` | `403` | Token is valid but not allowed to perform the action |
| `NOT_FOUND` | `404` | Generic not found error |
| `ACCOUNT_NOT_FOUND` | `404` | The requested linked account does not belong to the authenticated user or does not exist |
| `SUBSCRIPTION_UNAVAILABLE` | `403` | The account cannot be used for this operation because it is inactive, missing a subscription, or the subscription has ended |
| `RATE_LIMIT_EXCEEDED` | `429` | Too many requests for the current rate limit window |
| `FETCH_FAILED` | `502` | Upstream or internal data fetch failed |
| `INTERNAL_ERROR` | `500` | Unexpected server error |

Exact HTTP status codes may be tuned per deployment. Client libraries should rely on the response envelope, especially `status`, `code`, `message`, and `data`.

---

## Accounts

### `GET /accounts`

Returns every ShamCash account linked to the authenticated platform user.

### Success response

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
      "status": "active",
      "subscription_expires_at": "2026-12-31T23:59:59+03:00"
    }
  ]
}
```

### Account object

| Field | Type | Description |
|---|---|---|
| `id` | string | Stable linked account identifier |
| `name` | string | Display name |
| `email` | string | Email on file for this linked account |
| `phone` | string | Phone number on file for this linked account |
| `status` | string | `active` or `inactive` |
| `subscription_expires_at` | string \| null | End of the current subscription period as ISO 8601 with offset, or `null` |

### Recommended client behavior

Treat an account as unavailable for `/balances` and `/transactions` when:

- `status != "active"`
- or `subscription_expires_at` exists and is already in the past

---

### `GET /accounts/{account_id}`

Returns a single linked account by id.

This is useful when the client already knows which account it cares about and does not want to fetch the full list.

### Success response

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
    "status": "active",
    "subscription_expires_at": "2026-12-31T23:59:59+03:00"
  }
}
```

### Error response

```json
{
  "status": "error",
  "code": "ACCOUNT_NOT_FOUND",
  "message": "This account is not linked to your platform user.",
  "data": null
}
```

---

## Balances

### `GET /balances`

Returns balance rows for one linked account.

### Query parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `account_id` | string | Yes | Linked account id from `GET /accounts` |

### Success response

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

### Response fields

| Field | Description |
|---|---|
| `account_id` | Echo of the requested linked account id |
| `balances` | One entry per currency |
| `balances[].currency.id` | Currency id: `1` USD, `2` SYP, `3` EUR |
| `balances[].currency.code` | Currency code |
| `balances[].available` | Spendable amount |
| `balances[].blocked` | Held or reserved amount |

### Error behavior

If the account is inactive or not entitled, this endpoint returns `SUBSCRIPTION_UNAVAILABLE`.

---

## Transactions

### `GET /transactions`

Returns **incoming** transactions for one linked account, with optional filters.

### Query parameters

| # | Parameter | Type | Required | Description |
|---:|---|---|---|---|
| 1 | `account_id` | string | Yes | Linked account id from `GET /accounts` |
| 2 | `start_at` | string | No | Inclusive lower bound. `YYYY-MM-DD` or datetime. Assumed Asia or Damascus if no offset is present |
| 3 | `end_at` | string | No | Inclusive upper bound. Same rules as `start_at` |
| 4 | `transaction_ids` | string | No | Comma separated numeric ids, or repeated parameter form |
| 5 | `coin_id` | integer | No | Currency filter: `1` USD, `2` SYP, `3` EUR |
| 6 | `limit` | integer | No | Maximum number of returned rows. Default `20`. Server may enforce a hard maximum such as `200` |

### Filtering behavior

Filtering is applied in this logical order:

1. scope to the requested `account_id`
2. filter by `start_at` and `end_at` when present
3. filter by `coin_id` when present
4. intersect with `transaction_ids` when present
5. apply `limit` last

If `transaction_ids` is provided and none of the requested ids match, the response is still successful and returns:

```json
{
  "transactions": []
}
```

That is expected behavior for idempotent lookup workflows.

### Success response

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

### Transaction object

| Field | Type | Description |
|---|---|---|
| `transaction_id` | integer | Unique transaction id |
| `amount` | number | Received amount |
| `currency` | object | Currency descriptor with `id` and `code` |
| `occurred_at` | string | ISO 8601 timestamp with offset |
| `receiver_name` | string | Display name of the receiving linked account |
| `sender_name` | string | Display name of the sending party |
| `sender_address` | string | Opaque sender identifier returned by the upstream system |
| `note` | string | Payment note, or empty string if none |

### Notes

For incoming transfers:

- `receiver_name` is the linked ShamCash account that received funds
- `sender_name` is the counterparty display name
- `sender_address` is the upstream identifier for the sender

### Error behavior

If the account is inactive or not entitled, this endpoint returns `SUBSCRIPTION_UNAVAILABLE`.

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

Other valid examples of `message` for the same code include:

- `The subscription for this account ended on 2026-01-01. Renew on shamcash-api.com to continue.`
- `This ShamCash link is inactive. Reactivate it in your dashboard to continue.`
- `No subscription is associated with this account.`

---

## Client library notes

If you are building a Python library such as `shamcash`, the recommended flow is:

1. authenticate every request with `Authorization: Bearer <token>`
2. call `GET /accounts`
3. let the caller choose one `account_id`
4. use that `account_id` for `/balances` and `/transactions`
5. treat `SUBSCRIPTION_UNAVAILABLE`, `ACCOUNT_NOT_FOUND`, `AUTH_INVALID`, and `RATE_LIMIT_EXCEEDED` as first class library exceptions or typed error results

A client library should not depend only on HTTP status. It should always parse the JSON envelope and use `status`, `code`, `message`, and `data`.
