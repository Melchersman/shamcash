## 1.3.0

- Link or re-link ShamCash accounts with session creation, PNG QR download, polling, and a paced wait helper in both clients.
- Read plan durations and discounted USD prices, buy multiple prepaid periods with a purchase key, set auto-renew, activate a trial, and unlink an account.
- Parse linking and subscription responses into typed models with Decimal prices and UTC dates. Account models now include subscription type, auto-renew, and provider session status.
- Add typed exceptions for management permissions, linking failures, purchase conflicts, insufficient balance, and expired provider sessions. Existing read methods and the async `session=` argument remain supported.
- Validate purchase arguments before sending requests and preserve the server's original receipt on explicit retries. Charges are never retried automatically.
