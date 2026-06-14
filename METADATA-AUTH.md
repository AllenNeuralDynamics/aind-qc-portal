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

Body: JSON object representing the full metadata record. Must include `_id`,
which must match the `id` the token was issued for.

Responses:

- `200` `{"status":"pending","submissions":N,"required":2,"expires_at":<ts>}`
  — fewer than 2 distinct users have submitted this exact payload.
- `2xx` `{"status":"submitted","docdb_status":<code>,"docdb_response":<body>}`
  — second distinct user; upsert succeeded. Both tokens are consumed.
- Upstream status `{"status":"failed","docdb_status":<code>,...}` — upsert
  failed; tokens are **not** consumed so the second user can retry.
- `400` missing/invalid body or missing `_id`
- `401` missing/unknown/expired token
- `403` token's `_id` does not match the body's `_id`
- `409` same user submitting twice while still waiting for a second approver
- `502` DocDB client raised an exception

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

## Notes for integrators

- Send the **identical** payload from both users. The server hashes the
  canonical JSON; differing fields produce separate pending requests.
- `qc_auth_token` is intentionally non-HttpOnly so JS on `data.*` can read it.
  Any XSS on any `*.allenneuraldynamics.org` page can therefore harvest
  tokens; treat the cookie accordingly.
- State is in-memory on the QC portal process. A portal restart invalidates
  all outstanding tokens and pending requests.
