# Upstream

This service is a **lean fork** of the UCP Python reference merchant server.

| | |
|---|---|
| Repository | https://github.com/Universal-Commerce-Protocol/samples |
| Path | `rest/python/server` |
| Commit | `cdb291c452acf7f1253096b0e1ad7c45ecd4b5c7` (fetched 2026-10-09) |
| Licence | Apache License 2.0 (see the upstream `LICENSE`) |

## What was taken

- `exceptions.py` and `enums.py` → merged into `src/demo_store/ucp/errors.py` (the UCP error
  envelope, error classes and checkout status enum), restyled and extended with AP2 mandate
  error codes. The upstream copyright notice is kept in that file.
- The idempotency and error-envelope *behaviour* (not code) informed
  `src/demo_store/http/middleware.py`.

## Why not a full fork

The upstream server targets UCP spec `2026-04-08` and pins `ucp-sdk>=0.4.6,<0.5`. Our plan pins UCP
**`2026-08-25`** (research R3), which is `ucp-sdk` 0.5.x. Upstream is also built around a flower
shop with discounts, buyer consent, webhooks and RFC 9421 request signing, has no
`catalog.search` / `catalog.lookup`, and no AP2 mandates.

Forking it whole would have meant downgrading the spec version and deleting most of the code. So we
kept the reusable, version-independent parts and wrote the grocery catalogue, checkout,
fulfillment and AP2 pieces against the 2026-08-25 spec. This deviation from plan.md
("fork the sample") is recorded here and in `WORKLOG.md`.
