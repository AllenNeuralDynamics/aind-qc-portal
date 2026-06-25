# Metadata Auth API

Two-party DocDB upsert flow for apps on `*.allenneuraldynamics.org`.
Each upsert must be approved by **two distinct QC-portal-authenticated users**
who submit byte-for-byte identical payloads.

Base URL (prod): `https://qc.allenneuraldynamics.org`

## Flow

1. Your app redirects the user to `GET /metadata/token` (see below). The QC
   portal verifies the user is logged in and sets a cross-subdomain cookie
   `qc_auth_token` (the token) and `qc_auth_token_expires_at` (unix seconds).
2. Your app reads the cookie via JS, then `POST`s the metadata to
   `/metadata/v1` or `/metadata/v2` with `?auth-token=<token>`.
3. First valid POST returns `{"status":"pending","submissions":1,"required":2,"expires_at":<ts>}`.
4. A second user repeats steps 1–2 with the **same payload**. The second valid
   POST triggers the DocDB upsert and returns `{"status":"submitted", ...}`.

## Endpoints

### `GET /metadata/token`

Query params:

| Param      | Required | Notes                                                          |
| ---------- | -------- | -------------------------------------------------------------- |
| `id`       | yes      | The `_id` of the metadata record to be approved.               |
| `redirect` | yes      | Absolute `https://` URL on `*.allenneuraldynamics.org(-test)`. |

Auth: caller must hold a valid QC-portal OAuth session cookie.

Same-site enforcement: the request must include `Sec-Fetch-Site: same-origin`
or `same-site`, **or** an `Origin`/`Referer` header on the allowed-host list.
Top-level navigations from `*.allenneuraldynamics.org` pages satisfy this
automatically.

`redirect` is sent verbatim in the `Location` response header. **Query strings
and fragments on the supplied `redirect` URL are preserved as-is** — e.g.
`redirect=https://data.allenneuraldynamics.org/x?db=foo&id=bar&endpoint=baz`
will round-trip those query parameters untouched.

Responses:

- `302` → `redirect`. Sets two cookies on `.allenneuraldynamics.org`
  (Secure, SameSite=None, **not** HttpOnly):
  - `qc_auth_token` — the one-time token
  - `qc_auth_token_expires_at` — unix epoch seconds when the token expires
- `400` invalid/missing `id` or `redirect` (must be https + allowed host)
- `401` user not logged in to the QC portal
- `403` request did not come from an allowed AIND subdomain

### `POST /metadata/v1` and `POST /metadata/v2`

Routes to DocDB `v1` and `v2` respectively.

Query params:

| Param        | Required | Notes              |
| ------------ | -------- | ------------------ |
| `auth-token` | yes      | Token from step 1. |

Body: JSON object representing the **full** DocDB record (not a partial patch
or fragment). `_id` and `name` are required by DocDB itself, and `_id` must
match the `id` the token was issued for.

Responses:

- `200` `{"status":"pending","submissions":N,"required":2,"expires_at":<ts>,"body_hash":"<sha256>"}`
  — fewer than 2 distinct users have submitted this exact payload. When at
  least one other pending request exists for the same `_id` with a different
  body, the response additionally includes `"other_pending_hashes":[...]` so
  the UI can warn the second actor that its payload doesn't match a pending
  one (see also `GET /metadata/v{1,2}/pending`).
- `2xx` `{"status":"submitted","docdb_status":<code>,"docdb_response":<body>}`
  — second distinct user; upsert succeeded. Both tokens are consumed.
- Upstream status `{"status":"failed","docdb_status":<code>,...}` — upsert
  failed; tokens are **not** consumed so the second user can retry.
- `400` missing/invalid body or missing `_id`
- `401` missing/unknown/expired token. Body is JSON:
  `{"status":"error","error":"invalid_token","likely_restart":<bool>,"detail":"..."}`
  and the response carries `WWW-Authenticate: Bearer error="invalid_token"`.
  `likely_restart` is `true` when the portal process has been running for less
  than the 72h token TTL — i.e. no token issued by *this* process can have
  expired naturally yet, so an unknown token is most likely the result of a
  restart. The UI should prompt the user to re-validate.
- `403` token's `_id` does not match the body's `_id`
- `409` same user submitting twice while still waiting for a second approver
- `502` DocDB client raised an exception

### `GET /metadata/v1/pending` and `GET /metadata/v2/pending`

Returns the in-flight pending entries for a given `_id` on this DocDB version.
Useful for a second-actor UI to detect payload-hash drift before submitting.

Query params:

| Param | Required | Notes                                |
| ----- | -------- | ------------------------------------ |
| `id`  | yes      | The `_id` to look up pending requests for. |

Responses:

- `200` `{"id":"<_id>","version":"v1|v2","pending":[<entry>,...]}`
  where each `<entry>` is
  `{"version":"v1|v2","id":"<_id>","body_hash":"<sha256>","submissions":<n>,"required":2,"body":<full proposed payload>}`.
- `400` missing `id`

This endpoint does not require an auth-token. **The full proposed body is
public** so reviewers can diff a pending request against the live DocDB record
before approving.

### `GET /metadata/pending`

Returns every in-flight pending entry across both DocDB versions in a single
call. Powers second-actor reviewer queues.

Responses:

- `200` `{"pending":[<entry>, ...]}` — `<entry>` has the same shape as the
  per-id endpoint above (full body included).

No query params; no auth-token required. Public read-only.

Key behavior:

- Requests are coalesced by `(version, _id, sha256(canonical_json(body)))`.
  Key ordering doesn't matter, but any other byte difference produces a
  separate pending request.
- Tokens are bound to `(user, _id)` and expire **72 hours** after issuance.
- Two **distinct** OAuth user identities are required.

## Client snippet

```js
// 1. Send the user off to get a token.
const id = "<record _id>";
const back = location.href;
location.assign(
  `https://qc.allenneuraldynamics.org/metadata/token` +
  `?id=${encodeURIComponent(id)}&redirect=${encodeURIComponent(back)}`
);

// 2. After redirect, read the cookies.
function readCookie(name) {
  return document.cookie.split("; ")
    .find(c => c.startsWith(name + "="))?.split("=")[1];
}
const token = readCookie("qc_auth_token");
const expiresAt = Number(readCookie("qc_auth_token_expires_at")) * 1000; // ms
// Use expiresAt to drive a countdown.

// 3. Submit the metadata.
const r = await fetch(
  `https://qc.allenneuraldynamics.org/metadata/v2?auth-token=${token}`,
  {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(metadata), // must include _id === id
  }
);
const result = await r.json();
// result.status is "pending" or "submitted" (or "failed")
```

## CORS

The `POST /metadata/v{1,2}`, `GET /metadata/v{1,2}/pending`, and
`GET /metadata/token` endpoints emit CORS headers for browser callers. Cross-
origin requests are accepted **only** when the `Origin` header is an `https://`
URL on `*.allenneuraldynamics.org`; anything else (including the matching
`-test.org` domain) is treated as a same-origin / server-side caller and gets
no `Access-Control-Allow-Origin` header (the browser will block the request).

For browsers, the relevant response headers are:

```
Access-Control-Allow-Origin:  <echoed Origin, when allowed>
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Max-Age:       3600
Vary:                         Origin
```

`Content-Type: application/json` POSTs trigger a CORS preflight; the handlers
respond to `OPTIONS` with `204 No Content` when the `Origin` is allowed and
`403` otherwise.

## Notes for integrators

- Send the **identical** payload from both users. The server hashes the
  canonical JSON; differing fields produce separate pending requests. Anything
  non-deterministic upstream (timestamps, list ordering) will cause silent
  divergence — use `GET /metadata/v{1,2}/pending?id=<_id>` before submitting,
  or inspect `other_pending_hashes` on the `pending` POST response, to detect
  this and warn the user.
- The migrate UI **must be served from `*.allenneuraldynamics.org`** for the
  token round-trip to work. The cookies are `Secure; SameSite=None; Domain=
  .allenneuraldynamics.org`, so `http://localhost` (and any non-AIND origin)
  cannot read them. Local-dev against the prod portal is not possible; deploy
  to a `*.allenneuraldynamics.org(-test)` host to test end-to-end.
- `qc_auth_token` is intentionally non-HttpOnly so JS on `data.*` can read it.
  Any XSS on any `*.allenneuraldynamics.org` page can therefore harvest
  tokens; treat the cookie accordingly.
- State is in-memory on the QC portal process. A portal restart invalidates
  all outstanding tokens and pending requests. After a restart, the next POST
  with a previously-issued token returns `401` with
  `{"error":"invalid_token","likely_restart":true,...}` — surface this to the
  user as a re-validation prompt rather than a generic auth failure.
