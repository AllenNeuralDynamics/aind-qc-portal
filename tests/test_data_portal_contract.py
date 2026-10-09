"""Replay frozen requests captured from Zombie's real QC portal clients."""

import copy
import json
import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application, create_signed_value

from aind_qc_portal import plugin
from aind_qc_portal.api_docs import openapi_spec
from aind_qc_portal.qc_edit import qc_hash
from tests.test_plugin import ALLOWED_ORIGIN, COOKIE_SECRET, _ProposalApiTestCase
from tests.test_qc_submit_handler import _QcSubmitTestCase

CONTRACT = json.loads((Path(__file__).parent / "resources" / "qc-portal-contract.json").read_text())
REQUESTS = {request["name"]: request for request in CONTRACT["requests"]}


class TestContractRouteCoverage(unittest.TestCase):
    """Require contract coverage when new custom endpoint methods are added."""

    def test_every_endpoint_method_has_a_client_or_server_contract(self):
        """All route methods are captured or explicitly covered as server-only."""
        server_only = {(r"/docs/?", "GET"), (r"/openapi\.json", "GET"), ("/upload_metadata", "POST")}
        for route, handler, _ in plugin.ROUTES:
            for method in ("GET", "POST", "DELETE", "PUT", "PATCH"):
                if method.lower() not in handler.__dict__ or (route, method) in server_only:
                    continue
                self.assertTrue(
                    any(
                        request["method"] == method and re.fullmatch(route, request["path"].split("?")[0])
                        for request in REQUESTS.values()
                    ),
                    (route, method),
                )

    def test_documented_qc_fields_include_all_captured_client_fields(self):
        """Keep documented field names and null references aligned with clients."""
        schemas = openapi_spec()["components"]["schemas"]
        for request in REQUESTS.values():
            if request["path"] != "/api/qc/submit":
                continue
            self.assertLessEqual(set(request["body"]), set(schemas["QcSubmit"]["properties"]))
            for change in request["body"]["changes"]:
                self.assertLessEqual(set(change), set(schemas["MetricChange"]["properties"]))
            for metric in request["body"].get("add_metrics", []):
                self.assertLessEqual(set(metric), set(schemas["NewMetric"]["properties"]))
                if metric.get("reference") is None:
                    self.assertTrue(schemas["NewMetric"]["properties"]["reference"]["nullable"])


def _replay(test, name, *, path=None, actor=None, cookie=None):
    """Send a captured request with browser origin and optional test identity."""
    request = REQUESTS[name]
    headers = {**request["headers"], "Origin": ALLOWED_ORIGIN}
    if actor:
        headers["Authorization"] = f"Bearer {actor}"
    if cookie:
        headers["Cookie"] = cookie
    return test.fetch(
        path or request["path"],
        method=request["method"],
        headers=headers,
        body=json.dumps(request["body"]) if "body" in request else None,
        follow_redirects=False,
        allow_nonstandard_methods=True,
    )


class TestDataPortalQcContract(_QcSubmitTestCase):
    """Apply actual browser payloads to real QC mutation and HTTP handlers."""

    def test_all_browser_qc_payloads_are_applied(self):
        """Check hashes, metric shapes, notes, curation, and new metric families."""
        for case in CONTRACT["qc"]:
            with self.subTest(case=case["name"]):
                self.record = copy.deepcopy(case["record"])
                original = copy.deepcopy(self.record)
                self.docdb_client.reset_mock()
                request = REQUESTS[case["name"]]
                self.assertEqual(request["body"]["expected_qc_hash"], qc_hash(self.record["quality_control"]))
                response = _replay(self, case["name"])
                self.assertEqual(response.code, 200, response.body)
                body = json.loads(response.body)
                self.assertEqual(body["status"], "applied")
                self.assertEqual(body["record_id"], self.record["_id"])
                self.assertEqual(body["added_metrics"], len(request["body"].get("add_metrics", [])))
                self.docdb_client._upsert_one_record.assert_called_once()
                call = self.docdb_client._upsert_one_record.call_args.kwargs
                self.assertEqual(call["record_filter"], {"_id": self.record["_id"]})
                self.assertEqual(set(call["update"]["$set"]), {"quality_control"})
                qc = call["update"]["$set"]["quality_control"]
                metrics = {metric["name"]: metric for metric in qc["metrics"]}
                for change in request["body"]["changes"]:
                    metric = metrics[change["metric_name"]]
                    if "delete_curation_indices" in change:
                        self.assertEqual(metric["value"], ["keep", json.dumps(change["value"])])
                        self.assertEqual(len(metric["curation_history"]), 2)
                        self.assertEqual(metric["curation_history"][-1]["curator"], body["actor"])
                    elif "value" in change:
                        self.assertEqual(metric["value"], change["value"])
                    if "status" in change:
                        self.assertEqual(metric["status_history"][-1]["status"], change["status"])
                        self.assertEqual(metric["status_history"][-1]["evaluator"], body["actor"])
                for added in request["body"].get("add_metrics", []):
                    metric = metrics[added["name"]]
                    for field, value in added.items():
                        self.assertEqual(metric[field], value)
                    self.assertEqual(metric["status_history"][-1]["status"], "Pending")
                    self.assertEqual(metric["status_history"][-1]["evaluator"], body["actor"])
                if "notes" in request["body"]:
                    self.assertEqual(qc["notes"], request["body"]["notes"])
                self.assertEqual(
                    qc["default_grouping"],
                    request["body"].get("default_grouping", original["quality_control"]["default_grouping"]),
                )
                self.assertEqual(
                    qc["allow_tag_failures"], ["existing allowance"] + request["body"].get("allow_tag_failures", [])
                )
                self.assertEqual(self.record, original)

    def test_browser_smartspim_request_is_guarded_against_stale_records(self):
        """A client-shaped request must not bypass concurrent edit protection."""
        self.record = copy.deepcopy(next(case["record"] for case in CONTRACT["qc"] if case["name"] == "qc-smartspim"))
        self.record["quality_control"]["notes"] = "changed elsewhere"
        response = _replay(self, "qc-smartspim")
        self.assertEqual(response.code, 409)
        self.assertEqual(json.loads(response.body)["error"], "stale_record")
        self.docdb_client._upsert_one_record.assert_not_called()


class TestDataPortalProposalContract(_ProposalApiTestCase):
    """Replay compact proposal endpoints used by the migration pages."""

    def _create_from_browser(self):
        """Create a proposal with the captured browser request."""
        response = _replay(self, "proposal-create")
        self.assertEqual(response.code, 201, response.body)
        proposal = json.loads(response.body)["proposal"]
        self.assertNotIn("body", proposal)
        self.assertNotIn("base", proposal)
        self.assertIn("body_hash", proposal)
        self.assertEqual(self.store.get(proposal["proposal_id"])["body"], REQUESTS["proposal-create"]["body"]["body"])
        return proposal

    def test_create_list_and_detail_formats(self):
        """Client filters and response envelopes work across the queue and detail."""
        proposal = self._create_from_browser()
        for name in ("list-default", "list-filtered"):
            response = _replay(self, name)
            self.assertEqual(response.code, 200)
            listed = json.loads(response.body)["proposals"]
            self.assertEqual([item["proposal_id"] for item in listed], [proposal["proposal_id"]])
            self.assertNotIn("body", listed[0])
        response = _replay(
            self, "proposal-detail", path=REQUESTS["proposal-detail"]["path"].replace("p1", proposal["proposal_id"])
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body)["proposal"]["body"], REQUESTS["proposal-create"]["body"]["body"])

    def test_browser_rebase_supersedes_previous_proposal(self):
        """The optional supersedes field and compact response remain supported."""
        previous = self._create_from_browser()
        request = REQUESTS["proposal-rebase"]
        payload = {**request["body"], "supersedes": previous["proposal_id"]}
        response = self._post(request["path"], payload, user="good-token")
        self.assertEqual(response.code, 201, response.body)
        self.assertEqual(self.store.get(previous["proposal_id"])["status"], "superseded")
        self.assertNotIn("body", json.loads(response.body)["proposal"])

    def test_approve_reject_and_withdraw_formats(self):
        """Replay every action and check the response fields consumed by clients."""
        for name, status in (
            ("proposal-approve", "applied"),
            ("proposal-reject", "rejected"),
            ("proposal-withdraw", "withdrawn"),
        ):
            with self.subTest(action=name):
                self.store.items.clear()
                self.upsert_calls.clear()
                proposal = self._create_from_browser()
                request = REQUESTS[name]
                path = request["path"].replace("p1", proposal["proposal_id"])
                if name == "proposal-approve":
                    payload = {**request["body"], "body_hash": proposal["body_hash"]}
                    response = self._post(path, payload, user="reviewer")
                else:
                    response = _replay(self, name, path=path)
                self.assertEqual(response.code, 200, response.body)
                returned = json.loads(response.body)["proposal"]
                self.assertEqual(returned["status"], status)
                self.assertNotIn("body", returned)
                self.assertEqual(len(self.upsert_calls), 1 if status == "applied" else 0)
                if status == "applied":
                    self.assertEqual(self.upsert_calls[0], REQUESTS["proposal-create"]["body"]["body"])
                if status == "rejected":
                    self.assertEqual(returned["reason"], request["body"]["reason"])


class TestDataPortalSessionAndMediaContract(AsyncHTTPTestCase):
    """Cover legacy session requests and the media URL consumed by Zombie."""

    def get_app(self):
        """Use production routes with a local signing key."""
        return Application(plugin.ROUTES, cookie_secret=COOKIE_SECRET)

    def test_session_endpoints_match_browser_requests(self):
        """Login redirects, identity JSON, and logout match the legacy client."""
        with patch.object(plugin, "_panel_user_from_handler", return_value="alice"):
            response = _replay(self, "session-login")
        self.assertEqual(response.code, 302)
        self.assertEqual(
            response.headers["Location"], "https://data.allenneuraldynamics.org/migrate/submit?id=abc&version=v2"
        )
        value = create_signed_value(COOKIE_SECRET, plugin.SESSION_COOKIE_NAME, "alice").decode()
        cookie = f"{plugin.SESSION_COOKIE_NAME}={value}"
        response = _replay(self, "session-me", cookie=cookie)
        self.assertEqual(json.loads(response.body), {"authenticated": True, "user": "alice"})
        response = _replay(self, "session-logout", cookie=cookie)
        self.assertEqual(json.loads(response.body), {"authenticated": False})
        self.assertIn(plugin.SESSION_COOKIE_NAME, response.headers["Set-Cookie"])

    def test_media_reference_is_decoded_validated_and_signed(self):
        """Encoded names and relative references retain their exact S3 keys."""
        client = MagicMock()
        client.retrieve_docdb_records.return_value = [
            {
                "name": "asset with spaces",
                "location": "s3://private-bucket/prefix",
                "quality_control": {"metrics": [{"reference": "figures/QC image.png"}]},
            }
        ]
        with (
            patch.object(plugin, "_docdb_client", client),
            patch.object(plugin, "get_s3_url", return_value="https://example.org/signed.png") as sign,
        ):
            response = _replay(self, "media-sign")
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body), {"url": "https://example.org/signed.png"})
        sign.assert_called_once_with("private-bucket", "prefix/figures/QC image.png")
        self.assertEqual(client.retrieve_docdb_records.call_args.kwargs["filter_query"], {"name": "asset with spaces"})

    def test_unassociated_reference_is_not_signed(self):
        """An arbitrary reference cannot be signed using a valid asset name."""
        client = MagicMock()
        client.retrieve_docdb_records.return_value = [{"quality_control": {"metrics": []}}]
        with patch.object(plugin, "_docdb_client", client), patch.object(plugin, "get_s3_url") as sign:
            response = _replay(self, "media-sign")
        self.assertEqual(response.code, 403)
        sign.assert_not_called()

    def test_missing_reference_and_asset_are_not_signed(self):
        """Missing arguments and unknown assets fail before signing."""
        client = MagicMock()
        client.retrieve_docdb_records.return_value = []
        with patch.object(plugin, "_docdb_client", client), patch.object(plugin, "get_s3_url") as sign:
            response = self.fetch("/get-signed-reference/asset")
            self.assertEqual(response.code, 400)
            client.retrieve_docdb_records.assert_not_called()
            response = _replay(self, "media-sign")
            self.assertEqual(response.code, 404)
            sign.assert_not_called()

    def test_temporary_upload_endpoint(self):
        """Legacy temporary uploads pass the whole JSON record to their writer."""
        payload = {"name": "asset-1", "quality_control": {"metrics": []}}
        with patch.object(plugin, "upload_temporary_metadata") as upload:
            response = self.fetch(
                "/upload_metadata",
                method="POST",
                body=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body), {"status": 200})
        upload.assert_called_once_with(payload)

    def test_invalid_temporary_upload_does_not_write(self):
        """Malformed JSON is rejected before the temporary metadata writer."""
        with patch.object(plugin, "upload_temporary_metadata") as upload:
            response = self.fetch("/upload_metadata", method="POST", body="not json")
        self.assertEqual(response.code, 400)
        upload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
