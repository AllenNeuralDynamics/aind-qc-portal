"""Unit tests for plugin.py request handlers"""

import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application, create_signed_value

from aind_qc_portal import plugin

COOKIE_SECRET = "test-secret"
ALLOWED_ORIGIN = "https://data.allenneuraldynamics.org"


def _make_app() -> Application:
    return Application(plugin.ROUTES, cookie_secret=COOKIE_SECRET)


def _session_cookie(user: str) -> str:
    """Return a Cookie header carrying a valid session for `user`."""
    value = create_signed_value(COOKIE_SECRET, plugin.SESSION_COOKIE_NAME, user).decode()
    return f"{plugin.SESSION_COOKIE_NAME}={value}"


class _FakeStore:
    """In-memory stand-in for metadata_proposals.store, keyed by proposal_id."""

    def __init__(self):
        self.items = {}

    def put(self, proposal):
        self.items[proposal["proposal_id"]] = json.loads(json.dumps(proposal))

    def get(self, proposal_id):
        stored = self.items.get(str(proposal_id))
        return json.loads(json.dumps(stored)) if stored else None

    def list(self, status=None, version=None, record_id=None):
        wanted = None
        if status and status != "all":
            wanted = {s.strip() for s in status.split(",") if s.strip()}
        out = []
        for p in self.items.values():
            if wanted is not None and p["status"] not in wanted:
                continue
            if version and p["version"] != version:
                continue
            if record_id and str(p["record_id"]) != str(record_id):
                continue
            out.append(json.loads(json.dumps(p)))
        out.sort(key=lambda p: p["created_at"], reverse=True)
        return out


class _ProposalApiTestCase(AsyncHTTPTestCase):
    """Base case wiring the proposal handlers to a fake store and fake DocDB."""

    LIVE_RECORD = {"_id": "abc", "name": "asset-1", "subject": {"subject_id": "1"}}
    PROPOSED = {"_id": "abc", "name": "asset-1", "subject": {"subject_id": "2"}}

    def get_app(self) -> Application:
        return _make_app()

    def setUp(self):
        super().setUp()
        self.store = _FakeStore()
        self.live_record = json.loads(json.dumps(self.LIVE_RECORD))
        self.upsert_response = MagicMock(status_code=200, text="ok")
        self.upsert_response.json.return_value = {"message": "upserted"}
        self.upsert_calls = []

        def _upsert(body):
            self.upsert_calls.append(body)
            return self.upsert_response

        patches = [
            patch.object(plugin, "put_proposal", self.store.put),
            patch.object(plugin, "get_proposal", self.store.get),
            patch.object(plugin, "list_proposals", self.store.list),
            patch.object(plugin, "_fetch_live_record", lambda version, rid: self.live_record),
            patch.object(
                plugin,
                "_docdb_client_for",
                lambda version: MagicMock(upsert_one_docdb_record=_upsert),
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _post(self, path, body, user=None, origin=ALLOWED_ORIGIN, method="POST"):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        if user:
            headers["Cookie"] = _session_cookie(user)
        return self.fetch(
            path,
            method=method,
            body=json.dumps(body),
            headers=headers,
            allow_nonstandard_methods=True,
        )

    def _create(self, user="alice", body=None, **extra):
        payload = {"version": "v2", "id": "abc", "body": body or self.PROPOSED}
        payload.update(extra)
        response = self._post("/metadata/proposals", payload, user=user)
        return response, json.loads(response.body)

    def _json(self, response):
        return json.loads(response.body)


class TestMetadataLoginHandler(AsyncHTTPTestCase):
    """Tests for GET /metadata/login"""

    GOOD_REDIRECT = "https://data.allenneuraldynamics.org/migrate/submit?id=abc"
    SAME_SITE_HEADERS = {"Sec-Fetch-Site": "same-site"}

    def get_app(self) -> Application:
        return _make_app()

    def _fetch_no_follow(self, path: str, headers: dict | None = None):
        return self.fetch(path, follow_redirects=False, headers=headers or self.SAME_SITE_HEADERS)

    def test_missing_redirect(self):
        response = self._fetch_no_follow("/metadata/login")
        self.assertEqual(response.code, 400)

    def test_errors_are_json(self):
        response = self._fetch_no_follow("/metadata/login")
        self.assertIn("application/json", response.headers["Content-Type"])
        self.assertEqual(json.loads(response.body)["status"], "error")

    def test_redirect_must_be_https(self):
        response = self._fetch_no_follow(
            "/metadata/login?" + urlencode({"redirect": "http://data.allenneuraldynamics.org/x"})
        )
        self.assertEqual(response.code, 400)

    def test_redirect_must_be_allowed_host(self):
        response = self._fetch_no_follow("/metadata/login?" + urlencode({"redirect": "https://evil.example/x"}))
        self.assertEqual(response.code, 400)

    def test_test_domain_redirect_allowed(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self._fetch_no_follow(
                "/metadata/login?" + urlencode({"redirect": "https://data.allenneuraldynamics-test.org/x"})
            )
        self.assertEqual(response.code, 302)

    def test_cross_site_request_rejected(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self._fetch_no_follow(
                "/metadata/login?" + urlencode({"redirect": self.GOOD_REDIRECT}),
                headers={"Sec-Fetch-Site": "cross-site"},
            )
        self.assertEqual(response.code, 403)

    def test_direct_navigation_allowed(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self._fetch_no_follow(
                "/metadata/login?" + urlencode({"redirect": self.GOOD_REDIRECT}),
                headers={"Sec-Fetch-Site": "none"},
            )
        self.assertEqual(response.code, 302)

    def test_request_with_no_origin_signals_rejected(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self.fetch(
                "/metadata/login?" + urlencode({"redirect": self.GOOD_REDIRECT}),
                follow_redirects=False,
                headers={},
            )
        self.assertEqual(response.code, 403)

    def test_request_with_allowed_referer_accepted(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self.fetch(
                "/metadata/login?" + urlencode({"redirect": self.GOOD_REDIRECT}),
                follow_redirects=False,
                headers={"Referer": "https://data.allenneuraldynamics.org/start"},
            )
        self.assertEqual(response.code, 302)

    def test_unauthenticated_user_bounces_through_panel_login(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value=None):
            response = self._fetch_no_follow("/metadata/login?" + urlencode({"redirect": self.GOOD_REDIRECT}))
        self.assertEqual(response.code, 302)
        location = response.headers["Location"]
        self.assertTrue(location.startswith(plugin.PANEL_LOGIN_PATH))
        self.assertIn("%2Fmetadata%2Flogin", location)
        self.assertNotIn(plugin.SESSION_COOKIE_NAME, "\n".join(response.headers.get_list("Set-Cookie")))

    def test_authenticated_user_gets_session_and_returns_to_redirect(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self._fetch_no_follow("/metadata/login?" + urlencode({"redirect": self.GOOD_REDIRECT}))

        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers["Location"], self.GOOD_REDIRECT)

        cookie = next(
            c for c in response.headers.get_list("Set-Cookie") if c.startswith(plugin.SESSION_COOKIE_NAME + "=")
        )
        self.assertIn("Domain=" + plugin.SESSION_COOKIE_DOMAIN, cookie)
        self.assertIn("httponly", cookie.lower())
        self.assertIn("secure", cookie.lower())
        self.assertIn("samesite=none", cookie.lower())


class TestMetadataMeHandler(AsyncHTTPTestCase):
    """Tests for GET /metadata/me and POST /metadata/logout"""

    def get_app(self) -> Application:
        return _make_app()

    def test_no_session_is_401(self):
        response = self.fetch("/metadata/me")
        self.assertEqual(response.code, 401)
        self.assertEqual(json.loads(response.body)["error"], "not_authenticated")

    def test_session_returns_user(self):
        response = self.fetch("/metadata/me", headers={"Cookie": _session_cookie("alice")})
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body), {"authenticated": True, "user": "alice"})

    def test_logout_clears_the_cookie(self):
        response = self.fetch(
            "/metadata/logout",
            method="POST",
            body="",
            headers={"Cookie": _session_cookie("alice"), "Origin": ALLOWED_ORIGIN},
        )
        self.assertEqual(response.code, 200)
        cookie = next(
            c for c in response.headers.get_list("Set-Cookie") if c.startswith(plugin.SESSION_COOKIE_NAME + "=")
        )
        self.assertIn("expires=", cookie.lower())


class TestCreateProposal(_ProposalApiTestCase):
    """Tests for POST /metadata/proposals"""

    def test_requires_a_session(self):
        response, body = self._create(user=None)
        self.assertEqual(response.code, 401)
        self.assertEqual(body["error"], "not_authenticated")

    def test_rejects_disallowed_origin(self):
        response = self._post(
            "/metadata/proposals",
            {"version": "v2", "id": "abc", "body": self.PROPOSED},
            user="alice",
            origin="https://evil.example",
        )
        self.assertEqual(response.code, 403)
        self.assertEqual(self._json(response)["error"], "origin_not_allowed")

    def test_rejects_bad_version(self):
        response, body = self._create(version="v3")
        self.assertEqual(response.code, 400)
        self.assertEqual(body["error"], "invalid_version")

    def test_rejects_id_mismatch(self):
        response, body = self._create(id="other")
        self.assertEqual(response.code, 400)
        self.assertEqual(body["error"], "id_mismatch")

    def test_rejects_a_no_op(self):
        response, body = self._create(body=dict(self.LIVE_RECORD))
        self.assertEqual(response.code, 400)
        self.assertEqual(body["error"], "no_changes")

    def test_rejects_missing_record(self):
        with patch.object(plugin, "_fetch_live_record", lambda version, rid: None):
            response, body = self._create()
        self.assertEqual(response.code, 404)
        self.assertEqual(body["error"], "record_not_found")

    def test_stores_the_proposal_with_a_server_side_base(self):
        response, body = self._create(note="pull v2 subject")
        self.assertEqual(response.code, 201)
        proposal = body["proposal"]
        self.assertEqual(proposal["status"], "open")
        self.assertEqual(proposal["author"], "alice")
        self.assertEqual(proposal["note"], "pull v2 subject")
        self.assertEqual(proposal["base"], self.LIVE_RECORD)
        self.assertEqual(proposal["base_hash"], plugin.canonical_hash(self.LIVE_RECORD))
        self.assertEqual(proposal["body_hash"], plugin.canonical_hash(self.PROPOSED))
        self.assertEqual(proposal["record_name"], "asset-1")
        self.assertIn(proposal["proposal_id"], self.store.items)

    def test_duplicate_open_proposal_is_rejected(self):
        _, first = self._create()
        response, body = self._create(user="bob")
        self.assertEqual(response.code, 409)
        self.assertEqual(body["error"], "duplicate_proposal")
        self.assertEqual(body["proposal_id"], first["proposal"]["proposal_id"])

    def test_supersede_closes_the_previous_proposal(self):
        _, first = self._create()
        old_id = first["proposal"]["proposal_id"]
        rebased = {"_id": "abc", "name": "asset-1", "subject": {"subject_id": "3"}}
        response, body = self._create(user="alice", body=rebased, supersedes=old_id)
        self.assertEqual(response.code, 201)
        self.assertEqual(self.store.get(old_id)["status"], "superseded")
        self.assertEqual(self.store.get(old_id)["superseded_by"], body["proposal"]["proposal_id"])
        self.assertEqual(body["proposal"]["supersedes"], old_id)

    def test_supersede_requires_an_open_proposal(self):
        _, first = self._create()
        old_id = first["proposal"]["proposal_id"]
        stored = self.store.get(old_id)
        stored["status"] = "applied"
        self.store.put(stored)
        response, body = self._create(body={"_id": "abc", "name": "x"}, supersedes=old_id)
        self.assertEqual(response.code, 409)
        self.assertEqual(body["error"], "supersedes_not_open")


class TestListProposals(_ProposalApiTestCase):
    """Tests for GET /metadata/proposals"""

    def test_queue_is_public_and_defaults_to_open(self):
        _, created = self._create()
        applied = self.store.get(created["proposal"]["proposal_id"])
        applied["proposal_id"] = "applied-one"
        applied["status"] = "applied"
        self.store.put(applied)

        response = self.fetch("/metadata/proposals")
        self.assertEqual(response.code, 200)
        ids = [p["proposal_id"] for p in self._json(response)["proposals"]]
        self.assertEqual(ids, [created["proposal"]["proposal_id"]])

    def test_status_all_returns_everything(self):
        self._create()
        response = self.fetch("/metadata/proposals?status=all")
        self.assertEqual(len(self._json(response)["proposals"]), 1)

    def test_invalid_version_filter(self):
        response = self.fetch("/metadata/proposals?version=v9")
        self.assertEqual(response.code, 400)


class TestProposalDetailAndWithdraw(_ProposalApiTestCase):
    """Tests for GET/DELETE /metadata/proposals/<id>"""

    def test_get_unknown_proposal(self):
        response = self.fetch("/metadata/proposals/nope")
        self.assertEqual(response.code, 404)
        self.assertEqual(self._json(response)["error"], "proposal_not_found")

    def test_get_returns_the_proposal(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        response = self.fetch(f"/metadata/proposals/{pid}")
        self.assertEqual(response.code, 200)
        self.assertEqual(self._json(response)["proposal"]["proposal_id"], pid)

    def test_only_the_author_may_withdraw(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        response = self._post(f"/metadata/proposals/{pid}", {}, user="bob", method="DELETE")
        self.assertEqual(response.code, 403)
        self.assertEqual(self._json(response)["error"], "not_author")
        self.assertEqual(self.store.get(pid)["status"], "open")

    def test_author_withdraws(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        response = self._post(f"/metadata/proposals/{pid}", {}, user="alice", method="DELETE")
        self.assertEqual(response.code, 200)
        self.assertEqual(self.store.get(pid)["status"], "withdrawn")


class TestApproveProposal(_ProposalApiTestCase):
    """Tests for POST /metadata/proposals/<id>/approve"""

    def _approve(self, pid, user="bob", body_hash=None):
        payload = {"body_hash": body_hash if body_hash is not None else self.store.get(pid)["body_hash"]}
        response = self._post(f"/metadata/proposals/{pid}/approve", payload, user=user)
        return response, self._json(response)

    def test_requires_a_session(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        response, body = self._approve(pid, user=None)
        self.assertEqual(response.code, 401)
        self.assertEqual(self.upsert_calls, [])

    def test_author_cannot_approve_their_own(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        response, body = self._approve(pid, user="alice")
        self.assertEqual(response.code, 403)
        self.assertEqual(body["error"], "self_approval")
        self.assertEqual(self.upsert_calls, [])

    def test_hash_must_match_what_the_reviewer_saw(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        response, body = self._approve(pid, body_hash="stale")
        self.assertEqual(response.code, 409)
        self.assertEqual(body["error"], "hash_mismatch")
        self.assertEqual(self.upsert_calls, [])

    def test_body_hash_is_required(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        response = self._post(f"/metadata/proposals/{pid}/approve", {}, user="bob")
        self.assertEqual(response.code, 400)
        self.assertEqual(self._json(response)["error"], "missing_body_hash")

    def test_drifted_base_blocks_the_upsert(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        self.live_record = {"_id": "abc", "name": "asset-1", "subject": {"subject_id": "9"}}
        response, body = self._approve(pid)
        self.assertEqual(response.code, 409)
        self.assertEqual(body["error"], "base_drift")
        self.assertEqual(body["current"], self.live_record)
        self.assertEqual(self.upsert_calls, [])
        self.assertEqual(self.store.get(pid)["status"], "open")

    def test_second_user_applies_the_change(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        response, body = self._approve(pid)
        self.assertEqual(response.code, 200)
        self.assertEqual(body["status"], "applied")
        self.assertEqual(self.upsert_calls, [self.PROPOSED])
        stored = self.store.get(pid)
        self.assertEqual(stored["status"], "applied")
        self.assertEqual(stored["reviewer"], "bob")
        self.assertEqual(stored["docdb_status"], 200)
        self.assertIsNotNone(stored["reviewed_at"])

    def test_a_failed_upsert_leaves_the_proposal_open(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        self.upsert_response.status_code = 500
        response, body = self._approve(pid)
        self.assertEqual(response.code, 502)
        self.assertEqual(body["status"], "failed")
        self.assertEqual(self.store.get(pid)["status"], "open")

    def test_a_raising_upsert_leaves_the_proposal_open(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]

        def _boom(version):
            client = MagicMock()
            client.upsert_one_docdb_record.side_effect = RuntimeError("docdb down")
            return client

        with patch.object(plugin, "_docdb_client_for", _boom):
            response, body = self._approve(pid)
        self.assertEqual(response.code, 502)
        self.assertEqual(body["error"], "docdb_error")
        self.assertEqual(self.store.get(pid)["status"], "open")

    def test_cannot_approve_twice(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        self._approve(pid)
        response, body = self._approve(pid, user="carol")
        self.assertEqual(response.code, 409)
        self.assertEqual(body["error"], "not_open")
        self.assertEqual(len(self.upsert_calls), 1)


class TestRejectProposal(_ProposalApiTestCase):
    """Tests for POST /metadata/proposals/<id>/reject"""

    def test_reject_records_the_reason(self):
        _, created = self._create()
        pid = created["proposal"]["proposal_id"]
        response = self._post(f"/metadata/proposals/{pid}/reject", {"reason": "old value was right"}, user="bob")
        self.assertEqual(response.code, 200)
        stored = self.store.get(pid)
        self.assertEqual(stored["status"], "rejected")
        self.assertEqual(stored["reason"], "old value was right")
        self.assertEqual(stored["reviewer"], "bob")
        self.assertEqual(self.upsert_calls, [])


class TestCorsHeaders(AsyncHTTPTestCase):
    """Tests for CORS handling on /metadata/* endpoints."""

    def get_app(self) -> Application:
        return _make_app()

    def _preflight(self, origin, path="/metadata/proposals"):
        return self.fetch(
            path,
            method="OPTIONS",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
            allow_nonstandard_methods=True,
        )

    def test_allowed_origin_gets_cors_headers(self):
        response = self._preflight(ALLOWED_ORIGIN)
        self.assertEqual(response.code, 204)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), ALLOWED_ORIGIN)
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods", ""))
        self.assertIn("Content-Type", response.headers.get("Access-Control-Allow-Headers", ""))

    def test_preflight_on_a_proposal_action(self):
        response = self._preflight(ALLOWED_ORIGIN, "/metadata/proposals/abc/approve")
        self.assertEqual(response.code, 204)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), ALLOWED_ORIGIN)

    def test_test_domain_origin_is_rejected_for_cors(self):
        response = self._preflight("https://data.allenneuraldynamics-test.org")
        self.assertEqual(response.code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_disallowed_origin_no_cors_header(self):
        response = self._preflight("https://evil.example")
        self.assertEqual(response.code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_http_origin_is_rejected(self):
        response = self._preflight("http://qc.allenneuraldynamics.org")
        self.assertEqual(response.code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)


class TestCanonicalHash(unittest.TestCase):
    """Tests for the canonical_hash helper"""

    def test_key_order_independent_hash(self):
        self.assertEqual(
            plugin.canonical_hash({"a": 1, "b": 2}),
            plugin.canonical_hash({"b": 2, "a": 1}),
        )

    def test_different_payloads_have_different_hashes(self):
        self.assertNotEqual(plugin.canonical_hash({"a": 1}), plugin.canonical_hash({"a": 2}))


class TestHostAllowed(unittest.TestCase):
    """Tests for _host_allowed helper"""

    def test_allowed_exact_subdomain(self):
        self.assertTrue(plugin._host_allowed("data.allenneuraldynamics.org"))

    def test_allowed_test_domain(self):
        self.assertTrue(plugin._host_allowed("qc.allenneuraldynamics-test.org"))

    def test_allowed_with_port(self):
        self.assertTrue(plugin._host_allowed("qc.allenneuraldynamics.org:443"))

    def test_disallowed_lookalike(self):
        self.assertFalse(plugin._host_allowed("allenneuraldynamics.org.evil.com"))

    def test_disallowed_random(self):
        self.assertFalse(plugin._host_allowed("evil.example"))

    def test_disallowed_empty(self):
        self.assertFalse(plugin._host_allowed(""))
        self.assertFalse(plugin._host_allowed(None))


class TestValidateRedirect(unittest.TestCase):
    """Tests for _validate_redirect helper"""

    def test_valid(self):
        url = "https://data.allenneuraldynamics.org/x?y=1"
        self.assertEqual(plugin._validate_redirect(url), url)

    def test_missing(self):
        with self.assertRaises(plugin.HTTPError) as ctx:
            plugin._validate_redirect(None)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_http_rejected(self):
        with self.assertRaises(plugin.HTTPError) as ctx:
            plugin._validate_redirect("http://data.allenneuraldynamics.org/x")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_relative_rejected(self):
        with self.assertRaises(plugin.HTTPError):
            plugin._validate_redirect("/relative/path")

    def test_disallowed_host_rejected(self):
        with self.assertRaises(plugin.HTTPError):
            plugin._validate_redirect("https://evil.example/x")


class TestPanelUserFromHandler(unittest.TestCase):
    """Tests for _panel_user_from_handler helper"""

    def _handler(self, cookie_bytes):
        handler = MagicMock()
        handler.get_secure_cookie.return_value = cookie_bytes
        return handler

    def test_no_cookie_returns_none(self):
        self.assertIsNone(plugin._panel_user_from_handler(self._handler(None)))

    def test_guest_user_returns_none(self):
        self.assertIsNone(plugin._panel_user_from_handler(self._handler(b"guest")))

    def test_empty_user_returns_none(self):
        self.assertIsNone(plugin._panel_user_from_handler(self._handler(b"")))

    def test_valid_user(self):
        self.assertEqual(
            plugin._panel_user_from_handler(self._handler(b"alice")), "alice"
        )

    def test_non_utf8_returns_none(self):
        self.assertIsNone(
            plugin._panel_user_from_handler(self._handler(b"\xff\xfe\xff"))
        )


if __name__ == "__main__":
    unittest.main()
