"""Plugin file for custom Panel server endpoints"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

from aind_data_access_api.document_db import MetadataDbClient
from panel.config import config as panel_config
from tornado.web import HTTPError, RequestHandler

from aind_qc_portal.metadata_proposals import (
    canonical_hash,
    get_proposal,
    list_proposals,
    new_proposal,
    put_proposal,
)
from aind_qc_portal.view_contents.data_utils import upload_temporary_metadata
from aind_qc_portal.view_contents.panels.media.utils import clean_reference_prefix, get_s3_url

_logger = logging.getLogger(__name__)

# The QC submit API (`QcSubmitHandler` below) is isolated from the rest of
# the app: a failure importing its module — a missing dependency, a bug in
# qc_edit.py — must not prevent the whole Panel/Tornado app from starting.
# Every existing route (Panel, /metadata/*, media, etc.) has to keep working
# even if this import fails, so the failure is caught here and the handler
# checks `_QC_EDIT_IMPORT_ERROR` before touching any of these names.
try:
    from aind_qc_portal.qc_edit import (
        MISSING,
        QcEditError,
        apply_qc_changes,
        is_qc_hash,
        qc_hash,
        update_qc_record,
    )

    _QC_EDIT_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - defensive; see QcSubmitHandler.
    _logger.exception("QC edit module failed to import; /api/qc/submit will return 503")
    _QC_EDIT_IMPORT_ERROR = exc


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


_docdb_client = MetadataDbClient(
    host="api.allenneuraldynamics.org",
    version="v2",
)

DOCDB_HOST = "api.allenneuraldynamics.org"
DOCDB_VERSIONS = ("v1", "v2")

# Cross-subdomain session issued by /metadata/login. HttpOnly is possible —
# and correct — because no JavaScript ever needs to read it: SameSite=None
# means the browser attaches it to credentialed fetches from data.* and the
# portal reads it server-side. Signed with Panel's cookie secret, so it is
# stateless and survives a portal restart.
SESSION_COOKIE_NAME = "aind_metadata_session"
SESSION_COOKIE_DOMAIN = ".allenneuraldynamics.org"
SESSION_TTL_DAYS = 3

# Where an unauthenticated caller is sent to establish a Panel OAuth session.
PANEL_LOGIN_PATH = "/login"

ALLOWED_HOST_SUFFIXES = (
    ".allenneuraldynamics.org",
    ".allenneuraldynamics-test.org",
)
ALLOWED_CORS_SUFFIXES = (".allenneuraldynamics.org",)
CORS_MAX_AGE_SECONDS = 3600
QC_API_DEFAULT_ORIGINS = (
    "https://data.allenneuraldynamics.org",
    "http://localhost:5173",
)
QC_API_MAX_BODY_BYTES = 256 * 1024
QC_API_DEFAULT_TENANT_ID = "32669cd6-737f-4b39-8bdd-d6951120d3fc"
QC_API_DEFAULT_CLIENT_ID = "a625f758-ee73-4fc0-8a4b-b7467f33d68c"
_BEARER_RE = re.compile(r"^Bearer\s+(\S+)$")
_jwks_clients = {}


def _panel_user_from_handler(handler: RequestHandler) -> str | None:
    """Return the Panel OAuth user name from the request's secure cookie."""
    raw = handler.get_secure_cookie("user", max_age_days=panel_config.oauth_expiry)
    if not raw:
        return None
    try:
        user = raw.decode("utf-8")
    except Exception:
        return None
    if user in ("", "guest"):
        return None
    return user


def _session_user(handler: RequestHandler) -> str | None:
    """Return the user carried by our cross-subdomain session cookie, if any."""
    raw = handler.get_secure_cookie(SESSION_COOKIE_NAME, max_age_days=SESSION_TTL_DAYS)
    if not raw:
        return None
    try:
        user = raw.decode("utf-8")
    except Exception:
        return None
    return user or None


def _host_allowed(host: str | None) -> bool:
    """Return True if `host` is an allowed AIND host."""
    if not host:
        return False
    host = host.split(":", 1)[0].lower()
    return any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES)


def _validate_redirect(url: str | None) -> str:
    """Return `url` if it is an https URL pointing at an allowed AIND host, else raise 400."""
    if not url:
        raise HTTPError(400, "Missing required query parameter: redirect")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPError(400, "redirect must be an absolute https URL.")
    if not _host_allowed(parsed.hostname):
        raise HTTPError(400, "redirect host is not on the allowed list.")
    return url


def _enforce_same_site_request(handler: RequestHandler) -> None:
    """Reject the request unless it clearly originates from an allowed AIND host.

    Defends against CSRF. Accepts the request when either:
      * `Sec-Fetch-Site` is `same-origin`, `same-site`, or `none` (a user-typed
        URL or bookmark, which an attacker page cannot forge), OR
      * `Origin` or `Referer` host is on the allowlist.
    Rejects when no trustworthy signal is present (e.g. attacker-controlled page
    with `Referrer-Policy: no-referrer`).
    """
    sec_fetch_site = handler.request.headers.get("Sec-Fetch-Site")
    if sec_fetch_site in ("same-origin", "same-site", "none"):
        return
    if sec_fetch_site == "cross-site":
        raise HTTPError(403, "Cross-site requests are not permitted on this endpoint.")

    origin = handler.request.headers.get("Origin")
    if origin:
        if _host_allowed(urlparse(origin).hostname):
            return
        raise HTTPError(403, "Origin is not on the allowed list.")

    referer = handler.request.headers.get("Referer")
    if referer and _host_allowed(urlparse(referer).hostname):
        return

    raise HTTPError(403, "Request must originate from an allowed AIND subdomain.")


class UploadMetadataHandler(RequestHandler):
    """Request handler for uploading metadata"""

    def post(self):
        """Handle POST requests to upload metadata"""
        try:
            # Parse JSON from request body
            if self.request.body:
                metadata = json.loads(self.request.body)
            else:
                metadata = None

            if not metadata:
                raise HTTPError(400, "No metadata provided.")

            upload_temporary_metadata(metadata)
            status_code = 200  # Temporary success status
            self.set_header("Content-Type", "application/json")
            self.write({"status": status_code})
        except json.JSONDecodeError:
            raise HTTPError(400, "Invalid JSON in request body.")
        except Exception as e:
            raise HTTPError(500, f"Failed to upload metadata: {str(e)}")


class GetSignedReferenceHandler(RequestHandler):
    """Request handler for returning a pre-signed S3 URL for a validated metric reference"""

    def set_default_headers(self):
        """Set permissive CORS headers for public access."""
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def options(self, asset_name):
        """Handle CORS preflight requests."""
        self.set_status(204)
        self.finish()

    def get(self, asset_name):
        """Handle GET requests to validate and sign a metric reference"""
        reference = self.get_argument("reference", None)

        if not reference:
            raise HTTPError(400, "Missing required query parameter: reference")

        records = _docdb_client.retrieve_docdb_records(
            filter_query={"name": asset_name},
            projection={"quality_control": 1, "name": 1, "location": 1},
        )

        if not records:
            raise HTTPError(404, f"Asset '{asset_name}' not found.")

        record = records[0]
        quality_control = record.get("quality_control", {})
        metrics = quality_control.get("metrics", [])

        reference_found = any(
            metric.get("reference") == reference
            for metric in metrics
            if metric.get("reference") is not None
        )

        if not reference_found:
            raise HTTPError(403, f"Reference '{reference}' is not associated with any metric in asset '{asset_name}'.")

        if "s3" in reference:
            bucket = reference.split("/")[2]
            key = "/".join(reference.split("/")[3:])
        else:
            location = record.get("location", "")
            if not location.startswith("s3://"):
                raise HTTPError(500, f"Asset location '{location}' is not an s3:// URI.")
            parts = location.split("/")
            bucket = parts[2]
            prefix = "/".join(parts[3:])
            key = str(Path(prefix) / clean_reference_prefix(reference))

        url = get_s3_url(bucket, key)
        if not url:
            raise HTTPError(500, "Failed to generate pre-signed URL.")

        self.set_header("Content-Type", "application/json")
        self.write({"url": url})


def _origin_is_allowed(origin: str) -> bool:
    """Return True if `origin` is a scheme://host[:port] on an allowed AIND host."""
    if not origin:
        return False
    parsed = urlparse(origin)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in ALLOWED_CORS_SUFFIXES)


class _MetadataApiHandler(RequestHandler):
    """Base for every `/metadata/*` API handler.

    Provides CORS for trusted AIND subdomains, JSON error bodies (Tornado's
    default error page is HTML, which browser clients cannot act on), and the
    session/CSRF helpers the proposal endpoints share.
    """

    def set_default_headers(self):
        """Apply CORS headers when the caller is a trusted AIND subdomain."""
        origin = self.request.headers.get("Origin", "")
        if _origin_is_allowed(origin):
            self.set_header("Access-Control-Allow-Origin", origin)
            self.set_header("Access-Control-Allow-Credentials", "true")
            self.set_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.set_header("Access-Control-Max-Age", str(CORS_MAX_AGE_SECONDS))
        self.set_header("Vary", "Origin")

    def options(self, *args, **kwargs):
        """Answer CORS preflights: 204 for allowed origins, 403 otherwise."""
        origin = self.request.headers.get("Origin", "")
        if not _origin_is_allowed(origin):
            self.set_status(403)
            self.finish()
            return
        self.set_status(204)
        self.finish()

    def write_error(self, status_code: int, **kwargs):
        """Emit errors as JSON so clients never have to parse an HTML page."""
        reason = self._reason
        exc_info = kwargs.get("exc_info")
        if exc_info and isinstance(exc_info[1], HTTPError) and exc_info[1].log_message:
            reason = exc_info[1].log_message
        self.set_header("Content-Type", "application/json")
        self.finish({"status": "error", "error": reason})

    def fail(self, status_code: int, error: str, **extra):
        """Write a structured JSON error and finish the request."""
        self.set_status(status_code)
        self.set_header("Content-Type", "application/json")
        self.finish({"status": "error", "error": error, **extra})

    def write_json(self, payload: dict, status_code: int = 200):
        """Write `payload` as JSON with `status_code`."""
        self.set_status(status_code)
        self.set_header("Content-Type", "application/json")
        self.write(payload)

    def require_user(self) -> str | None:
        """Return the session user, or write a 401 and return None."""
        user = _session_user(self)
        if not user:
            self.fail(401, "not_authenticated", detail="Log in via GET /metadata/login first.")
            return None
        return user

    def require_write_origin(self) -> bool:
        """Reject state-changing requests that did not come from an AIND page.

        The session cookie is `SameSite=None`, so the browser would attach it
        to a cross-site request too. A JSON POST triggers a CORS preflight that
        we already reject, but a simple request (`text/plain` form post) does
        not — so the origin is checked on the request itself as well.
        """
        origin = self.request.headers.get("Origin")
        if origin:
            if _origin_is_allowed(origin):
                return True
            self.fail(403, "origin_not_allowed")
            return False
        if self.request.headers.get("Sec-Fetch-Site") in ("same-origin", "none", None):
            return True
        self.fail(403, "origin_not_allowed")
        return False

    def json_body(self) -> dict | None:
        """Parse the request body as a JSON object, or write a 400 and return None."""
        if not self.request.body:
            self.fail(400, "missing_body")
            return None
        try:
            parsed = json.loads(self.request.body)
        except json.JSONDecodeError:
            self.fail(400, "invalid_json")
            return None
        if not isinstance(parsed, dict):
            self.fail(400, "invalid_json", detail="Request body must be a JSON object.")
            return None
        return parsed


class MetadataLoginHandler(_MetadataApiHandler):
    """GET /metadata/login?redirect=<url>

    Top-level navigation target. Establishes the cross-subdomain session from
    the caller's Panel OAuth session, then bounces straight back to the page
    they came from — so a login round trip never strands the user on the QC
    portal. If they are not logged in to the portal yet, they are sent through
    Panel's own login first and land back here afterwards.
    """

    def get(self):
        """Establish the cross-subdomain session, then return to `redirect`."""
        redirect = _validate_redirect(self.get_argument("redirect", None))
        _enforce_same_site_request(self)

        user = _panel_user_from_handler(self)
        if not user:
            here = self.request.uri
            self.redirect(f"{PANEL_LOGIN_PATH}?{urlencode({'next': here})}")
            return

        self.set_secure_cookie(
            SESSION_COOKIE_NAME,
            user,
            domain=SESSION_COOKIE_DOMAIN,
            path="/",
            secure=True,
            samesite="None",
            httponly=True,
            expires_days=SESSION_TTL_DAYS,
        )
        self.redirect(redirect)


class MetadataLogoutHandler(_MetadataApiHandler):
    """POST /metadata/logout — clear the cross-subdomain session cookie.

    Does not touch the Panel OAuth session; the user stays logged in to the QC
    portal itself.
    """

    def post(self):
        """Clear the session cookie."""
        if not self.require_write_origin():
            return
        self.clear_cookie(
            SESSION_COOKIE_NAME,
            domain=SESSION_COOKIE_DOMAIN,
            path="/",
            secure=True,
            samesite="None",
        )
        self.write_json({"authenticated": False})


class MetadataMeHandler(_MetadataApiHandler):
    """GET /metadata/me — who the caller is, for rendering login state."""

    def get(self):
        """Return the caller's identity, or 401 when there is no session."""
        user = _session_user(self)
        if not user:
            self.fail(401, "not_authenticated")
            return
        self.write_json({"authenticated": True, "user": user})


def _qc_api_config() -> dict:
    """Read server-only QC API configuration from the deployment environment."""
    tenant = os.environ.get("QC_API_TENANT_ID", "").strip() or QC_API_DEFAULT_TENANT_ID
    issuer = os.environ.get("QC_API_ISSUER", "").strip()
    if not issuer and tenant:
        issuer = f"https://login.microsoftonline.com/{tenant}/v2.0"
    origins = tuple(
        value.strip()
        for value in os.environ.get("QC_API_ALLOWED_ORIGINS", ",".join(QC_API_DEFAULT_ORIGINS)).split(",")
        if value.strip()
    )
    return {
        "enabled": os.environ.get("QC_API_ENABLED", "true").lower() in {"1", "true", "yes"},
        "issuer": issuer,
        # The browser signs users into the existing Entra app.  Its ID token is
        # accepted only when it was issued by this tenant for this client.
        "audience": os.environ.get("QC_API_AUDIENCE", "").strip()
        or os.environ.get("QC_API_CLIENT_ID", "").strip()
        or QC_API_DEFAULT_CLIENT_ID,
        "jwks_url": os.environ.get("QC_API_JWKS_URL", "").strip()
        or (f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys" if tenant else ""),
        "origins": origins,
    }


def _qc_origin_allowed(origin: str, config: dict) -> bool:
    """Return True only for an exact configured browser origin."""
    return bool(origin) and origin in config["origins"]


def _verified_qc_actor(token: str, config: dict) -> str:
    """Validate an Entra ID token and return its server-verified actor.

    Tenant membership is the authorization boundary for the inline editor:
    there is intentionally no application-specific scope or role check here.
    Audience and issuer validation still prevent a token issued for another
    Entra tenant or application from being used for QC writes.
    """
    if not config["issuer"] or not config["audience"] or not config["jwks_url"]:
        raise RuntimeError("QC API JWT configuration is incomplete")
    try:
        import jwt
        from jwt import PyJWKClient

        jwks_client = _jwks_clients.get(config["jwks_url"])
        if jwks_client is None:
            jwks_client = PyJWKClient(config["jwks_url"], cache_jwk_set=True, lifespan=3600)
            _jwks_clients[config["jwks_url"]] = jwks_client
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=config["audience"],
            issuer=config["issuer"],
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except Exception as exc:
        raise ValueError("Invalid QC identity token") from exc

    stable_identity = claims.get("oid") or claims.get("sub")
    actor = claims.get("preferred_username") or claims.get("email") or claims.get("upn") or stable_identity
    if not stable_identity:
        raise ValueError("QC API token has no usable identity")
    return str(actor)


class QcSubmitHandler(RequestHandler):
    """POST /api/qc/submit — tenant-authenticated bearer-token QC edit endpoint."""

    def set_default_headers(self):
        """Set CORS headers for the QC API only."""
        correlation_id = self.request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        self._correlation_id = correlation_id[:128]
        self.set_header("X-Correlation-ID", self._correlation_id)
        config = _qc_api_config()
        origin = self.request.headers.get("Origin", "")
        if _qc_origin_allowed(origin, config):
            self.set_header("Access-Control-Allow-Origin", origin)
            self.set_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.set_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.set_header("Access-Control-Max-Age", str(CORS_MAX_AGE_SECONDS))
        self.set_header("Vary", "Origin")
        self.set_header("Cache-Control", "no-store")

    def write_error(self, status_code: int, **kwargs):
        """Emit a small JSON error without Tornado internals."""
        self.set_status(status_code)
        self.set_header("Content-Type", "application/json")
        self.finish({"status": "error", "error": "request_failed"})

    def options(self):
        """Answer only exact allowed-origin preflights."""
        if not _qc_origin_allowed(self.request.headers.get("Origin", ""), _qc_api_config()):
            self.set_status(403)
            self.finish({"status": "error", "error": "origin_not_allowed"})
            return
        self.set_status(204)
        self.finish()

    def post(self):  # noqa: C901
        """Authenticate, validate, conditionally mutate, and respond."""
        if _QC_EDIT_IMPORT_ERROR is not None:
            self._fail(503, "qc_api_unavailable")
            return
        config = _qc_api_config()
        origin = self.request.headers.get("Origin", "")
        if not config["enabled"]:
            self._fail(503, "qc_api_disabled")
            return
        if not _qc_origin_allowed(origin, config):
            self._fail(403, "origin_not_allowed")
            return
        if len(self.request.body) > QC_API_MAX_BODY_BYTES:
            self._fail(400, "request_too_large")
            return
        if not self.request.headers.get("Content-Type", "").lower().startswith("application/json"):
            self._fail(400, "content_type_required")
            return

        match = _BEARER_RE.match(self.request.headers.get("Authorization", ""))
        if not match:
            self._fail(401, "unauthenticated")
            return
        try:
            actor = _verified_qc_actor(match.group(1), config)
        except (ValueError, RuntimeError):
            self._fail(401, "unauthenticated")
            return

        try:
            payload = json.loads(self.request.body)
        except (TypeError, json.JSONDecodeError):
            self._fail(400, "malformed_request")
            return
        if not isinstance(payload, dict):
            self._fail(400, "malformed_request")
            return
        unknown = set(payload) - {"record_id", "expected_qc_hash", "changes", "notes"}
        if unknown:
            self._fail(400, "unsupported_request_field")
            return
        record_id = payload.get("record_id")
        expected_hash = payload.get("expected_qc_hash")
        changes = payload.get("changes")
        if not isinstance(record_id, str) or not record_id or len(record_id) > 256:
            self._fail(400, "record_id_required")
            return
        if not is_qc_hash(expected_hash):
            self._fail(400, "invalid_expected_qc_hash")
            return
        if not isinstance(changes, list) or (not changes and "notes" not in payload):
            self._fail(400, "no_changes")
            return
        if "notes" in payload and not isinstance(payload["notes"], str):
            self._fail(400, "invalid_notes")
            return

        try:
            record = _fetch_live_record("v2", record_id)
        except Exception:
            _logger.exception(
                "QC API DocDB read failed",
                extra={"record_id": record_id, "correlation_id": self._correlation_id},
            )
            self._fail(502, "docdb_unavailable")
            return
        if record is None:
            self._fail(404, "record_not_found")
            return
        current_qc = record.get("quality_control")
        if qc_hash(current_qc) != expected_hash:
            self._fail(409, "stale_record", detail="The QC record changed. Reload and review again.")
            return
        try:
            new_record = apply_qc_changes(
                record,
                changes,
                actor=actor,
                notes=payload.get("notes", MISSING),
            )
        except QcEditError as exc:
            message = str(exc)
            status = 422 if "schema validation" in message else 400
            self._fail(status, "invalid_qc_data" if status == 422 else "malformed_request")
            return

        if not changes and new_record["quality_control"] == current_qc:
            self._fail(400, "no_changes")
            return
        try:
            response = update_qc_record(
                _docdb_client_for("v2"),
                record_id,
                new_record["quality_control"],
            )
        except Exception:
            _logger.exception(
                "QC API DocDB conditional write failed",
                extra={"record_id": record_id, "correlation_id": self._correlation_id},
            )
            self._fail(502, "docdb_unavailable")
            return

        asset_name = record.get("name", "")
        _logger.info(
            "QC API edit applied",
            extra={
                "record_id": record_id,
                "asset_name": asset_name,
                "actor": actor,
                "changed_metrics": len(changes),
                "correlation_id": self._correlation_id,
                "result": "applied",
            },
        )
        self.set_status(200)
        self.set_header("Content-Type", "application/json")
        self.write(
            {
                "status": "applied",
                "record_id": record_id,
                "asset_name": asset_name,
                "actor": actor,
                "changed_metrics": len(changes),
                "docdb_status": getattr(response, "status_code", 200),
            }
        )

    def _fail(self, status_code: int, error: str, **extra):
        """Write a structured QC API error."""
        self.set_status(status_code)
        self.set_header("Content-Type", "application/json")
        self.finish({"status": "error", "error": error, **extra})


def _docdb_client_for(version: str) -> MetadataDbClient:
    """Return a DocDB client for `version` ('v1' or 'v2')."""
    return MetadataDbClient(host=DOCDB_HOST, version=version)


def _fetch_live_record(version: str, record_id: str) -> dict | None:
    """Return the current DocDB record for `record_id`, or None if absent."""
    records = _docdb_client_for(version).retrieve_docdb_records(
        filter_query={"_id": str(record_id)},
        limit=1,
    )
    return records[0] if records else None


class MetadataProposalsHandler(_MetadataApiHandler):
    """`/metadata/proposals`

    GET — the review queue. Public: proposed bodies are readable by anyone so a
    change can be inspected before it lands. Query params: `status` (default
    `open`, accepts a comma-separated list or `all`), `version`, `id`.

    POST — create a proposal. Requires a session. Body::

        {"version": "v1"|"v2", "id": "<_id>", "body": {...},
         "note": "<optional>", "supersedes": "<optional proposal_id>"}

    The server snapshots the live DocDB record itself and stores it as the
    proposal's `base`, so review always diffs against a server-observed
    starting point rather than whatever the client happened to have loaded.
    """

    def get(self):
        """Return the review queue."""
        status = self.get_argument("status", "open")
        version = self.get_argument("version", None)
        record_id = self.get_argument("id", None)
        if version and version not in DOCDB_VERSIONS:
            self.fail(400, "invalid_version")
            return
        try:
            proposals = list_proposals(status=status, version=version, record_id=record_id)
        except Exception as e:  # pragma: no cover - S3 failures
            _logger.exception("Failed to list metadata proposals")
            self.fail(502, "store_unavailable", detail=str(e))
            return
        self.write_json({"proposals": proposals})

    def post(self):
        """Create a proposal from the caller's suggested record."""
        if not self.require_write_origin():
            return
        user = self.require_user()
        if not user:
            return
        payload = self.json_body()
        if payload is None:
            return
        request = self._validate_create(payload)
        if request is None:
            return
        version, record_id, body = request

        supersedes = payload.get("supersedes")
        previous = self._resolve_supersedes(supersedes)
        if supersedes and previous is None:
            return

        base = self._snapshot_base(version, record_id, body)
        if base is None:
            return

        proposal = new_proposal(
            version=version,
            record_id=record_id,
            record_name=body.get("name"),
            body=body,
            base=base,
            note=payload.get("note") or "",
            author=user,
            supersedes=str(supersedes) if supersedes else None,
        )
        try:
            put_proposal(proposal)
            if previous is not None:
                previous["status"] = "superseded"
                previous["superseded_by"] = proposal["proposal_id"]
                put_proposal(previous)
        except Exception as e:  # pragma: no cover - S3 failures
            _logger.exception("Failed to store metadata proposal")
            self.fail(502, "store_unavailable", detail=str(e))
            return

        self.write_json({"proposal": proposal}, status_code=201)

    def _resolve_supersedes(self, supersedes):
        """Return the open proposal being rebased, or None (writing an error if it is unusable)."""
        if not supersedes:
            return None
        previous = get_proposal(str(supersedes))
        if previous is None:
            self.fail(404, "supersedes_not_found")
            return None
        if previous.get("status") != "open":
            self.fail(409, "supersedes_not_open", proposal_status=previous.get("status"))
            return None
        return previous

    def _validate_create(self, payload):
        """Return `(version, record_id, body)`, or write an error and return None."""
        version = payload.get("version")
        if version not in DOCDB_VERSIONS:
            self.fail(400, "invalid_version", detail="version must be 'v1' or 'v2'.")
            return None

        body = payload.get("body")
        if not isinstance(body, dict):
            self.fail(400, "invalid_body", detail="body must be a JSON object.")
            return None

        record_id = payload.get("id") or body.get("_id")
        if not record_id:
            self.fail(400, "missing_id", detail="Supply 'id', or an '_id' field in the body.")
            return None
        if str(body.get("_id")) != str(record_id):
            self.fail(400, "id_mismatch", detail="body._id must match the proposal's id.")
            return None
        return version, str(record_id), body

    def _snapshot_base(self, version, record_id, body):
        """Return the live record to base the proposal on, or write an error and return None.

        Also rejects a proposal that changes nothing, and one that duplicates an
        open proposal for the same record.
        """
        try:
            base = _fetch_live_record(version, record_id)
        except Exception as e:
            _logger.exception("DocDB read failed while creating a proposal")
            self.fail(502, "docdb_unavailable", detail=str(e))
            return None
        if base is None:
            self.fail(404, "record_not_found", detail=f"No DocDB {version} record with _id {record_id}.")
            return None

        body_hash = canonical_hash(body)
        if body_hash == canonical_hash(base):
            self.fail(400, "no_changes", detail="The proposed body is identical to the live record.")
            return None

        try:
            duplicates = [
                p
                for p in list_proposals(status="open", version=version, record_id=record_id)
                if p.get("body_hash") == body_hash
            ]
        except Exception as e:  # pragma: no cover - S3 failures
            _logger.exception("Failed to check for duplicate proposals")
            self.fail(502, "store_unavailable", detail=str(e))
            return None
        if duplicates:
            self.fail(
                409,
                "duplicate_proposal",
                proposal_id=duplicates[0]["proposal_id"],
                detail="An identical proposal is already open for this record.",
            )
            return None
        return base


class MetadataProposalHandler(_MetadataApiHandler):
    """`/metadata/proposals/<proposal_id>`

    GET — one proposal, including its base snapshot. Public.
    DELETE — withdraw an open proposal. Author only.
    """

    def get(self, proposal_id):
        """Return one proposal, including the record it was based on."""
        proposal = self._load(proposal_id)
        if proposal is None:
            return
        self.write_json({"proposal": proposal})

    def delete(self, proposal_id):
        """Withdraw the caller's own open proposal."""
        if not self.require_write_origin():
            return
        user = self.require_user()
        if not user:
            return
        proposal = self._load(proposal_id)
        if proposal is None:
            return
        if proposal["status"] != "open":
            self.fail(409, "not_open", proposal_status=proposal["status"])
            return
        if proposal["author"] != user:
            self.fail(403, "not_author", detail="Only the author can withdraw a proposal.")
            return
        proposal["status"] = "withdrawn"
        proposal["reviewer"] = user
        proposal["reviewed_at"] = _now_iso()
        put_proposal(proposal)
        self.write_json({"proposal": proposal})

    def _load(self, proposal_id):
        """Return the stored proposal, or write an error and return None."""
        try:
            proposal = get_proposal(str(proposal_id))
        except Exception as e:  # pragma: no cover - S3 failures
            _logger.exception("Failed to read metadata proposal")
            self.fail(502, "store_unavailable", detail=str(e))
            return None
        if proposal is None:
            self.fail(404, "proposal_not_found")
            return None
        return proposal


class MetadataProposalActionHandler(_MetadataApiHandler):
    """POST `/metadata/proposals/<proposal_id>/(approve|reject)`

    Approve is the whole second-actor flow in one call. The reviewer sends the
    `body_hash` they were shown; the server checks that it still matches the
    stored proposal (so a reviewer can never approve something other than what
    they read), that the reviewer is not the author, and that live DocDB still
    matches the proposal's `base_hash` — then upserts.

    Approving is deliberately open to any authenticated QC-portal user: the
    rule being enforced is "two distinct people agreed", not membership of an
    approver list.
    """

    def post(self, proposal_id, action):
        """Approve or reject the proposal named in the path."""
        if not self.require_write_origin():
            return
        user = self.require_user()
        if not user:
            return
        payload = self.json_body()
        if payload is None:
            return

        try:
            proposal = get_proposal(str(proposal_id))
        except Exception as e:  # pragma: no cover - S3 failures
            _logger.exception("Failed to read metadata proposal")
            self.fail(502, "store_unavailable", detail=str(e))
            return
        if proposal is None:
            self.fail(404, "proposal_not_found")
            return
        if proposal["status"] != "open":
            self.fail(409, "not_open", proposal_status=proposal["status"])
            return

        if action == "reject":
            self._reject(proposal, user, payload)
            return
        self._approve(proposal, user, payload)

    def _reject(self, proposal, user, payload):
        """Close the proposal as rejected, recording who rejected it and why."""
        proposal["status"] = "rejected"
        proposal["reviewer"] = user
        proposal["reviewed_at"] = _now_iso()
        proposal["reason"] = payload.get("reason") or ""
        put_proposal(proposal)
        self.write_json({"proposal": proposal})

    def _approve(self, proposal, user, payload):
        """Apply the proposal to DocDB once every approval check passes."""
        if not self._approval_allowed(proposal, user, payload):
            return

        try:
            response = _docdb_client_for(proposal["version"]).upsert_one_docdb_record(proposal["body"])
        except Exception as e:
            _logger.exception("DocDB upsert failed")
            self.fail(502, "docdb_error", detail=str(e))
            return

        status_code = getattr(response, "status_code", 200) or 200
        try:
            docdb_response = response.json() if hasattr(response, "json") else None
        except Exception:
            docdb_response = None
        if docdb_response is None:
            docdb_response = getattr(response, "text", "")

        if not 200 <= status_code < 300:
            # Leave the proposal open so it can be retried once DocDB recovers.
            self.write_json(
                {
                    "status": "failed",
                    "docdb_status": status_code,
                    "docdb_response": docdb_response,
                    "proposal": proposal,
                },
                status_code=502,
            )
            return

        proposal["status"] = "applied"
        proposal["reviewer"] = user
        proposal["reviewed_at"] = _now_iso()
        proposal["docdb_status"] = status_code
        proposal["docdb_response"] = docdb_response
        put_proposal(proposal)
        self.write_json({"status": "applied", "proposal": proposal})

    def _approval_allowed(self, proposal, user, payload):
        """Return True if this approval may proceed, else write an error and return False.

        Three separate things have to hold: the reviewer is not the author, the
        hash they reviewed is still the proposal's, and live DocDB still matches
        the record the proposal was based on.
        """
        if proposal["author"] == user:
            self.fail(
                403,
                "self_approval",
                detail="A proposal must be approved by someone other than its author.",
            )
            return False

        body_hash = payload.get("body_hash")
        if not body_hash:
            self.fail(400, "missing_body_hash", detail="Send the body_hash you reviewed.")
            return False
        if body_hash != proposal["body_hash"]:
            self.fail(
                409,
                "hash_mismatch",
                expected=proposal["body_hash"],
                detail="The proposal changed since you loaded it — reload and review again.",
            )
            return False

        try:
            live = _fetch_live_record(proposal["version"], proposal["record_id"])
        except Exception as e:
            _logger.exception("DocDB read failed while approving a proposal")
            self.fail(502, "docdb_unavailable", detail=str(e))
            return False
        if live is None:
            self.fail(404, "record_not_found")
            return False

        live_hash = canonical_hash(live)
        if live_hash != proposal["base_hash"]:
            self.fail(
                409,
                "base_drift",
                current=live,
                current_hash=live_hash,
                detail="The DocDB record changed after this proposal was made. Rebase it and review again.",
            )
            return False
        return True


ROUTES = [
    ("/upload_metadata", UploadMetadataHandler, {}),
    (r"/get-signed-reference/([^/]+)", GetSignedReferenceHandler, {}),
    ("/metadata/login", MetadataLoginHandler, {}),
    ("/metadata/logout", MetadataLogoutHandler, {}),
    ("/metadata/me", MetadataMeHandler, {}),
    ("/metadata/proposals", MetadataProposalsHandler, {}),
    (r"/metadata/proposals/([^/]+)", MetadataProposalHandler, {}),
    (r"/metadata/proposals/([^/]+)/(approve|reject)", MetadataProposalActionHandler, {}),
    (r"/api/qc/submit", QcSubmitHandler, {}),
]

# Export ROUTES for Panel server to discover
__all__ = ["ROUTES"]
