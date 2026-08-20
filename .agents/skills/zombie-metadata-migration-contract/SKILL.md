---
name: zombie-metadata-migration-contract
description: Safely evolve the QC Portal metadata proposal API in relation to Zombie's legacy migration client.
---

# Zombie metadata migration contract

The current QC Portal plugin exposes cross-domain session routes `/metadata/login`, `/metadata/logout`, `/metadata/me`, proposal routes `/metadata/proposals` and `/metadata/proposals/<id>`, and `/metadata/proposals/<id>/approve` or `/reject`. Proposals carry a version (`v1` or `v2`), id, body, optional note, and optional supersedes value; approval snapshots live DocDB, checks the canonical/base and body hashes, requires a different user, and then upserts. Preserve JSON errors with `status: 'error'` and the trusted-origin credentialed session cookie.

Zombie's current `web/src/migrate/` client still targets a different deployed legacy API: `/metadata/token`, `/metadata/pending`, and POST `/metadata/v1` or `/metadata/v2?auth-token=...`, with `qc_auth_token` cookies and DocDB polling. These paths are not present in the current plugin source. Treat the mismatch as a release/deployment contract, not a client-side typo: first identify which QC Portal deployment Zombie must use, then update both sides or preserve a compatibility adapter. Do not silently remove the token flow or make the proposal API accept legacy mutations without its two-party approval rules.

Test proposal listing, body/base-hash conflict handling, same-user approval rejection, approve/reject transitions, session expiry, and JSON error envelopes with the existing QC Portal test patches. Add a focused compatibility test before changing any route consumed by Zombie.
