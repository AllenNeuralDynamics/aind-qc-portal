""" Test the database functions in the docdb module """

import unittest
from unittest.mock import patch
from aind_data_schema.core.quality_control import QualityControl

from aind_qc_portal.docdb.database import (
    get_project_names,
    record_from_id,
    project_name_from_id,
    qc_update_to_id,
    get_name_from_id,
    get_subj_from_id,
    _raw_name_from_derived,
    get_assets_by_name,
    get_assets_by_subj,
    get_meta,
    get_all,
    get_project_data,
    get_subjects,
    get_sessions,
)


class TestDatabase(unittest.TestCase):
    """Test the database functions"""

    def setUp(self):
        """Set up the mock client for testing"""
        self.patcher = patch("aind_qc_portal.docdb.database.client")
        self.mock_client = self.patcher.start()

    def tearDown(self):
        """Stop the patcher"""
        self.patcher.stop()

    def test_get_project_names(self):
        """Test the get_project_names function"""
        expected_names = ["project1", "project2"]
        self.mock_client.aggregate_docdb_records.return_value = [{"unique_project_names": expected_names}]
        result = get_project_names()
        self.assertEqual(result, expected_names)

    def test_record_from_id(self):
        """Test the record_from_id function"""
        # Test found record
        mock_record = {"_id": "123", "data": "test"}
        self.mock_client.retrieve_docdb_records.return_value = [mock_record]
        result = record_from_id("123")
        self.assertEqual(result, mock_record)

        # Test not found
        self.mock_client.retrieve_docdb_records.return_value = []
        result = record_from_id("456")
        self.assertIsNone(result)

    def test_project_name_from_id(self):
        """Test the project_name_from_id function"""
        # Test found project
        self.mock_client.retrieve_docdb_records.return_value = [{"data_description": {"project_name": "test_project"}}]
        result = project_name_from_id("123")
        self.assertEqual(result, "test_project")

        # Test not found
        self.mock_client.retrieve_docdb_records.return_value = []
        result = project_name_from_id("456")
        self.assertIsNone(result)

    def test_qc_update_to_id(self):
        """Test the qc_update_to_id function"""
        mock_qc = QualityControl(notes="test note", evaluations=[])
        self.mock_client.upsert_one_docdb_record.return_value = {"status": "success"}
        result = qc_update_to_id("123", mock_qc)
        self.assertEqual(result, {"status": "success"})

    def test_get_name_from_id(self):
        """Test the get_name_from_id function"""
        self.mock_client.aggregate_docdb_records.return_value = [{"name": "test_name"}]
        result = get_name_from_id("123")
        self.assertEqual(result, "test_name")

    def test_get_subj_from_id(self):
        """Test the get_subj_from_id function"""
        # Test found subject
        self.mock_client.retrieve_docdb_records.return_value = [{"subject": {"subject_id": "test_subject"}}]
        result = get_subj_from_id("123")
        self.assertEqual(result, "test_subject")

        # Test not found
        self.mock_client.retrieve_docdb_records.return_value = []

        result = get_subj_from_id("456")
        self.assertIsNone(result)

    def test_raw_name_from_derived(self):
        """Test the _raw_name_from_derived function"""
        # Test derived name
        derived_name = "part1_part2_part3_part4_derived"
        result = _raw_name_from_derived(derived_name)
        self.assertEqual(result, "part1_part2_part3_part4")

        # Test raw name
        raw_name = "part1_part2_part3"
        result = _raw_name_from_derived(raw_name)
        self.assertEqual(result, raw_name)

    def test_get_assets_by_name(self):
        """Test the get_assets_by_name function"""
        mock_assets = [{"name": "asset1"}, {"name": "asset2"}]
        self.mock_client.retrieve_docdb_records.return_value = mock_assets
        result = get_assets_by_name("test_asset")
        self.assertEqual(result, mock_assets)

    def test_get_assets_by_subj(self):
        """Test the get_assets_by_subj function"""
        mock_assets = [
            {"subject": {"subject_id": "123"}},
            {"subject": {"subject_id": "123"}},
        ]
        self.mock_client.retrieve_docdb_records.return_value = mock_assets
        result = get_assets_by_subj("123")
        self.assertEqual(result, mock_assets)

    def test_get_meta(self):
        """Test the get_meta function"""
        mock_meta = [{"_id": "123", "name": "test", "quality_control": {}}]
        self.mock_client.aggregate_docdb_records.return_value = mock_meta
        result = get_meta()
        self.assertEqual(result, mock_meta)

    def test_get_all(self):
        """Test the get_all function"""
        mock_records = [{"_id": "1"}, {"_id": "2"}]
        self.mock_client.retrieve_docdb_records.return_value = mock_records
        result = get_all()
        self.assertEqual(result, mock_records)

    def test_get_project_data(self):
        """Test the get_project_data function"""
        mock_data = [{"_id": "1", "data_description": {"project_name": "test_project"}}]
        self.mock_client.retrieve_docdb_records.return_value = mock_data
        result = get_project_data("test_project")
        self.assertEqual(result, mock_data)

    def test_get_subjects(self):
        """Test the get_subjects function"""
        mock_subjects = [
            {"subject": {"subject_id": "1"}},
            {"subject": {"subject_id": "2"}},
        ]
        self.mock_client.retrieve_docdb_records.return_value = mock_subjects
        result = get_subjects()
        self.assertEqual(result, [1, 2])

    def test_get_sessions(self):
        """Test the get_sessions function"""
        mock_sessions = [{"session": {"id": "1"}}, {"session": {"id": "2"}}]
        self.mock_client.retrieve_docdb_records.return_value = mock_sessions
        result = get_sessions("123")
        self.assertEqual(result, [{"id": "1"}, {"id": "2"}])


if __name__ == "__main__":  # pragma: no cover
    """Run the unittests"""
    unittest.main()
