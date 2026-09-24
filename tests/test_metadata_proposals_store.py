"""Unit tests for the metadata proposal store backends."""

import io
import json
import unittest
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from aind_qc_portal.metadata_proposals import store


class TestMetadataProposalStore(unittest.TestCase):
    """Test the temporary memory backend and the preserved S3 backend."""

    def setUp(self):
        """Start each test with an empty process-local proposal store."""
        with store._MEMORY_LOCK:
            store._MEMORY_PROPOSALS.clear()

    def tearDown(self):
        """Leave the process-local proposal store empty for other tests."""
        with store._MEMORY_LOCK:
            store._MEMORY_PROPOSALS.clear()

    def _proposal(self, proposal_id, *, version="v1", record_id=None, status="open", created_at=None):
        """Build a small proposal envelope for backend tests."""
        record_id = record_id or proposal_id
        proposal = store.new_proposal(
            version=version,
            record_id=record_id,
            record_name=f"asset-{record_id}",
            body={"_id": record_id, "value": proposal_id},
            base={"_id": record_id, "value": "base"},
            note="test",
            author="alice",
        )
        proposal["proposal_id"] = proposal_id
        proposal["status"] = status
        if created_at is not None:
            proposal["created_at"] = created_at
        return proposal

    @staticmethod
    def _client_error(code):
        """Build a botocore client error for the requested S3 error code."""
        return ClientError({"Error": {"Code": code, "Message": code}}, "GetObject")

    @patch.object(store, "METADATA_PROPOSALS_BACKEND", "memory")
    def test_memory_backend_round_trip_and_filters(self):
        """Store, retrieve, filter, and isolate copies of memory-backed proposals."""
        first = self._proposal("p1", version="v1", record_id="asset-1", created_at="2026-01-01")
        second = self._proposal("p2", version="v2", record_id="asset-2", status="rejected", created_at="2026-02-01")

        store.put_proposal(first)
        store.put_proposal(second)

        loaded = store.get_proposal("p1")
        loaded["body"]["value"] = "mutated outside the store"
        loaded["status"] = "rejected"
        self.assertEqual(store.get_proposal("p1")["body"]["value"], "p1")
        self.assertEqual(store.get_proposal("p1")["status"], "open")
        self.assertIsNone(store.get_proposal("missing"))
        self.assertIsNone(store._copy_proposal(None))

        all_proposals = store.list_proposals()
        self.assertEqual([proposal["proposal_id"] for proposal in all_proposals], ["p2", "p1"])
        self.assertEqual([proposal["proposal_id"] for proposal in store.list_proposals(status="open")], ["p1"])
        self.assertEqual(store.list_proposals(status="rejected", version="v1"), [])
        self.assertEqual(store.list_proposals(status="all", version="v1", record_id="asset-2"), [])
        self.assertEqual([proposal["proposal_id"] for proposal in store.list_proposals(record_id="asset-1")], ["p1"])

    @patch.object(store, "METADATA_PROPOSALS_BACKEND", "memory")
    def test_memory_filters_before_copying_full_records(self):
        """Record-specific duplicate checks must not clone the whole queue."""
        store.put_proposal(self._proposal("p1", record_id="asset-1"))
        store.put_proposal(self._proposal("p2", record_id="asset-2"))

        original_copy = store._copy_proposal
        with patch.object(store, "_copy_proposal", wraps=original_copy) as copy_proposal:
            listed = store.list_proposals(status="open", record_id="asset-1")

        self.assertEqual([proposal["proposal_id"] for proposal in listed], ["p1"])
        self.assertEqual(copy_proposal.call_count, 1)

    @patch.object(store, "METADATA_PROPOSALS_BACKEND", "memory")
    def test_summary_omits_large_snapshots_and_groups_same_replacement(self):
        first = self._proposal("p1", record_id="asset-1")
        second = self._proposal("p2", record_id="asset-2")
        second["base"]["value"] = "different-base"
        second["body"]["value"] = first["body"]["value"]
        second.pop("change_key", None)
        second.pop("changed_sections", None)
        store.put_proposal(first)
        store.put_proposal(second)

        summaries = store.list_proposals(status="open", summary=True)

        self.assertEqual(len(summaries), 2)
        self.assertNotIn("base", summaries[0])
        self.assertNotIn("body", summaries[0])
        self.assertNotIn("docdb_response", summaries[0])
        self.assertEqual(summaries[0]["changed_sections"], ["value"])
        self.assertEqual(summaries[0]["change_key"], summaries[1]["change_key"])

    @patch.object(store, "METADATA_PROPOSALS_BACKEND", "s3")
    def test_s3_backend_preserves_put_get_and_list_behavior(self):
        """Route S3 mode through the original object layout and filters."""
        first = self._proposal("p1", version="v1", record_id="asset-1", created_at="2026-01-01")
        second = self._proposal("p2", version="v2", record_id="asset-2", created_at="2026-02-01")
        objects = {
            "metadata-proposals/p1.json": first,
            "metadata-proposals/p2.json": second,
        }
        client = MagicMock()

        def get_object(**kwargs):
            """Return the JSON object requested by the S3 test client."""
            proposal = objects[kwargs["Key"]]
            return {"Body": io.BytesIO(json.dumps(proposal).encode())}

        client.get_object.side_effect = get_object
        client.get_paginator.return_value.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "metadata-proposals/p1.json"},
                    {"Key": "metadata-proposals/p2.json"},
                    {"Key": "metadata-proposals/not-json.txt"},
                ]
            }
        ]

        with patch.object(store, "_s3", return_value=client):
            store.put_proposal(first)
            self.assertEqual(client.put_object.call_args.kwargs["Bucket"], store.S3_BUCKET)
            self.assertEqual(client.put_object.call_args.kwargs["Key"], "metadata-proposals/p1.json")
            self.assertEqual(json.loads(client.put_object.call_args.kwargs["Body"]), first)
            self.assertEqual(store.get_proposal("p1"), first)
            self.assertEqual(store._list_keys(), ["metadata-proposals/p1.json", "metadata-proposals/p2.json"])
            listed = store.list_proposals(status="open", version="v1", record_id="asset-1")
            self.assertEqual([proposal["proposal_id"] for proposal in listed], ["p1"])
            self.assertEqual(store.list_proposals(status="rejected", version="v1"), [])
            self.assertEqual(store.list_proposals(status="all", version="v1", record_id="asset-2"), [])

            client.get_paginator.return_value.paginate.return_value = [{}]
            self.assertEqual(store.list_proposals(), [])

    @patch.object(store, "METADATA_PROPOSALS_BACKEND", "s3")
    def test_s3_read_errors_and_helpers(self):
        """Preserve S3 missing-object handling and malformed-object tolerance."""
        client = MagicMock()
        with patch.object(store.boto3, "client", return_value=client) as client_factory:
            self.assertIs(store._s3(), client)
            client_factory.assert_called_once_with("s3")

        with patch.object(store, "_s3", return_value=client):
            client.get_object.side_effect = self._client_error("NoSuchKey")
            self.assertIsNone(store._get_proposal_s3("missing"))
            client.get_object.side_effect = self._client_error("AccessDenied")
            with self.assertRaises(ClientError):
                store.get_proposal("forbidden")

            client.get_object.side_effect = self._client_error("AccessDenied")
            self.assertIsNone(store._read_key("metadata-proposals/forbidden.json"))
            client.get_object.side_effect = None
            client.get_object.return_value = {"Body": io.BytesIO(b"not json")}
            self.assertIsNone(store._read_key("metadata-proposals/broken.json"))
