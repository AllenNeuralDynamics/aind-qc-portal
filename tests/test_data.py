"""Unit tests for data.py"""

import copy
import json
import unittest
from datetime import datetime
from unittest.mock import patch

from aind_data_schema.core.quality_control import (
    CurationMetric,
    Modality,
    QCMetric,
    QCStatus,
    QualityControl,
    Stage,
    Status,
)

from aind_qc_portal.view_contents.data_utils import (
    apply_curation_metric_change,
    apply_qc_metric_change,
    apply_status_change,
    create_curation_history_entry,
    create_status_history_entry,
    decode_dict_value,
    encode_dict_value,
    upload_temporary_metadata,
)


class TestEncodeDecodeHelpers(unittest.TestCase):
    """Test the helper functions for encoding and decoding dictionary values in QC metrics"""

    def test_encode_dict_value(self):
        """Test that a dictionary value is correctly encoded as a JSON string with 'json:' prefix"""
        test_dict = {"key": "value", "nested": {"inner": 123}}
        encoded = encode_dict_value(test_dict)
        self.assertTrue(encoded.startswith("json:"))
        self.assertIn("key", encoded)
        self.assertIn("value", encoded)

    def test_encode_non_dict_value(self):
        """Test that non-dictionary values are returned unchanged by the encoding function"""
        self.assertEqual(encode_dict_value("string"), "string")
        self.assertEqual(encode_dict_value(123), 123)
        self.assertEqual(encode_dict_value([1, 2, 3]), [1, 2, 3])

    def test_decode_dict_value(self):
        """Test that a JSON string with 'json:' prefix is correctly decoded back to a dictionary"""
        test_dict = {"key": "value", "nested": {"inner": 123}}
        encoded = f"json:{json.dumps(test_dict)}"
        decoded = decode_dict_value(encoded)
        self.assertEqual(decoded, test_dict)

    def test_decode_non_json_value(self):
        """Test that values without 'json:' prefix are returned unchanged by the decoding function"""
        self.assertEqual(decode_dict_value("string"), "string")
        self.assertEqual(decode_dict_value(123), 123)

    def test_encode_decode_roundtrip(self):
        """Test that encoding and then decoding a dictionary value returns the original dictionary"""
        test_dict = {"status": "Pass", "units": [1, 2, 3], "threshold": 0.5}
        encoded = encode_dict_value(test_dict)
        decoded = decode_dict_value(encoded)
        self.assertEqual(decoded, test_dict)


class TestUploadTemporaryMetadata(unittest.TestCase):
    """Test the function that uploads temporary metadata to the database, ensuring it correctly creates or appends to the metadata dictionary in pn.state"""

    @patch("aind_qc_portal.view_contents.data_utils.pn.state")
    def test_upload_temporary_metadata_creates_metadata_dict(self, mock_state):
        """Test that upload_temporary_metadata creates metadata dict if it doesn't exist"""
        del mock_state.metadata
        test_metadata = {"name": "test_asset", "data": "test_data"}
        
        upload_temporary_metadata(test_metadata)
        
        self.assertEqual(mock_state.metadata, {"test_asset": test_metadata})

    @patch("aind_qc_portal.view_contents.data_utils.pn.state")
    def test_upload_temporary_metadata_appends_to_existing(self, mock_state):
        """Test that upload_temporary_metadata appends to existing metadata dict"""
        mock_state.metadata = {"existing": {"name": "existing", "data": "old"}}
        test_metadata = {"name": "test_asset", "data": "new_data"}
        
        upload_temporary_metadata(test_metadata)
        
        self.assertEqual(len(mock_state.metadata), 2)
        self.assertIn("existing", mock_state.metadata)
        self.assertIn("test_asset", mock_state.metadata)
        self.assertEqual(mock_state.metadata["test_asset"], test_metadata)


class TestHistoryEntryCreation(unittest.TestCase):
    """Test the creation of history entries for curation and status changes"""

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_create_curation_history_entry(self, mock_datetime):
        """Test that a curation history entry is created with the correct structure and timestamp"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        entry = create_curation_history_entry("test_user")

        self.assertEqual(entry["object_type"], "Curation history")
        self.assertEqual(entry["curator"], "test_user")
        self.assertEqual(entry["timestamp"], "2026-01-27T12:00:00")

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_create_status_history_entry(self, mock_datetime):
        """Test that a status history entry is created with the correct structure and timestamp"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        entry = create_status_history_entry("Pass", "test_evaluator")

        self.assertEqual(entry["status"], "Pass")
        self.assertEqual(entry["evaluator"], "test_evaluator")
        self.assertEqual(entry["timestamp"], "2026-01-27T12:00:00")


class TestApplyCurationMetricChange(unittest.TestCase):
    """Test the function that applies changes to curation metrics, ensuring it correctly updates the value and history"""

    def setUp(self):
        """Set up a sample curation metric for testing"""
        self.metric = {"name": "test_curation", "object_type": "Curation metric", "value": [], "curation_history": []}

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_apply_curation_metric_change_to_empty_list(self, mock_datetime):
        """Test that applying a curation change to an empty value list correctly appends the new data and history entry"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        new_data = {"unit_id": 1, "label": "good"}
        apply_curation_metric_change(self.metric, new_data, "curator1")

        self.assertEqual(len(self.metric["value"]), 1)
        self.assertEqual(json.loads(self.metric["value"][0]), new_data)
        self.assertEqual(len(self.metric["curation_history"]), 1)
        self.assertEqual(self.metric["curation_history"][0]["curator"], "curator1")

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_apply_curation_metric_change_appends_to_existing(self, mock_datetime):
        """Test that applying a curation change to a metric with existing values correctly appends the new data and history entry"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        # Add first curation
        first_data = {"unit_id": 1, "label": "good"}
        self.metric["value"] = [json.dumps(first_data)]
        self.metric["curation_history"] = [create_curation_history_entry("curator1")]

        # Add second curation
        second_data = {"unit_id": 2, "label": "bad"}
        apply_curation_metric_change(self.metric, second_data, "curator2")

        self.assertEqual(len(self.metric["value"]), 2)
        self.assertEqual(json.loads(self.metric["value"][0]), first_data)
        self.assertEqual(json.loads(self.metric["value"][1]), second_data)
        self.assertEqual(len(self.metric["curation_history"]), 2)
        self.assertEqual(self.metric["curation_history"][1]["curator"], "curator2")

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_apply_curation_metric_change_initializes_missing_fields(self, mock_datetime):
        """Test that applying a curation change to a metric missing the 'value' or 'curation_history' fields initializes them correctly"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        # Metric without value or curation_history fields
        metric = {"name": "test", "object_type": "Curation metric"}

        new_data = {"unit_id": 1, "label": "good"}
        apply_curation_metric_change(metric, new_data, "curator1")

        self.assertIn("value", metric)
        self.assertIsInstance(metric["value"], list)
        self.assertIn("curation_history", metric)
        self.assertIsInstance(metric["curation_history"], list)
        self.assertEqual(len(metric["value"]), 1)
        self.assertEqual(len(metric["curation_history"]), 1)

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_apply_curation_metric_change_converts_non_list_value(self, mock_datetime):
        """Test that if the existing value is not a list, it is converted to a list before appending the new curation data"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        # Metric with non-list value
        metric = {"name": "test", "object_type": "Curation metric", "value": "invalid_non_list"}

        new_data = {"unit_id": 1, "label": "good"}
        apply_curation_metric_change(metric, new_data, "curator1")

        self.assertIsInstance(metric["value"], list)
        self.assertEqual(len(metric["value"]), 1)


class TestApplyQCMetricChange(unittest.TestCase):
    """Test the function that applies changes to regular QC metrics, ensuring it correctly replaces the value without appending"""

    def test_apply_qc_metric_change_replaces_value(self):
        """Test that applying a QC metric change replaces the existing value rather than appending to it"""
        metric = {"name": "test_qc", "object_type": "QC metric", "value": "old_value"}

        apply_qc_metric_change(metric, "new_value")

        self.assertEqual(metric["value"], "new_value")

    def test_apply_qc_metric_change_with_dict_value(self):
        """Test that applying a QC metric change with a dictionary value correctly replaces the existing value"""
        metric = {"name": "test_qc", "object_type": "QC metric", "value": {"old": "data"}}

        new_value = {"new": "data", "count": 5}
        apply_qc_metric_change(metric, new_value)

        self.assertEqual(metric["value"], new_value)

    def test_apply_qc_metric_change_with_numeric_value(self):
        """Test that applying a QC metric change with a numeric value correctly replaces the existing value"""
        metric = {"name": "test_qc", "object_type": "QC metric", "value": 0.5}

        apply_qc_metric_change(metric, 0.95)

        self.assertEqual(metric["value"], 0.95)


class TestApplyStatusChange(unittest.TestCase):
    """Test the function that applies status changes to QC metrics, ensuring it correctly updates the status history"""

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_apply_status_change_to_existing_history(self, mock_datetime):
        """Test that applying a status change to a metric with existing status history correctly appends the new status entry"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        metric = {
            "name": "test",
            "status_history": [{"status": "Pending", "evaluator": "system", "timestamp": "2026-01-26T10:00:00"}],
        }

        apply_status_change(metric, "Pass", "evaluator1")

        self.assertEqual(len(metric["status_history"]), 2)
        self.assertEqual(metric["status_history"][1]["status"], "Pass")
        self.assertEqual(metric["status_history"][1]["evaluator"], "evaluator1")
        self.assertEqual(metric["status_history"][1]["timestamp"], "2026-01-27T12:00:00")

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_apply_status_change_initializes_missing_history(self, mock_datetime):
        """Test that applying a status change to a metric missing the 'status_history' field initializes it correctly and adds the new status entry"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        metric = {"name": "test"}

        apply_status_change(metric, "Fail", "evaluator1")

        self.assertIn("status_history", metric)
        self.assertIsInstance(metric["status_history"], list)
        self.assertEqual(len(metric["status_history"]), 1)
        self.assertEqual(metric["status_history"][0]["status"], "Fail")

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_apply_status_change_multiple_times(self, mock_datetime):
        """Test that applying multiple status changes in sequence correctly appends each new status entry to the history"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        metric = {"name": "test", "status_history": []}

        apply_status_change(metric, "Pending", "system")
        apply_status_change(metric, "Pass", "user1")
        apply_status_change(metric, "Fail", "user2")

        self.assertEqual(len(metric["status_history"]), 3)
        self.assertEqual(metric["status_history"][0]["status"], "Pending")
        self.assertEqual(metric["status_history"][1]["status"], "Pass")
        self.assertEqual(metric["status_history"][2]["status"], "Fail")


class TestCurationMetricChangeIntegration(unittest.TestCase):
    """Integration tests for the full curation metric update flow"""

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_full_curation_update_workflow(self, mock_datetime):
        """Test the full workflow of applying a curation change and a status change to a curation metric, ensuring all fields are updated correctly"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        # Simulate a curation metric with initial data
        metric = {
            "name": "spike_sorting_curation",
            "object_type": "Curation metric",
            "value": [json.dumps({"unit_id": 1, "label": "good"})],
            "curation_history": [
                {"object_type": "Curation history", "curator": "initial_curator", "timestamp": "2026-01-26T10:00:00"}
            ],
            "status_history": [{"status": "Pending", "evaluator": "system", "timestamp": "2026-01-26T09:00:00"}],
        }

        # Apply a new curation value
        new_curation = {"unit_id": 2, "label": "bad"}
        apply_curation_metric_change(metric, new_curation, "curator2")

        # Apply a status change
        apply_status_change(metric, "Pass", "curator2")

        # Verify the metric has been updated correctly
        self.assertEqual(len(metric["value"]), 2)
        self.assertEqual(json.loads(metric["value"][1]), new_curation)
        self.assertEqual(len(metric["curation_history"]), 2)
        self.assertEqual(metric["curation_history"][1]["curator"], "curator2")
        self.assertEqual(len(metric["status_history"]), 2)
        self.assertEqual(metric["status_history"][1]["status"], "Pass")

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_qc_metric_does_not_append_values(self, mock_datetime):
        """Test that applying a QC metric change to a regular QC metric does not append to the value but replaces it instead"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        # Regular QC metric
        metric = {
            "name": "drift_metric",
            "object_type": "QC metric",
            "value": 0.5,
            "status_history": [{"status": "Pending", "evaluator": "system", "timestamp": "2026-01-26T09:00:00"}],
        }

        # Apply a new value (should replace, not append)
        apply_qc_metric_change(metric, 0.95)
        apply_status_change(metric, "Pass", "evaluator1")

        # Verify value was replaced, not appended
        self.assertEqual(metric["value"], 0.95)
        self.assertNotIsInstance(metric["value"], list)
        self.assertEqual(len(metric["status_history"]), 2)


class TestCurationDataTypes(unittest.TestCase):
    """Test that curation data handles various data types correctly"""

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_curation_with_complex_nested_data(self, mock_datetime):
        """Test that applying a curation change with complex nested data structures is correctly encoded and stored in the metric value"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        metric = {"name": "test", "object_type": "Curation metric", "value": []}

        complex_data = {
            "units": [1, 2, 3],
            "labels": {"1": "good", "2": "bad", "3": "good"},
            "metrics": {"snr": [10.5, 5.2, 8.9], "firing_rate": [2.3, 1.1, 3.4]},
        }

        apply_curation_metric_change(metric, complex_data, "curator1")

        # Verify complex data was stored correctly
        stored_data = json.loads(metric["value"][0])
        self.assertEqual(stored_data, complex_data)
        self.assertEqual(stored_data["units"], [1, 2, 3])
        self.assertEqual(stored_data["labels"]["2"], "bad")
        self.assertEqual(stored_data["metrics"]["snr"][0], 10.5)


class TestSubmitFunctionality(unittest.TestCase):
    """Test the full submission workflow to ensure data integrity"""

    def setUp(self):
        """Create a complete test quality control structure using proper schema objects"""
        # Create proper QC metrics using schema
        qc_metric = QCMetric(
            name="drift_metric",
            modality=Modality.ECEPHYS,
            stage=Stage.RAW,
            value=0.5,
            status_history=[
                QCStatus(status=Status.PENDING, evaluator="system", timestamp=datetime(2026, 1, 26, 10, 0, 0))
            ],
            tags={"probe": "probeA", "session": "session1"},
            description="Drift measurement",
        )

        curation_metric = CurationMetric(
            name="spike_sorting_curation",
            modality=Modality.ECEPHYS,
            stage=Stage.ANALYSIS,
            value=[json.dumps({"unit_id": 1, "label": "good"})],
            status_history=[
                QCStatus(status=Status.PENDING, evaluator="system", timestamp=datetime(2026, 1, 26, 10, 0, 0))
            ],
            curation_history=[
                {
                    "object_type": "Curation history",
                    "curator": "initial_curator",
                    "timestamp": datetime(2026, 1, 26, 10, 0, 0).isoformat(),
                }
            ],
            tags={"probe": "probeA"},
            description="Spike sorting curation",
            type="Spike sorting curation",
        )

        # Create QualityControl object
        qc = QualityControl(
            default_grouping=[("modality", "stage")],
            metrics=[qc_metric, curation_metric],
        )

        # Convert to dict for testing (this is what the actual code works with)
        self.test_qc_structure = qc.model_dump()

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_qc_metric_change_preserves_tags(self, mock_datetime):
        """Test that QC metric changes preserve tags"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)
        metric = qc_copy["metrics"][0]

        # Store original tags
        original_tags = copy.deepcopy(metric["tags"])

        # Apply a value change
        apply_qc_metric_change(metric, 0.95)

        # Verify tags are unchanged
        self.assertEqual(metric["tags"], original_tags)
        self.assertEqual(metric["value"], 0.95)

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_curation_metric_change_preserves_tags(self, mock_datetime):
        """Test that curation metric changes preserve tags"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)
        metric = qc_copy["metrics"][1]

        # Store original tags
        original_tags = copy.deepcopy(metric["tags"])

        # Apply a curation change
        new_curation = {"unit_id": 2, "label": "bad"}
        apply_curation_metric_change(metric, new_curation, "curator2")

        # Verify tags are unchanged
        self.assertEqual(metric["tags"], original_tags)
        self.assertEqual(len(metric["value"]), 2)

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_status_change_preserves_tags(self, mock_datetime):
        """Test that status changes preserve tags"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)
        metric = qc_copy["metrics"][0]

        # Store original tags
        original_tags = copy.deepcopy(metric["tags"])

        # Apply a status change
        apply_status_change(metric, "Pass", "evaluator1")

        # Verify tags are unchanged
        self.assertEqual(metric["tags"], original_tags)
        self.assertEqual(len(metric["status_history"]), 2)

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_modified_qc_validates_with_schema(self, mock_datetime):
        """Test that modified QC structure validates against schema"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)

        # Apply changes to both metrics
        apply_qc_metric_change(qc_copy["metrics"][0], 0.95)
        apply_status_change(qc_copy["metrics"][0], "Pass", "evaluator1")

        new_curation = {"unit_id": 2, "label": "bad"}
        apply_curation_metric_change(qc_copy["metrics"][1], new_curation, "curator2")
        apply_status_change(qc_copy["metrics"][1], "Pass", "curator2")

        QualityControl.model_validate(qc_copy)

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_default_grouping_unchanged_after_modifications(self, mock_datetime):
        """Test that default_grouping field is not modified by metric changes"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)
        original_grouping = copy.deepcopy(qc_copy["default_grouping"])

        # Apply multiple changes
        apply_qc_metric_change(qc_copy["metrics"][0], 0.95)
        apply_status_change(qc_copy["metrics"][0], "Pass", "evaluator1")

        new_curation = {"unit_id": 2, "label": "bad"}
        apply_curation_metric_change(qc_copy["metrics"][1], new_curation, "curator2")

        # Verify default_grouping is unchanged
        self.assertEqual(qc_copy["default_grouping"], original_grouping)

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_multiple_sequential_changes_preserve_structure(self, mock_datetime):
        """Test that multiple sequential changes don't corrupt the structure"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)
        curation_metric = qc_copy["metrics"][1]

        original_tags = copy.deepcopy(curation_metric["tags"])
        original_object_type = curation_metric["object_type"]

        # Apply multiple curation changes
        for i in range(3):
            new_curation = {"unit_id": i + 2, "label": "good" if i % 2 == 0 else "bad"}
            apply_curation_metric_change(curation_metric, new_curation, f"curator{i}")

        # Verify structure integrity
        self.assertEqual(len(curation_metric["value"]), 4)  # 1 original + 3 new
        self.assertEqual(len(curation_metric["curation_history"]), 4)
        self.assertEqual(curation_metric["tags"], original_tags)
        self.assertEqual(curation_metric["object_type"], original_object_type)

        QualityControl.model_validate(qc_copy)

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_tags_with_special_characters_preserved(self, mock_datetime):
        """Test that tags with special characters are preserved correctly"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)
        metric = qc_copy["metrics"][0]

        # Add tags with special characters
        metric["tags"] = {
            "probe_name": "probeA-001",
            "session_id": "sess_2026.01.27",
            "notes": "test with spaces & symbols!",
        }
        original_tags = copy.deepcopy(metric["tags"])

        # Apply changes
        apply_qc_metric_change(metric, 0.85)
        apply_status_change(metric, "Fail", "evaluator1")

        # Verify tags are unchanged
        self.assertEqual(metric["tags"], original_tags)

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_empty_tags_preserved(self, mock_datetime):
        """Test that empty tags dict is preserved"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)
        metric = qc_copy["metrics"][0]
        metric["tags"] = {}

        # Apply changes
        apply_qc_metric_change(metric, 0.75)

        # Verify tags remain as empty dict
        self.assertEqual(metric["tags"], {})

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_modality_and_stage_preserved(self, mock_datetime):
        """Test that modality and stage fields are not modified"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)
        metric = qc_copy["metrics"][0]

        original_modality = copy.deepcopy(metric["modality"])
        original_stage = metric["stage"]

        # Apply changes
        apply_qc_metric_change(metric, 0.95)
        apply_status_change(metric, "Pass", "evaluator1")

        # Verify modality and stage unchanged
        self.assertEqual(metric["modality"], original_modality)
        self.assertEqual(metric["stage"], original_stage)

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_curation_type_field_preserved(self, mock_datetime):
        """Test that the 'type' field in curation metrics is preserved"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)
        metric = qc_copy["metrics"][1]

        original_type = metric.get("type")

        # Apply curation change
        new_curation = {"unit_id": 2, "label": "bad"}
        apply_curation_metric_change(metric, new_curation, "curator2")

        # Verify type field unchanged
        self.assertEqual(metric.get("type"), original_type)

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_validation_roundtrip_preserves_tags(self, mock_datetime):
        """Test that validating through QualityControl and back preserves tags as dicts"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        qc_copy = copy.deepcopy(self.test_qc_structure)
        original_tags = copy.deepcopy(qc_copy["metrics"][0]["tags"])
        original_grouping = copy.deepcopy(qc_copy["default_grouping"])

        # Apply changes
        apply_qc_metric_change(qc_copy["metrics"][0], 0.95)
        apply_status_change(qc_copy["metrics"][0], "Pass", "evaluator1")

        # Validate (this is what happens in submit_changes_to_docdb)
        validated_qc = QualityControl.model_validate(qc_copy)

        # Convert back to dict (simulating what would go to DocDB)
        qc_dict = validated_qc.model_dump()

        # Check that tags are still dicts, not lists
        self.assertIsInstance(
            qc_dict["metrics"][0]["tags"], dict, f"Tags became {type(qc_dict['metrics'][0]['tags'])} instead of dict"
        )
        self.assertEqual(qc_dict["metrics"][0]["tags"], original_tags)

        # Check that default_grouping didn't trigger the validator
        self.assertEqual(qc_dict["default_grouping"], original_grouping, "default_grouping was modified by validator")

    @patch("aind_qc_portal.view_contents.data_utils.datetime")
    def test_exact_production_structure_preserved(self, mock_datetime):
        """Test exact production structure: tags as dict, default_grouping as list of strings"""
        mock_datetime.now.return_value.isoformat.return_value = "2026-01-27T12:00:00"

        # Create structure with production format: list of strings for default_grouping
        qc_metric = QCMetric(
            name="drift_metric",
            modality=Modality.ECEPHYS,
            stage=Stage.RAW,
            value=0.5,
            status_history=[
                QCStatus(status=Status.PENDING, evaluator="system", timestamp=datetime(2026, 1, 26, 10, 0, 0))
            ],
            tags={"probe": "experiment1_ProbeA_group0"},  # Dict with string key-value
            description="Drift measurement",
        )

        qc_obj = QualityControl(
            default_grouping=["probe", "stage"],  # List of strings is valid
            metrics=[qc_metric],
        )

        # Convert to dict to work with our helper functions
        qc_structure = qc_obj.model_dump()

        # Store original values
        original_tags = copy.deepcopy(qc_structure["metrics"][0]["tags"])
        original_grouping = copy.deepcopy(qc_structure["default_grouping"])

        # Verify original structure - default_grouping can be list of strings
        self.assertIsInstance(original_tags, dict)
        self.assertIsInstance(original_grouping, list)
        self.assertEqual(original_grouping, ["probe", "stage"])

        # Apply changes to the dict
        apply_qc_metric_change(qc_structure["metrics"][0], 0.95)
        apply_status_change(qc_structure["metrics"][0], "Pass", "evaluator1")

        # Validate through QualityControl
        validated_qc = QualityControl.model_validate(qc_structure)
        qc_dict = validated_qc.model_dump()

        # Verify tags remained as dict
        self.assertIsInstance(qc_dict["metrics"][0]["tags"], dict, "Tags should remain as dict")
        self.assertEqual(qc_dict["metrics"][0]["tags"], original_tags, "Tags content should be unchanged")

        # Verify default_grouping is unchanged (should stay as strings)
        self.assertEqual(qc_dict["default_grouping"], original_grouping, "default_grouping should not be modified")
        self.assertEqual(
            qc_dict["default_grouping"], ["probe", "stage"], "default_grouping should remain as list of strings"
        )
        self.assertNotEqual(
            qc_dict["default_grouping"], [["modality"], ["tag_1"]], "default_grouping should NOT trigger validator fix"
        )


if __name__ == "__main__":
    unittest.main()
