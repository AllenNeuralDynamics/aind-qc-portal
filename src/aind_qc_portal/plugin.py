"""Plugin file for custom Panel server endpoints"""

import hashlib
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlparse

from aind_data_access_api.document_db import MetadataDbClient
from panel.config import config as panel_config
from tornado.web import HTTPError, RequestHandler

from aind_qc_portal.view_contents.data_utils import upload_temporary_metadata
from aind_qc_portal.view_contents.panels.media.utils import clean_reference_prefix, get_s3_url

_docdb_client = MetadataDbClient(
    host="api.allenneuraldynamics.org",
    version="v2",
)

DOCDB_HOST = "api.allenneuraldynamics.org"
AUTH_COOKIE_NAME = "qc_auth_token"
AUTH_EXPIRY_COOKIE_NAME = "qc_auth_token_expires_at"
AUTH_COOKIE_DOMAIN = ".allenneuraldynamics.org"
AUTH_TOKEN_TTL_SECONDS = 60 * 60 * 72
REQUIRED_DISTINCT_USERS = 2
ALLOWED_HOST_SUFFIXES = (
    ".allenneuraldynamics.org",
    ".allenneuraldynamics-test.org",
)
ALLOWED_CORS_SUFFIXES = ALLOWED_HOST_SUFFIXES

_ISSUED_TOKENS: dict[str, dict] = {}
_PENDING_UPSERTS: dict[tuple[str, str, str], dict] = {}


def _now() -> float:
    """Return the current epoch time in seconds."""
    return time.time()


def _prune_expired_tokens() -> None:
    """Drop tokens older than AUTH_TOKEN_TTL_SECONDS."""
    cutoff = _now() - AUTH_TOKEN_TTL_SECONDS
    for token in [t for t, info in _ISSUED_TOKENS.items() if info["issued_at"] < cutoff]:
        _ISSUED_TOKENS.pop(token, None)


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


def _canonical_body(body: bytes) -> tuple[str, dict]:
    """Parse JSON and return (sha256-of-canonical-form, parsed-dict)."""
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPError(400, "Invalid JSON body.")
    if not isinstance(parsed, dict):
        raise HTTPError(400, "Request body must be a JSON object.")
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest(), parsed


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

    Defends against CSRF on the token-issuing GET endpoint. Accepts the request
    when either:
      * `Sec-Fetch-Site` is `same-origin` or `same-site`, OR
      * `Origin` or `Referer` host is on the allowlist.
    Rejects when no trustworthy signal is present (e.g. attacker-controlled page
    with `Referrer-Policy: no-referrer`).
    """
    sec_fetch_site = handler.request.headers.get("Sec-Fetch-Site")
    if sec_fetch_site in ("same-origin", "same-site"):
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


class _CrossOriginMixin:
    """Mixin that applies permissive CORS for trusted AIND subdomains."""

    def set_default_headers(self):
        origin = self.request.headers.get("Origin", "")
        if origin and any(origin.endswith(suffix) for suffix in ALLOWED_CORS_SUFFIXES):
            self.set_header("Access-Control-Allow-Origin", origin)
            self.set_header("Access-Control-Allow-Credentials", "true")
        self.set_header("Vary", "Origin")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()


class IssueMetadataTokenHandler(_CrossOriginMixin, RequestHandler):
    """GET /metadata/token?redirect=<url>&id=<_id>

    Requires the caller to be authenticated against the QC portal. Issues a
    one-time token bound to (user, _id), stores it server-side, sets a
    cross-subdomain cookie, then 302-redirects to <redirect>.
    """

    def get(self):
        redirect = self.get_argument("redirect", None)
        record_id = self.get_argument("id", None)
        if not record_id:
            raise HTTPError(400, "Missing required query parameter: id")
        redirect = _validate_redirect(redirect)
        _enforce_same_site_request(self)

        user = _panel_user_from_handler(self)
        if not user:
            raise HTTPError(401, "User must be logged in to the QC portal to obtain a token.")

        _prune_expired_tokens()
        token = secrets.token_urlsafe(32)
        issued_at = _now()
        expires_at = issued_at + AUTH_TOKEN_TTL_SECONDS
        _ISSUED_TOKENS[token] = {"user": user, "id": str(record_id), "issued_at": issued_at}

        cookie_expires_days = AUTH_TOKEN_TTL_SECONDS / 86400
        self.set_cookie(
            AUTH_COOKIE_NAME,
            token,
            domain=AUTH_COOKIE_DOMAIN,
            path="/",
            secure=True,
            samesite="None",
            httponly=False,
            expires_days=cookie_expires_days,
        )
        self.set_cookie(
            AUTH_EXPIRY_COOKIE_NAME,
            str(int(expires_at)),
            domain=AUTH_COOKIE_DOMAIN,
            path="/",
            secure=True,
            samesite="None",
            httponly=False,
            expires_days=cookie_expires_days,
        )
        self.redirect(redirect)


class _UpsertMetadataHandler(_CrossOriginMixin, RequestHandler):
    """POST /metadata/v{1,2}?auth-token=<token>

    Coalesces requests by (version, _id, canonical-body-hash). Once
    REQUIRED_DISTINCT_USERS distinct users have submitted the same payload
    with valid tokens bound to the same _id, the metadata is upserted to
    DocDB and the participating tokens are consumed.
    """

    VERSION: str = ""

    def post(self):
        token = self.get_argument("auth-token", None)
        if not token:
            raise HTTPError(401, "Missing auth-token query parameter.")
        if not self.request.body:
            raise HTTPError(400, "Missing request body.")

        _prune_expired_tokens()

        token_info = _ISSUED_TOKENS.get(token)
        if not token_info:
            raise HTTPError(401, "Invalid or expired auth-token.")

        body_hash, parsed_body = _canonical_body(self.request.body)

        record_id = parsed_body.get("_id")
        if not record_id:
            raise HTTPError(400, "Request body must include an '_id' field.")
        if str(record_id) != token_info["id"]:
            raise HTTPError(403, "auth-token is not valid for the supplied _id.")

        key = (self.VERSION, str(record_id), body_hash)
        pending = _PENDING_UPSERTS.setdefault(
            key,
            {"version": self.VERSION, "body": parsed_body, "submissions": {}},
        )

        already_submitted = token_info["user"] in pending["submissions"]
        if already_submitted and len(pending["submissions"]) < REQUIRED_DISTINCT_USERS:
            raise HTTPError(409, "This user has already submitted this request.")

        if not already_submitted:
            pending["submissions"][token_info["user"]] = token

        if len(pending["submissions"]) < REQUIRED_DISTINCT_USERS:
            earliest_expiry = min(
                _ISSUED_TOKENS[t]["issued_at"] for t in pending["submissions"].values()
            ) + AUTH_TOKEN_TTL_SECONDS
            self.set_header("Content-Type", "application/json")
            self.write(
                {
                    "status": "pending",
                    "submissions": len(pending["submissions"]),
                    "required": REQUIRED_DISTINCT_USERS,
                    "expires_at": int(earliest_expiry),
                }
            )
            return

        client = MetadataDbClient(host=DOCDB_HOST, version=self.VERSION)
        try:
            response = client.upsert_one_docdb_record(pending["body"])
        except Exception as e:
            raise HTTPError(502, f"DocDB upsert error: {str(e)}")

        status_code = getattr(response, "status_code", 200) or 200
        try:
            payload = response.json() if hasattr(response, "json") else None
        except Exception:
            payload = None
        text = getattr(response, "text", "")

        succeeded = 200 <= status_code < 300

        if succeeded:
            for consumed_token in pending["submissions"].values():
                _ISSUED_TOKENS.pop(consumed_token, None)
            _PENDING_UPSERTS.pop(key, None)

        self.set_header("Content-Type", "application/json")
        self.set_status(status_code)
        self.write(
            {
                "status": "submitted" if succeeded else "failed",
                "docdb_status": status_code,
                "docdb_response": payload if payload is not None else text,
            }
        )


class UpsertMetadataV1Handler(_UpsertMetadataHandler):
    """POST /metadata/v1?auth-token=<token>"""

    VERSION = "v1"


class UpsertMetadataV2Handler(_UpsertMetadataHandler):
    """POST /metadata/v2?auth-token=<token>"""

    VERSION = "v2"


ROUTES = [
    ("/upload_metadata", UploadMetadataHandler, {}),
    (r"/get-signed-reference/([^/]+)", GetSignedReferenceHandler, {}),
    ("/metadata/token", IssueMetadataTokenHandler, {}),
    ("/metadata/v1", UpsertMetadataV1Handler, {}),
    ("/metadata/v2", UpsertMetadataV2Handler, {}),
]

# Export ROUTES for Panel server to discover
__all__ = ["ROUTES"]
