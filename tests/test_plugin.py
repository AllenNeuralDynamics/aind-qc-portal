"""Unit tests for plugin.py request handlers"""

import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

from aind_qc_portal import plugin


def _make_app() -> Application:
    return Application(plugin.ROUTES, cookie_secret="test-secret")


def _reset_state() -> None:
    plugin._ISSUED_TOKENS.clear()
    plugin._PENDING_UPSERTS.clear()


class TestIssueMetadataTokenHandler(AsyncHTTPTestCase):
    """Tests for GET /metadata/token"""

    GOOD_REDIRECT = "https://data.allenneuraldynamics.org/landing"
    SAME_SITE_HEADERS = {"Sec-Fetch-Site": "same-site"}

    def get_app(self) -> Application:
        return _make_app()

    def setUp(self):
        super().setUp()
        _reset_state()

    def _fetch_no_follow(self, path: str, headers: dict | None = None):
        return self.fetch(path, follow_redirects=False, headers=headers or self.SAME_SITE_HEADERS)

    def test_missing_query_params(self):
        response = self._fetch_no_follow("/metadata/token")
        self.assertEqual(response.code, 400)

    def test_missing_id(self):
        response = self._fetch_no_follow("/metadata/token?" + urlencode({"redirect": self.GOOD_REDIRECT}))
        self.assertEqual(response.code, 400)

    def test_redirect_must_be_https(self):
        response = self._fetch_no_follow(
            "/metadata/token?" + urlencode({"redirect": "http://data.allenneuraldynamics.org/x", "id": "abc"})
        )
        self.assertEqual(response.code, 400)

    def test_redirect_must_be_allowed_host(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self._fetch_no_follow(
                "/metadata/token?" + urlencode({"redirect": "https://evil.example/x", "id": "abc"})
            )
        self.assertEqual(response.code, 400)
        self.assertEqual(plugin._ISSUED_TOKENS, {})

    def test_test_domain_redirect_allowed(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self._fetch_no_follow(
                "/metadata/token?"
                + urlencode({"redirect": "https://data.allenneuraldynamics-test.org/x", "id": "abc"})
            )
        self.assertEqual(response.code, 302)

    def test_cross_site_request_rejected(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self._fetch_no_follow(
                "/metadata/token?" + urlencode({"redirect": self.GOOD_REDIRECT, "id": "abc"}),
                headers={"Sec-Fetch-Site": "cross-site"},
            )
        self.assertEqual(response.code, 403)
        self.assertEqual(plugin._ISSUED_TOKENS, {})

    def test_request_with_no_origin_signals_rejected(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self.fetch(
                "/metadata/token?" + urlencode({"redirect": self.GOOD_REDIRECT, "id": "abc"}),
                follow_redirects=False,
                headers={},
            )
        self.assertEqual(response.code, 403)

    def test_request_with_allowed_referer_accepted(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self.fetch(
                "/metadata/token?" + urlencode({"redirect": self.GOOD_REDIRECT, "id": "abc"}),
                follow_redirects=False,
                headers={"Referer": "https://data.allenneuraldynamics.org/start"},
            )
        self.assertEqual(response.code, 302)

    def test_request_with_disallowed_referer_rejected(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self.fetch(
                "/metadata/token?" + urlencode({"redirect": self.GOOD_REDIRECT, "id": "abc"}),
                follow_redirects=False,
                headers={"Referer": "https://evil.example/page"},
            )
        self.assertEqual(response.code, 403)

    def test_unauthenticated_user_rejected(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value=None):
            response = self._fetch_no_follow(
                "/metadata/token?" + urlencode({"redirect": self.GOOD_REDIRECT, "id": "abc"})
            )
        self.assertEqual(response.code, 401)
        self.assertEqual(plugin._ISSUED_TOKENS, {})

    def test_authenticated_user_issues_token_and_redirects(self):
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = self._fetch_no_follow(
                "/metadata/token?" + urlencode({"redirect": self.GOOD_REDIRECT, "id": "abc"})
            )

        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers["Location"], self.GOOD_REDIRECT)

        self.assertEqual(len(plugin._ISSUED_TOKENS), 1)
        token, info = next(iter(plugin._ISSUED_TOKENS.items()))
        self.assertEqual(info["user"], "alice")
        self.assertEqual(info["id"], "abc")
        self.assertIn("issued_at", info)

        set_cookies = response.headers.get_list("Set-Cookie")
        joined = "\n".join(set_cookies)
        self.assertIn(plugin.AUTH_COOKIE_NAME + "=" + token, joined)
        self.assertIn("Domain=" + plugin.AUTH_COOKIE_DOMAIN, joined)
        self.assertIn("Path=/", joined)

        expiry_cookie = next((c for c in set_cookies if c.startswith(plugin.AUTH_EXPIRY_COOKIE_NAME + "=")), None)
        self.assertIsNotNone(expiry_cookie)
        expiry_value = expiry_cookie.split(";", 1)[0].split("=", 1)[1]
        expected = int(info["issued_at"] + plugin.AUTH_TOKEN_TTL_SECONDS)
        self.assertEqual(int(expiry_value), expected)


class TestUpsertMetadataHandler(AsyncHTTPTestCase):
    """Tests for POST /metadata/v1 and /metadata/v2"""

    def get_app(self) -> Application:
        return _make_app()

    def setUp(self):
        super().setUp()
        _reset_state()

    def _issue(self, user: str, record_id: str) -> str:
        token = "tok-" + user + "-" + record_id
        plugin._ISSUED_TOKENS[token] = {
            "user": user,
            "id": record_id,
            "issued_at": plugin._now(),
        }
        return token

    def _post(self, path: str, body: dict, token: str | None):
        url = path
        if token is not None:
            url = path + "?" + urlencode({"auth-token": token})
        return self.fetch(
            url,
            method="POST",
            body=json.dumps(body),
            headers={"Content-Type": "application/json"},
            allow_nonstandard_methods=False,
        )

    def test_missing_token(self):
        response = self.fetch(
            "/metadata/v2",
            method="POST",
            body=json.dumps({"_id": "abc"}),
            allow_nonstandard_methods=False,
        )
        self.assertEqual(response.code, 401)

    def test_invalid_token(self):
        response = self._post("/metadata/v2", {"_id": "abc"}, "bogus-token")
        self.assertEqual(response.code, 401)

    def test_missing_body(self):
        token = self._issue("alice", "abc")
        response = self.fetch(
            "/metadata/v2?" + urlencode({"auth-token": token}),
            method="POST",
            body=b"",
            allow_nonstandard_methods=True,
        )
        self.assertEqual(response.code, 400)

    def test_invalid_json_body(self):
        token = self._issue("alice", "abc")
        response = self.fetch(
            "/metadata/v2?" + urlencode({"auth-token": token}),
            method="POST",
            body=b"not-json",
            allow_nonstandard_methods=False,
        )
        self.assertEqual(response.code, 400)

    def test_body_must_be_object(self):
        token = self._issue("alice", "abc")
        response = self.fetch(
            "/metadata/v2?" + urlencode({"auth-token": token}),
            method="POST",
            body=b"[1, 2, 3]",
            allow_nonstandard_methods=False,
        )
        self.assertEqual(response.code, 400)

    def test_missing_id_in_body(self):
        token = self._issue("alice", "abc")
        response = self._post("/metadata/v2", {"name": "no-id"}, token)
        self.assertEqual(response.code, 400)

    def test_token_id_mismatch(self):
        token = self._issue("alice", "abc")
        response = self._post("/metadata/v2", {"_id": "other"}, token)
        self.assertEqual(response.code, 403)

    def test_first_submission_pending(self):
        token = self._issue("alice", "abc")
        response = self._post("/metadata/v2", {"_id": "abc", "name": "x"}, token)
        self.assertEqual(response.code, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["submissions"], 1)
        self.assertEqual(payload["required"], plugin.REQUIRED_DISTINCT_USERS)
        self.assertIn("body_hash", payload)
        self.assertNotIn("other_pending_hashes", payload)
        info = plugin._ISSUED_TOKENS[token]
        self.assertEqual(payload["expires_at"], int(info["issued_at"] + plugin.AUTH_TOKEN_TTL_SECONDS))
        self.assertEqual(len(plugin._PENDING_UPSERTS), 1)
        self.assertIn(token, plugin._ISSUED_TOKENS)

    def test_same_user_double_submit_rejected(self):
        token = self._issue("alice", "abc")
        first = self._post("/metadata/v2", {"_id": "abc", "name": "x"}, token)
        self.assertEqual(first.code, 200)
        second = self._post("/metadata/v2", {"_id": "abc", "name": "x"}, token)
        self.assertEqual(second.code, 409)

    def test_two_users_different_payload_do_not_merge(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "abc")

        r1 = self._post("/metadata/v2", {"_id": "abc", "name": "x"}, t1)
        r2 = self._post("/metadata/v2", {"_id": "abc", "name": "y"}, t2)

        self.assertEqual(r1.code, 200)
        self.assertEqual(r2.code, 200)
        self.assertEqual(json.loads(r1.body)["status"], "pending")
        self.assertEqual(json.loads(r2.body)["status"], "pending")
        self.assertEqual(len(plugin._PENDING_UPSERTS), 2)

    def test_canonical_body_independent_of_key_order(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "abc")

        r1 = self._post("/metadata/v2", {"_id": "abc", "a": 1, "b": 2}, t1)
        self.assertEqual(r1.code, 200)
        self.assertEqual(len(plugin._PENDING_UPSERTS), 1)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_client.upsert_one_docdb_record.return_value = mock_response

        with patch.object(plugin, "MetadataDbClient", return_value=mock_client):
            r2 = self._post("/metadata/v2", {"b": 2, "a": 1, "_id": "abc"}, t2)

        self.assertEqual(r2.code, 200)
        self.assertEqual(json.loads(r2.body)["status"], "submitted")
        self.assertEqual(len(plugin._PENDING_UPSERTS), 0)

    def test_second_distinct_user_triggers_successful_upsert(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "abc")

        body = {"_id": "abc", "name": "x"}
        self._post("/metadata/v2", body, t1)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"created": True}
        mock_client.upsert_one_docdb_record.return_value = mock_response

        with patch.object(plugin, "MetadataDbClient", return_value=mock_client) as cls:
            response = self._post("/metadata/v2", body, t2)

        cls.assert_called_once_with(host=plugin.DOCDB_HOST, version="v2")
        mock_client.upsert_one_docdb_record.assert_called_once_with(body)

        self.assertEqual(response.code, 201)
        payload = json.loads(response.body)
        self.assertEqual(payload["status"], "submitted")
        self.assertEqual(payload["docdb_status"], 201)
        self.assertEqual(payload["docdb_response"], {"created": True})

        self.assertNotIn(t1, plugin._ISSUED_TOKENS)
        self.assertNotIn(t2, plugin._ISSUED_TOKENS)
        self.assertEqual(plugin._PENDING_UPSERTS, {})

    def test_v1_route_uses_v1_client(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "abc")

        body = {"_id": "abc"}
        self._post("/metadata/v1", body, t1)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_client.upsert_one_docdb_record.return_value = mock_response

        with patch.object(plugin, "MetadataDbClient", return_value=mock_client) as cls:
            response = self._post("/metadata/v1", body, t2)

        cls.assert_called_once_with(host=plugin.DOCDB_HOST, version="v1")
        self.assertEqual(response.code, 200)

    def test_failed_upsert_preserves_tokens_for_retry(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "abc")

        body = {"_id": "abc"}
        self._post("/metadata/v2", body, t1)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "boom"}
        mock_response.text = "boom"
        mock_client.upsert_one_docdb_record.return_value = mock_response

        with patch.object(plugin, "MetadataDbClient", return_value=mock_client):
            response = self._post("/metadata/v2", body, t2)

        self.assertEqual(response.code, 500)
        payload = json.loads(response.body)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["docdb_status"], 500)

        self.assertIn(t1, plugin._ISSUED_TOKENS)
        self.assertIn(t2, plugin._ISSUED_TOKENS)
        key = next(iter(plugin._PENDING_UPSERTS))
        self.assertEqual(
            plugin._PENDING_UPSERTS[key]["submissions"], {"alice": t1, "bob": t2}
        )

    def test_failed_upsert_then_retry_with_new_token_succeeds(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "abc")
        body = {"_id": "abc"}
        self._post("/metadata/v2", body, t1)

        mock_client = MagicMock()
        mock_fail = MagicMock()
        mock_fail.status_code = 500
        mock_fail.json.return_value = {"error": "boom"}
        mock_fail.text = "boom"
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {"ok": True}
        mock_client.upsert_one_docdb_record.side_effect = [mock_fail, mock_ok]

        with patch.object(plugin, "MetadataDbClient", return_value=mock_client):
            failed = self._post("/metadata/v2", body, t2)
            self.assertEqual(failed.code, 500)
            retry = self._post("/metadata/v2", body, t2)

        self.assertEqual(retry.code, 200)
        self.assertEqual(json.loads(retry.body)["status"], "submitted")
        self.assertEqual(plugin._PENDING_UPSERTS, {})

    def test_upsert_client_exception_returns_502(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "abc")
        body = {"_id": "abc"}
        self._post("/metadata/v2", body, t1)

        mock_client = MagicMock()
        mock_client.upsert_one_docdb_record.side_effect = RuntimeError("network down")

        with patch.object(plugin, "MetadataDbClient", return_value=mock_client):
            response = self._post("/metadata/v2", body, t2)

        self.assertEqual(response.code, 502)
        self.assertIn(t1, plugin._ISSUED_TOKENS)
        self.assertIn(t2, plugin._ISSUED_TOKENS)

    def test_expired_token_is_pruned(self):
        token = self._issue("alice", "abc")
        plugin._ISSUED_TOKENS[token]["issued_at"] = (
            plugin._now() - plugin.AUTH_TOKEN_TTL_SECONDS - 10
        )
        response = self._post("/metadata/v2", {"_id": "abc"}, token)
        self.assertEqual(response.code, 401)
        self.assertNotIn(token, plugin._ISSUED_TOKENS)

    def test_invalid_token_body_indicates_likely_restart(self):
        original = plugin._PROCESS_STARTED_AT
        plugin._PROCESS_STARTED_AT = plugin._now()
        try:
            response = self._post("/metadata/v2", {"_id": "abc"}, "bogus-token")
        finally:
            plugin._PROCESS_STARTED_AT = original
        self.assertEqual(response.code, 401)
        self.assertIn("invalid_token", response.headers.get("WWW-Authenticate", ""))
        body = json.loads(response.body)
        self.assertEqual(body["error"], "invalid_token")
        self.assertTrue(body["likely_restart"])
        self.assertIn("restart", body["detail"].lower())

    def test_invalid_token_body_no_restart_after_full_ttl(self):
        original = plugin._PROCESS_STARTED_AT
        plugin._PROCESS_STARTED_AT = plugin._now() - plugin.AUTH_TOKEN_TTL_SECONDS - 1
        try:
            response = self._post("/metadata/v2", {"_id": "abc"}, "bogus-token")
        finally:
            plugin._PROCESS_STARTED_AT = original
        self.assertEqual(response.code, 401)
        body = json.loads(response.body)
        self.assertFalse(body["likely_restart"])

    def test_pending_response_includes_other_pending_hashes(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "abc")
        r1 = self._post("/metadata/v2", {"_id": "abc", "name": "x"}, t1)
        first_hash = json.loads(r1.body)["body_hash"]
        r2 = self._post("/metadata/v2", {"_id": "abc", "name": "y"}, t2)
        self.assertEqual(r2.code, 200)
        payload = json.loads(r2.body)
        self.assertEqual(payload["status"], "pending")
        self.assertIn("other_pending_hashes", payload)
        self.assertIn(first_hash, payload["other_pending_hashes"])
        self.assertNotIn(payload["body_hash"], payload["other_pending_hashes"])


class TestPendingMetadataHandler(AsyncHTTPTestCase):
    """Tests for GET /metadata/v{1,2}/pending"""

    def get_app(self) -> Application:
        return _make_app()

    def setUp(self):
        super().setUp()
        _reset_state()

    def _issue(self, user: str, record_id: str) -> str:
        token = "tok-" + user + "-" + record_id
        plugin._ISSUED_TOKENS[token] = {
            "user": user,
            "id": record_id,
            "issued_at": plugin._now(),
        }
        return token

    def test_missing_id(self):
        response = self.fetch("/metadata/v2/pending")
        self.assertEqual(response.code, 400)

    def test_no_pending_returns_empty_list(self):
        response = self.fetch("/metadata/v2/pending?id=abc")
        self.assertEqual(response.code, 200)
        body = json.loads(response.body)
        self.assertEqual(body["id"], "abc")
        self.assertEqual(body["version"], "v2")
        self.assertEqual(body["pending"], [])

    def test_lists_pending_for_matching_version_and_id(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "abc")
        self.fetch(
            "/metadata/v2?" + urlencode({"auth-token": t1}),
            method="POST",
            body=json.dumps({"_id": "abc", "name": "x"}),
            headers={"Content-Type": "application/json"},
        )
        self.fetch(
            "/metadata/v2?" + urlencode({"auth-token": t2}),
            method="POST",
            body=json.dumps({"_id": "abc", "name": "y"}),
            headers={"Content-Type": "application/json"},
        )
        response = self.fetch("/metadata/v2/pending?id=abc")
        self.assertEqual(response.code, 200)
        body = json.loads(response.body)
        self.assertEqual(len(body["pending"]), 2)
        for entry in body["pending"]:
            self.assertIn("body_hash", entry)
            self.assertEqual(entry["submissions"], 1)
            self.assertEqual(entry["version"], "v2")
            self.assertEqual(entry["id"], "abc")
            self.assertEqual(entry["required"], plugin.REQUIRED_DISTINCT_USERS)
            self.assertEqual(entry["body"]["_id"], "abc")
            self.assertIn(entry["body"]["name"], {"x", "y"})

    def test_does_not_leak_other_version_or_other_id(self):
        t = self._issue("alice", "abc")
        self.fetch(
            "/metadata/v1?" + urlencode({"auth-token": t}),
            method="POST",
            body=json.dumps({"_id": "abc"}),
            headers={"Content-Type": "application/json"},
        )
        response = self.fetch("/metadata/v2/pending?id=abc")
        self.assertEqual(json.loads(response.body)["pending"], [])
        response = self.fetch("/metadata/v1/pending?id=other")
        self.assertEqual(json.loads(response.body)["pending"], [])


class TestPendingMetadataAllHandler(AsyncHTTPTestCase):
    """Tests for GET /metadata/pending (combined across both versions)."""

    def get_app(self) -> Application:
        return _make_app()

    def setUp(self):
        super().setUp()
        _reset_state()

    def _issue(self, user: str, record_id: str) -> str:
        token = "tok-" + user + "-" + record_id
        plugin._ISSUED_TOKENS[token] = {
            "user": user,
            "id": record_id,
            "issued_at": plugin._now(),
        }
        return token

    def test_no_pending_returns_empty_list(self):
        response = self.fetch("/metadata/pending")
        self.assertEqual(response.code, 200)
        body = json.loads(response.body)
        self.assertEqual(body, {"pending": []})

    def test_lists_pending_across_versions_with_bodies(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "xyz")
        self.fetch(
            "/metadata/v1?" + urlencode({"auth-token": t1}),
            method="POST",
            body=json.dumps({"_id": "abc", "name": "v1-record"}),
            headers={"Content-Type": "application/json"},
        )
        self.fetch(
            "/metadata/v2?" + urlencode({"auth-token": t2}),
            method="POST",
            body=json.dumps({"_id": "xyz", "name": "v2-record"}),
            headers={"Content-Type": "application/json"},
        )
        response = self.fetch("/metadata/pending")
        self.assertEqual(response.code, 200)
        body = json.loads(response.body)
        self.assertEqual(len(body["pending"]), 2)
        by_id = {entry["id"]: entry for entry in body["pending"]}
        self.assertEqual(by_id["abc"]["version"], "v1")
        self.assertEqual(by_id["abc"]["body"]["name"], "v1-record")
        self.assertEqual(by_id["abc"]["submissions"], 1)
        self.assertEqual(by_id["xyz"]["version"], "v2")
        self.assertEqual(by_id["xyz"]["body"]["name"], "v2-record")

    def test_excludes_completed_upserts(self):
        t1 = self._issue("alice", "abc")
        t2 = self._issue("bob", "abc")
        body = {"_id": "abc", "name": "x"}
        self.fetch(
            "/metadata/v2?" + urlencode({"auth-token": t1}),
            method="POST",
            body=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_client.upsert_one_docdb_record.return_value = mock_response
        with patch.object(plugin, "MetadataDbClient", return_value=mock_client):
            self.fetch(
                "/metadata/v2?" + urlencode({"auth-token": t2}),
                method="POST",
                body=json.dumps(body),
                headers={"Content-Type": "application/json"},
            )
        response = self.fetch("/metadata/pending")
        self.assertEqual(json.loads(response.body)["pending"], [])


class TestCorsHeaders(AsyncHTTPTestCase):
    """Tests for CORS handling on /metadata/* endpoints."""

    def get_app(self) -> Application:
        return _make_app()

    def setUp(self):
        super().setUp()
        _reset_state()

    def test_allowed_origin_gets_cors_headers(self):
        origin = "https://data.allenneuraldynamics.org"
        response = self.fetch(
            "/metadata/v2",
            method="OPTIONS",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
            allow_nonstandard_methods=True,
        )
        self.assertEqual(response.code, 204)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods", ""))
        self.assertIn("Content-Type", response.headers.get("Access-Control-Allow-Headers", ""))

    def test_test_domain_origin_is_rejected_for_cors(self):
        response = self.fetch(
            "/metadata/v2",
            method="OPTIONS",
            headers={
                "Origin": "https://data.allenneuraldynamics-test.org",
                "Access-Control-Request-Method": "POST",
            },
            allow_nonstandard_methods=True,
        )
        self.assertEqual(response.code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_disallowed_origin_no_cors_header(self):
        response = self.fetch(
            "/metadata/v2",
            method="OPTIONS",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
            allow_nonstandard_methods=True,
        )
        self.assertEqual(response.code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_http_origin_is_rejected(self):
        response = self.fetch(
            "/metadata/v2",
            method="OPTIONS",
            headers={
                "Origin": "http://qc.allenneuraldynamics.org",
                "Access-Control-Request-Method": "POST",
            },
            allow_nonstandard_methods=True,
        )
        self.assertEqual(response.code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)


class TestCanonicalBody(unittest.TestCase):
    """Tests for _canonical_body helper"""

    def test_key_order_independent_hash(self):
        h1, _ = plugin._canonical_body(json.dumps({"a": 1, "b": 2}).encode())
        h2, _ = plugin._canonical_body(json.dumps({"b": 2, "a": 1}).encode())
        self.assertEqual(h1, h2)

    def test_different_payloads_have_different_hashes(self):
        h1, _ = plugin._canonical_body(b'{"a": 1}')
        h2, _ = plugin._canonical_body(b'{"a": 2}')
        self.assertNotEqual(h1, h2)


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
