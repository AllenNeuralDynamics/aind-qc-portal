"""Unit tests for aind_qc_portal.qc_edit"""

import copy
import unittest
from unittest.mock import MagicMock

import requests

from aind_qc_portal.qc_edit import (
    MISSING,
    QcEditError,
    QcEditWriteError,
    apply_qc_changes,
    canonical_qc_json,
    is_qc_hash,
    qc_hash,
    update_qc_record,
)

# Mirrors web/src/qc/canonical-fixtures.js verbatim. If this drifts from the
# JS fixtures, the browser and server no longer hash the same bytes and the
# stale-record check silently stops meaning anything.
QC_HASH_FIXTURES = [
    (
        {"metrics": [], "notes": ""},
        "d9bcfc79fadae39f5d317d8d953af1452c25c3cfb048fc5c3b3c1c528482b446",
    ),
    (
        {"metrics": [{"name": "drift", "value": 0.94, "status_history": []}], "notes": "Δ QC"},
        "92880929eef1ffa332c6be2396058430d1c760a26c55873706bebf5620897c11",
    ),
    (
        {
            "metrics": [{"name": "m", "value": [1, None, True, {"β": "東京"}]}],
            "numbers": [1, 1.0, 0.000001, 100000000000000000000, 0.0000001],
        },
        "84c0981cf52eaf4bff129b6141eba513c0f023588af112b314d14a4a214eadbc",
    ),
]

DEFAULT_GROUPING = ["ECEPHYS"]


def _metric(**overrides):
    metric = {
        "object_type": "QC metric",
        "name": "drift",
        "modality": {"name": "Extracellular electrophysiology", "abbreviation": "ecephys"},
        "stage": "Processing",
        "value": 0.5,
        "status_history": [
            {
                "object_type": "QC status",
                "evaluator": "system",
                "status": "Pending",
                "timestamp": "2024-01-01T00:00:00Z",
            }
        ],
        "tags": {},
    }
    metric.update(overrides)
    return metric


def _curation_metric(**overrides):
    metric = _metric(
        object_type="Curation metric",
        name="curation-a",
        value=[],
        type="manual",
        curation_history=[],
    )
    metric.update(overrides)
    return metric


def _record(metrics, notes=None, default_grouping=None):
    return {
        "_id": "abc",
        "name": "asset-1",
        "quality_control": {
            "object_type": "Quality control",
            "schema_version": "2.4.0",
            "metrics": metrics,
            "notes": notes,
            "default_grouping": default_grouping or DEFAULT_GROUPING,
            "allow_tag_failures": [],
        },
    }


class TestCanonicalHashFixtures(unittest.TestCase):
    """Cross-language contract: must match web/src/qc/canonical-fixtures.js"""

    def test_fixtures_match(self):
        for value, expected in QC_HASH_FIXTURES:
            self.assertEqual(qc_hash(value), expected, msg=canonical_qc_json(value))

    def test_is_qc_hash(self):
        self.assertTrue(is_qc_hash("a" * 64))
        self.assertFalse(is_qc_hash("A" * 64))  # must be lowercase, like a hex digest
        self.assertFalse(is_qc_hash("a" * 63))
        self.assertFalse(is_qc_hash(12345))
        self.assertFalse(is_qc_hash(None))

    def test_hash_is_order_independent_of_insertion_but_not_of_keys(self):
        a = {"a": 1, "b": 2}
        b = {"b": 2, "a": 1}
        self.assertEqual(qc_hash(a), qc_hash(b))


class TestApplyQcChanges(unittest.TestCase):
    """Mutation semantics must match the Panel write path exactly."""

    def test_replace_regular_metric_value(self):
        record = _record([_metric(name="drift", value=0.5)])
        new_record = apply_qc_changes(record, [{"metric_name": "drift", "value": 0.94}], actor="alice")
        self.assertEqual(new_record["quality_control"]["metrics"][0]["value"], 0.94)
        # Original record must not be mutated.
        self.assertEqual(record["quality_control"]["metrics"][0]["value"], 0.5)

    def test_curation_metric_appends_and_records_history(self):
        record = _record([_curation_metric(value=["existing"], curation_history=[])])
        new_record = apply_qc_changes(
            record, [{"metric_name": "curation-a", "value": {"label": "good"}}], actor="alice"
        )
        metric = new_record["quality_control"]["metrics"][0]
        self.assertEqual(metric["value"], ["existing", '{"label": "good"}'])
        self.assertEqual(len(metric["curation_history"]), 1)
        self.assertEqual(metric["curation_history"][0]["curator"], "alice")

    def test_curation_metric_does_not_double_encode_existing_entries(self):
        record = _record([_curation_metric(value=['{"label": "old"}'], curation_history=[])])
        new_record = apply_qc_changes(record, [{"metric_name": "curation-a", "value": "new"}], actor="alice")
        metric = new_record["quality_control"]["metrics"][0]
        self.assertEqual(metric["value"], ['{"label": "old"}', '"new"'])

    def test_status_change_appends_history_with_actor(self):
        record = _record([_metric(status_history=[])])
        new_record = apply_qc_changes(record, [{"metric_name": "drift", "status": "Pass"}], actor="bob")
        history = new_record["quality_control"]["metrics"][0]["status_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "Pass")
        self.assertEqual(history[0]["evaluator"], "bob")

    def test_value_and_status_in_one_change(self):
        record = _record([_metric(value=0.5, status_history=[])])
        new_record = apply_qc_changes(record, [{"metric_name": "drift", "value": 0.94, "status": "Fail"}], actor="bob")
        metric = new_record["quality_control"]["metrics"][0]
        self.assertEqual(metric["value"], 0.94)
        self.assertEqual(metric["status_history"][-1]["status"], "Fail")

    def test_unsupported_status_rejected(self):
        record = _record([_metric()])
        with self.assertRaises(QcEditError):
            apply_qc_changes(record, [{"metric_name": "drift", "status": "Unknown"}], actor="alice")

    def test_unknown_metric_name_rejected(self):
        record = _record([_metric()])
        with self.assertRaises(QcEditError):
            apply_qc_changes(record, [{"metric_name": "does-not-exist", "value": 1}], actor="alice")

    def test_duplicate_metric_name_rejected(self):
        record = _record([_metric()])
        changes = [
            {"metric_name": "drift", "value": 1},
            {"metric_name": "drift", "status": "Pass"},
        ]
        with self.assertRaises(QcEditError):
            apply_qc_changes(record, changes, actor="alice")

    def test_unsupported_change_field_rejected(self):
        record = _record([_metric()])
        with self.assertRaises(QcEditError):
            apply_qc_changes(record, [{"metric_name": "drift", "evaluator": "eve", "value": 1}], actor="alice")

    def test_change_without_value_or_status_rejected(self):
        record = _record([_metric()])
        with self.assertRaises(QcEditError):
            apply_qc_changes(record, [{"metric_name": "drift"}], actor="alice")

    def test_empty_changes_with_no_notes_is_a_noop_but_still_valid(self):
        record = _record([_metric()])
        new_record = apply_qc_changes(record, [], actor="alice")
        self.assertEqual(new_record["quality_control"], record["quality_control"])

    def test_notes_omitted_leaves_notes_unchanged(self):
        record = _record([_metric()], notes="original")
        new_record = apply_qc_changes(record, [], actor="alice", notes=MISSING)
        self.assertEqual(new_record["quality_control"]["notes"], "original")

    def test_notes_explicit_empty_string_clears_notes(self):
        record = _record([_metric()], notes="original")
        new_record = apply_qc_changes(record, [], actor="alice", notes="")
        self.assertEqual(new_record["quality_control"]["notes"], "")

    def test_notes_explicit_value_sets_notes(self):
        record = _record([_metric()], notes="original")
        new_record = apply_qc_changes(record, [], actor="alice", notes="updated")
        self.assertEqual(new_record["quality_control"]["notes"], "updated")

    def test_non_string_notes_rejected(self):
        record = _record([_metric()])
        with self.assertRaises(QcEditError):
            apply_qc_changes(record, [], actor="alice", notes=123)

    def test_schema_validation_failure_is_reported_distinctly(self):
        record = _record([_metric()], default_grouping=None)
        del record["quality_control"]["default_grouping"]
        with self.assertRaises(QcEditError) as ctx:
            apply_qc_changes(record, [], actor="alice")
        self.assertIn("schema validation", str(ctx.exception))

    def test_actor_is_never_taken_from_the_change_payload(self):
        record = _record([_metric(status_history=[])])
        new_record = apply_qc_changes(
            record, [{"metric_name": "drift", "status": "Pass"}], actor="server-verified-actor"
        )
        evaluator = new_record["quality_control"]["metrics"][0]["status_history"][0]["evaluator"]
        self.assertEqual(evaluator, "server-verified-actor")

    def test_original_record_is_not_mutated(self):
        record = _record([_metric(status_history=[])])
        original = copy.deepcopy(record)
        apply_qc_changes(record, [{"metric_name": "drift", "status": "Pass"}], actor="alice")
        self.assertEqual(record, original)


class TestUpdateQcRecord(unittest.TestCase):
    """The write primitive: filters on _id only, sets only quality_control."""

    def test_success_returns_response(self):
        response = MagicMock(status_code=200)
        client = MagicMock()
        client._upsert_one_record.return_value = response
        result = update_qc_record(client, "abc", {"metrics": [], "notes": "x"})
        self.assertIs(result, response)
        call = client._upsert_one_record.call_args
        self.assertEqual(call.kwargs["update"], {"$set": {"quality_control": {"metrics": [], "notes": "x"}}})

    def test_filter_is_id_only(self):
        client = MagicMock()
        client._upsert_one_record.return_value = MagicMock(status_code=200)
        update_qc_record(client, "abc", {"metrics": []})
        # A filter on anything else would make upsert:True insert a duplicate
        # record instead of erroring when it misses.
        self.assertEqual(client._upsert_one_record.call_args.kwargs["record_filter"], {"_id": "abc"})

    def test_other_record_fields_are_never_written(self):
        client = MagicMock()
        client._upsert_one_record.return_value = MagicMock(status_code=200)
        update_qc_record(client, "abc", {"metrics": []})
        self.assertEqual(list(client._upsert_one_record.call_args.kwargs["update"]["$set"]), ["quality_control"])

    def test_bad_status_code_raises(self):
        client = MagicMock()
        client._upsert_one_record.return_value = MagicMock(status_code=500)
        with self.assertRaises(QcEditWriteError):
            update_qc_record(client, "abc", {})

    def test_client_exception_propagates(self):
        client = MagicMock()
        client._upsert_one_record.side_effect = requests.exceptions.HTTPError(response=MagicMock(status_code=500))
        with self.assertRaises(requests.exceptions.HTTPError):
            update_qc_record(client, "abc", {})


if __name__ == "__main__":
    unittest.main()
