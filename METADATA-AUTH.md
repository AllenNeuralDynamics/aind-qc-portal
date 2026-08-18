# Metadata Proposals API

Two-party DocDB upsert flow for apps on `*.allenneuraldynamics.org`.

A **proposal** is one user's suggested replacement for a DocDB record. It is
stored server-side the moment it is created and applied when a *second*
authenticated user approves it. Any QC-portal user may approve any proposal
except their own — the rule being enforced is "two distinct people agreed", not
membership of an approver list.

Base URL (prod): `https://qc.allenneuraldynamics.org`

## Flow

1. The app sends the user to `GET /metadata/login?redirect=<current page>` as a
   top-level navigation. The portal establishes a cross-subdomain session and
   sends them straight back.
2. Every later call is a plain credentialed fetch — no tokens, no cookie
   reading. `GET /metadata/me` says who is logged in.
3. The author `POST`s a proposal to `/metadata/proposals`.
4. A different user reviews it in the queue (`GET /metadata/proposals`) and
   `POST`s to `/metadata/proposals/{id}/approve` with the `body_hash` they were
   shown. The portal re-checks the hash, that the reviewer is not the author,
   and that live DocDB still matches the proposal's `base_hash`, then upserts.

## Authentication

### `GET /metadata/login`

Top-level navigation target — not a fetch.

| Param      | Required | Notes                                                          |
| ---------- | -------- | -------------------------------------------------------------- |
| `redirect` | yes      | Absolute `https://` URL on `*.allenneuraldynamics.org(-test)`. |

If the caller has no QC-portal OAuth session, they are redirected to the
portal's own `/login?next=…` and land back here afterwards — a login round trip
never strands the user on the portal.

Same-site enforcement: the request must carry `Sec-Fetch-Site` of
`same-origin`, `same-site` or `none` (a typed URL or bookmark, which an attacker
page cannot forge), **or** an `Origin`/`Referer` on the allowed-host list.

Responses:

- `302` → `redirect`, setting `aind_metadata_session` on
  `.allenneuraldynamics.org` (`Secure; SameSite=None; **HttpOnly**`, 3 days).
  The cookie is signed with the portal's cookie secret and carries no
  server-side state, so it survives a portal restart. JavaScript never reads it
  — with `SameSite=None` the browser attaches it to credentialed cross-origin
  fetches on its own.
- `400` missing/invalid `redirect`
- `403` request did not come from an allowed AIND subdomain

### `GET /metadata/me`

- `200` `{"authenticated": true, "user": "<user>"}`
- `401` `{"status":"error","error":"not_authenticated"}`

### `POST /metadata/logout`

Clears the session cookie. Does not touch the QC-portal OAuth session.

## Proposals

Every error response is JSON of the form
`{"status":"error","error":"<machine-readable code>","detail":"…"}` — the API
never returns an HTML error page.

### `GET /metadata/proposals`

The review queue. **Public** — proposed bodies are readable by anyone so a
change can be inspected before it lands.

| Param     | Default | Notes                                                      |
| --------- | ------- | ---------------------------------------------------------- |
| `status`  | `open`  | One status, a comma-separated list, or `all`.               |
| `version` | —       | `v1` or `v2`.                                               |
| `id`      | —       | Restrict to one record `_id`.                               |

`200` `{"proposals": [<proposal>, …]}`, newest first.

### `POST /metadata/proposals`

Create a proposal. Requires a session.

```json
{
  "version": "v2",
  "id": "<_id>",
  "body": { "_id": "<_id>", "name": "…", "...": "full replacement record" },
  "note": "optional free text",
  "supersedes": "optional proposal_id being rebased"
}
```

The server reads the live record itself and stores it as the proposal's
`base`, so review always diffs against a server-observed starting point rather
than whatever the client happened to have loaded.

- `201` `{"proposal": <proposal>}`
- `400` `invalid_version` · `invalid_body` · `missing_id` · `id_mismatch` ·
  `no_changes` (the body is identical to the live record)
- `401` `not_authenticated`
- `403` `origin_not_allowed`
- `404` `record_not_found` · `supersedes_not_found`
- `409` `duplicate_proposal` (an identical open proposal exists; the response
  carries its `proposal_id`) · `supersedes_not_open`
- `502` `docdb_unavailable` · `store_unavailable`

### `GET /metadata/proposals/{proposal_id}`

`200` `{"proposal": <proposal>}` · `404` `proposal_not_found`. Public.

### `DELETE /metadata/proposals/{proposal_id}`

Withdraw an open proposal. Author only.

`200` `{"proposal": …}` · `403` `not_author` · `409` `not_open`

### `POST /metadata/proposals/{proposal_id}/approve`

Body: `{"body_hash": "<the hash you reviewed>"}`. Requires a session.

- `200` `{"status":"applied","proposal": <proposal>}`
- `400` `missing_body_hash`
- `403` `self_approval` — the author cannot approve their own proposal
- `409` `not_open` · `hash_mismatch` (the proposal changed since you loaded it)
- `409` `base_drift` — DocDB moved after the proposal was made. The response
  carries `current` (the live record) and `current_hash`; rebase and review
  again rather than clobbering the newer record.
- `502` `{"status":"failed","docdb_status":…}` — the upsert failed; the
  proposal stays **open** so it can be retried.

### `POST /metadata/proposals/{proposal_id}/reject`

Body: `{"reason": "…"}`. Requires a session. `200` `{"proposal": …}`.

## Proposal shape

```json
{
  "proposal_id":   "<uuid4>",
  "version":       "v1|v2",
  "record_id":     "<_id>",
  "record_name":   "<name>",
  "body":          { },
  "body_hash":     "<sha256 of canonical body>",
  "base":          { },
  "base_hash":     "<sha256 of canonical base>",
  "note":          "",
  "author":        "<user>",
  "created_at":    "<ISO-8601 UTC>",
  "status":        "open|applied|rejected|withdrawn|superseded",
  "reviewer":      null,
  "reviewed_at":   null,
  "reason":        null,
  "supersedes":    null,
  "superseded_by": null,
  "docdb_status":  null,
  "docdb_response": null
}
```

Hashes are `sha256` over key-sorted, whitespace-free JSON, so key ordering does
not matter.

## Storage

Proposals live in S3 (`aind-scratch-data`, prefix `metadata-proposals/`), one
object per proposal, rewritten in place on each status transition. Override
with `METADATA_PROPOSALS_BUCKET` / `METADATA_PROPOSALS_PREFIX`. Nothing about a
proposal is held in process memory, so restarts and redeploys are invisible to
users, and applied/rejected proposals remain as an audit trail.

## CORS

`/metadata/*` emits CORS headers for browser callers. Cross-origin requests are
accepted **only** when the `Origin` header is an `https://` URL on
`*.allenneuraldynamics.org`; anything else (including the matching `-test.org`
domain) gets no `Access-Control-Allow-Origin` header and the browser blocks the
request. State-changing methods additionally re-check `Origin` on the request
itself, so a form-style POST that skips the preflight cannot ride the
`SameSite=None` session cookie.

```
Access-Control-Allow-Origin:  <echoed Origin, when allowed>
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Max-Age:       3600
Vary:                         Origin
```

## Client snippet

```js
const QC = "https://qc.allenneuraldynamics.org";

// 1. Who am I? (null when logged out)
const me = await fetch(`${QC}/metadata/me`, { credentials: "include" })
  .then((r) => (r.ok ? r.json() : null));

// 2. Log in — a top-level navigation that returns to this page.
if (!me) {
  location.assign(
    `${QC}/metadata/login?redirect=${encodeURIComponent(location.href)}`
  );
}

// 3. Propose a change.
const { proposal } = await fetch(`${QC}/metadata/proposals`, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ version: "v2", id: record._id, body: record, note: "" }),
}).then((r) => r.json());

// 4. A different user approves it.
await fetch(`${QC}/metadata/proposals/${proposal.proposal_id}/approve`, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ body_hash: proposal.body_hash }),
});
```

## Notes for integrators

- The UI **must be served from `*.allenneuraldynamics.org`**. The session cookie
  is `Secure; SameSite=None; Domain=.allenneuraldynamics.org`, so
  `http://localhost` cannot participate; deploy to a
  `*.allenneuraldynamics.org(-test)` host to test end-to-end.
- Send the reviewer the `body_hash` you displayed, not one you recomputed from a
  fresh fetch. That is what makes "approved" mean "approved *this*".
- A `base_drift` 409 is not an error to retry — it means the record changed. Show
  the user the returned `current` record and let them rebase (create a new
  proposal with `supersedes` set to the stale one).
