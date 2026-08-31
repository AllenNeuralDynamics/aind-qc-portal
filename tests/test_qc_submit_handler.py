"""Tests for POST/OPTIONS /api/qc/submit (QcSubmitHandler) and _verified_qc_actor.

Kept separate from test_plugin.py because it exercises a handler that is
deliberately isolated from the rest of the app (see the try/except around
the `aind_qc_portal.qc_edit` import in plugin.py) — a regression here should
never look like a regression in the unrelated /metadata/* surface.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import requests
from cryptography.hazmat.primitives.asymmetric import rsa
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

from aind_qc_portal import plugin
from aind_qc_portal.qc_edit import qc_hash

ALLOWED_ORIGIN = "https://data.allenneuraldynamics.org"
ISSUER = "https://login.microsoftonline.com/test-tenant/v2.0"
AUDIENCE = "test-client-id"


def _make_app() -> Application:
    return Application(plugin.ROUTES, cookie_secret="test-secret")


def _fixed_config(**overrides):
    config = {
        "enabled": True,
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "jwks_url": "https://login.microsoftonline.com/test-tenant/discovery/v2.0/keys",
        "origins": (ALLOWED_ORIGIN,),
    }
    config.update(overrides)
    return config


def _record(metric_value=0.5, status_history=None, notes="original notes"):
    return {
        "_id": "record-1",
        "name": "asset-1",
        "quality_control": {
            "object_type": "Quality control",
            "schema_version": "2.4.0",
            "metrics": [
                {
                    "object_type": "QC metric",
                    "name": "drift",
                    "modality": {"name": "Extracellular electrophysiology", "abbreviation": "ecephys"},
                    "stage": "Processing",
                    "value": metric_value,
                    "status_history": status_history
                    if status_history is not None
                    else [
                        {
                            "object_type": "QC status",
                            "evaluator": "system",
                            "status": "Pending",
                            "timestamp": "2024-01-01T00:00:00Z",
                        }
                    ],
                    "tags": {},
                }
            ],
            "notes": notes,
            "default_grouping": ["ECEPHYS"],
            "allow_tag_failures": [],
        },
    }


class _QcSubmitTestCase(AsyncHTTPTestCase):
    """Base case: valid auth/CORS/config, real record + real hash, mocked DocDB."""

    def get_app(self) -> Application:
        return _make_app()

    def setUp(self):
        super().setUp()
        self.record = _record()
        self.upsert_response = MagicMock(status_code=200)
        self.docdb_client = MagicMock()
        self.docdb_client._upsert_one_record.return_value = self.upsert_response

        patches = [
            patch.object(plugin, "_qc_api_config", lambda: _fixed_config()),
            patch.object(plugin, "_verified_qc_actor", self._verify_actor),
            patch.object(plugin, "_fetch_live_record", lambda version, rid: self.record),
            patch.object(plugin, "_docdb_client_for", lambda version: self.docdb_client),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _verify_actor(self, token, config):
        if token != "good-token":
            raise ValueError("Invalid QC identity token")
        return "verified-actor@allenneuraldynamics.org"

    def _post(self, body, token="good-token", origin=ALLOWED_ORIGIN, raw_body=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return self.fetch(
            "/api/qc/submit",
            method="POST",
            body=raw_body if raw_body is not None else json.dumps(body),
            headers=headers,
        )

    def _good_payload(self, **overrides):
        payload = {
            "record_id": "record-1",
            "expected_qc_hash": qc_hash(self.record["quality_control"]),
            "changes": [{"metric_name": "drift", "value": 0.94, "status": "Pass"}],
        }
        payload.update(overrides)
        return payload


class TestCors(_QcSubmitTestCase):
    def test_preflight_allowed_origin(self):
        response = self.fetch(
            "/api/qc/submit", method="OPTIONS", headers={"Origin": ALLOWED_ORIGIN}, allow_nonstandard_methods=True
        )
        self.assertEqual(response.code, 204)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], ALLOWED_ORIGIN)

    def test_preflight_disallowed_origin(self):
        response = self.fetch(
            "/api/qc/submit",
            method="OPTIONS",
            headers={"Origin": "https://evil.example.com"},
            allow_nonstandard_methods=True,
        )
        self.assertEqual(response.code, 403)

    def test_post_from_disallowed_origin(self):
        response = self._post(self._good_payload(), origin="https://evil.example.com")
        self.assertEqual(response.code, 403)
        self.assertEqual(json.loads(response.body)["error"], "origin_not_allowed")

    def test_wildcard_is_never_set(self):
        response = self.fetch(
            "/api/qc/submit", method="OPTIONS", headers={"Origin": ALLOWED_ORIGIN}, allow_nonstandard_methods=True
        )
        self.assertNotEqual(response.headers.get("Access-Control-Allow-Origin"), "*")


class TestAuthentication(_QcSubmitTestCase):
    def test_missing_authorization_header_is_401(self):
        response = self._post(self._good_payload(), token=None)
        self.assertEqual(response.code, 401)
        self.assertEqual(json.loads(response.body)["error"], "unauthenticated")

    def test_malformed_authorization_header_is_401(self):
        response = self.fetch(
            "/api/qc/submit",
            method="POST",
            body=json.dumps(self._good_payload()),
            headers={"Content-Type": "application/json", "Origin": ALLOWED_ORIGIN, "Authorization": "Basic xyz"},
        )
        self.assertEqual(response.code, 401)

    def test_invalid_token_is_401(self):
        response = self._post(self._good_payload(), token="bad-token")
        self.assertEqual(response.code, 401)

    def test_error_body_never_leaks_token_or_internals(self):
        response = self._post(self._good_payload(), token="bad-token")
        self.assertNotIn(b"bad-token", response.body)


class TestRequestValidation(_QcSubmitTestCase):
    def test_unknown_top_level_field_is_400(self):
        response = self._post(self._good_payload(evaluator="someone-else"))
        self.assertEqual(response.code, 400)
        self.assertEqual(json.loads(response.body)["error"], "unsupported_request_field")

    def test_malformed_json_is_400(self):
        response = self._post({}, raw_body="not json")
        self.assertEqual(response.code, 400)

    def test_missing_record_id_is_400(self):
        response = self._post(self._good_payload(record_id=""))
        self.assertEqual(response.code, 400)
        self.assertEqual(json.loads(response.body)["error"], "record_id_required")

    def test_malformed_expected_hash_is_400(self):
        response = self._post(self._good_payload(expected_qc_hash="not-a-hash"))
        self.assertEqual(response.code, 400)
        self.assertEqual(json.loads(response.body)["error"], "invalid_expected_qc_hash")

    def test_empty_changes_without_notes_is_400(self):
        response = self._post(self._good_payload(changes=[]))
        self.assertEqual(response.code, 400)
        self.assertEqual(json.loads(response.body)["error"], "no_changes")

    def test_empty_changes_with_notes_is_accepted(self):
        response = self._post(self._good_payload(changes=[], notes="updated"))
        self.assertEqual(response.code, 200)

    def test_non_string_notes_is_400(self):
        response = self._post(self._good_payload(notes=123))
        self.assertEqual(response.code, 400)
        self.assertEqual(json.loads(response.body)["error"], "invalid_notes")

    def test_record_not_found_is_404(self):
        with patch.object(plugin, "_fetch_live_record", lambda version, rid: None):
            response = self._post(self._good_payload())
        self.assertEqual(response.code, 404)

    def test_unknown_metric_name_is_400(self):
        response = self._post(self._good_payload(changes=[{"metric_name": "does-not-exist", "value": 1}]))
        self.assertEqual(response.code, 400)
        self.assertEqual(json.loads(response.body)["error"], "malformed_request")


class TestStaleRecord(_QcSubmitTestCase):
    def test_stale_hash_is_409_without_upsert(self):
        response = self._post(self._good_payload(expected_qc_hash="a" * 64))
        self.assertEqual(response.code, 409)
        self.assertEqual(json.loads(response.body)["error"], "stale_record")
        self.docdb_client._upsert_one_record.assert_not_called()


class TestSuccessfulSubmission(_QcSubmitTestCase):
    def test_value_and_status_change_applied_with_verified_actor(self):
        response = self._post(self._good_payload())
        self.assertEqual(response.code, 200)
        body = json.loads(response.body)
        self.assertEqual(body["status"], "applied")
        self.assertEqual(body["actor"], "verified-actor@allenneuraldynamics.org")
        self.assertEqual(body["changed_metrics"], 1)

        call = self.docdb_client._upsert_one_record.call_args
        new_qc = call.kwargs["update"]["$set"]["quality_control"]
        self.assertEqual(new_qc["metrics"][0]["value"], 0.94)
        self.assertEqual(new_qc["metrics"][0]["status_history"][-1]["status"], "Pass")
        self.assertEqual(
            new_qc["metrics"][0]["status_history"][-1]["evaluator"], "verified-actor@allenneuraldynamics.org"
        )

    def test_notes_change_applied(self):
        response = self._post(self._good_payload(changes=[], notes="brand new notes"))
        self.assertEqual(response.code, 200)
        call = self.docdb_client._upsert_one_record.call_args
        new_qc = call.kwargs["update"]["$set"]["quality_control"]
        self.assertEqual(new_qc["notes"], "brand new notes")

    def test_client_can_never_set_evaluator_or_curator_fields(self):
        response = self._post(self._good_payload())
        self.assertEqual(response.code, 200)
        call = self.docdb_client._upsert_one_record.call_args
        new_qc = call.kwargs["update"]["$set"]["quality_control"]
        self.assertEqual(
            new_qc["metrics"][0]["status_history"][-1]["evaluator"], "verified-actor@allenneuraldynamics.org"
        )


class TestWriteFailureModes(_QcSubmitTestCase):
    def test_docdb_write_failure_is_502(self):
        self.docdb_client._upsert_one_record.side_effect = requests.exceptions.HTTPError(
            response=MagicMock(status_code=500)
        )
        response = self._post(self._good_payload())
        self.assertEqual(response.code, 502)
        self.assertEqual(json.loads(response.body)["error"], "docdb_unavailable")

    def test_write_filters_on_id_only(self):
        self._post(self._good_payload())
        self.assertEqual(self.docdb_client._upsert_one_record.call_args.kwargs["record_filter"], {"_id": "record-1"})

    def test_docdb_read_failure_is_502(self):
        def _boom(version, rid):
            raise RuntimeError("docdb down")

        with patch.object(plugin, "_fetch_live_record", _boom):
            response = self._post(self._good_payload())
        self.assertEqual(response.code, 502)
        self.assertEqual(json.loads(response.body)["error"], "docdb_unavailable")


class TestFeatureFlags(_QcSubmitTestCase):
    def test_disabled_api_is_503(self):
        with patch.object(plugin, "_qc_api_config", lambda: _fixed_config(enabled=False)):
            response = self._post(self._good_payload())
        self.assertEqual(response.code, 503)
        self.assertEqual(json.loads(response.body)["error"], "qc_api_disabled")


class TestImportIsolation(_QcSubmitTestCase):
    """A broken qc_edit import must degrade this endpoint, not the whole app."""

    def test_broken_qc_edit_import_returns_503_not_a_crash(self):
        with patch.object(plugin, "_QC_EDIT_IMPORT_ERROR", ImportError("simulated missing module")):
            response = self._post(self._good_payload())
        self.assertEqual(response.code, 503)
        self.assertEqual(json.loads(response.body)["error"], "qc_api_unavailable")

    def test_other_routes_unaffected_when_qc_edit_import_is_broken(self):
        with patch.object(plugin, "_QC_EDIT_IMPORT_ERROR", ImportError("simulated missing module")):
            response = self.fetch("/metadata/me", headers={"Origin": ALLOWED_ORIGIN})
        self.assertEqual(response.code, 401)  # unaffected: still a normal, well-formed auth failure


class TestVerifiedQcActor(unittest.TestCase):
    """_verified_qc_actor's own JWT validation, independent of the handler."""

    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()

    def setUp(self):
        plugin._jwks_clients.clear()
        self.addCleanup(plugin._jwks_clients.clear)

    def _config(self):
        return _fixed_config()

    def _patched_jwks(self):
        instance = MagicMock()
        instance.get_signing_key_from_jwt.return_value = MagicMock(key=self.public_key)
        return patch("jwt.PyJWKClient", return_value=instance)

    def _token(self, **claim_overrides):
        now = datetime.now(timezone.utc)
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "user-object-id",
            "oid": "user-object-id",
            "exp": now + timedelta(hours=1),
            "iat": now,
            "preferred_username": "alice@allenneuraldynamics.org",
        }
        claims.update(claim_overrides)
        return jwt.encode(claims, self.private_key, algorithm="RS256")

    def test_valid_token_returns_preferred_username(self):
        with self._patched_jwks():
            actor = plugin._verified_qc_actor(self._token(), self._config())
        self.assertEqual(actor, "alice@allenneuraldynamics.org")

    def test_falls_back_to_email_then_oid(self):
        with self._patched_jwks():
            actor = plugin._verified_qc_actor(
                self._token(preferred_username=None, email="bob@allenneuraldynamics.org"), self._config()
            )
        self.assertEqual(actor, "bob@allenneuraldynamics.org")

    def test_expired_token_is_rejected(self):
        expired = self._token(exp=datetime.now(timezone.utc) - timedelta(hours=1))
        with self._patched_jwks():
            with self.assertRaises(ValueError):
                plugin._verified_qc_actor(expired, self._config())

    def test_wrong_audience_is_rejected(self):
        with self._patched_jwks():
            with self.assertRaises(ValueError):
                plugin._verified_qc_actor(self._token(aud="some-other-app"), self._config())

    def test_wrong_issuer_is_rejected(self):
        with self._patched_jwks():
            with self.assertRaises(ValueError):
                plugin._verified_qc_actor(
                    self._token(iss="https://login.microsoftonline.com/other-tenant/v2.0"), self._config()
                )

    def test_malformed_token_is_rejected(self):
        with self._patched_jwks():
            with self.assertRaises(ValueError):
                plugin._verified_qc_actor("not-a-jwt", self._config())

    def test_missing_identity_claims_is_rejected(self):
        token = self._token(sub=None, oid=None)
        with self._patched_jwks():
            with self.assertRaises((ValueError, Exception)):
                plugin._verified_qc_actor(token, self._config())

    def test_incomplete_server_config_fails_closed(self):
        with self.assertRaises(RuntimeError):
            plugin._verified_qc_actor(self._token(), _fixed_config(issuer=""))


if __name__ == "__main__":
    unittest.main()
