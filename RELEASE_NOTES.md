## 1.3.0

- Link or re-link ShamCash accounts with session creation, PNG QR download, polling, and a paced wait helper in both clients.
- Read plan durations and discounted USD prices, buy multiple prepaid periods with a purchase key, set auto-renew, activate a trial, and unlink an account.
- Parse linking and subscription responses into typed models with Decimal prices and UTC dates. Account models now include subscription type, auto-renew, and provider session status.
- Add typed exceptions for management permissions, linking failures, purchase conflicts, insufficient balance, and expired provider sessions. Existing read methods and the async `session=` argument remain supported.
- Validate purchase arguments before sending requests and preserve the server's original receipt on explicit retries. Charges are never retried automatically.
# 1.3.1

Documentation and package metadata update. The client API and runtime behavior are unchanged.

- Set the package homepage to https://shamcash-api.com and documentation to the public English API reference.
- Add direct links to Arabic and English Python guides, payment integration guidance, source and issue tracking.
- Clarify that the SDK belongs to the independent ShamCash API platform and is not published by the wallet operator.
- Update the package contact address to api.shamcash@gmail.com.

