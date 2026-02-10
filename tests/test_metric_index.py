"""Integration tests for index key handling in MetricValue DataFrames"""

import unittest
from unittest.mock import MagicMock

import pandas as pd
import panel as pn

from aind_qc_portal.view_contents.panels.metrics import MetricValue


class TestMetricValueIndexHandling(unittest.TestCase):
    """Tests for index key handling in MetricValue dictionary-to-DataFrame conversion"""

    def setUp(self):
        """Set up common test fixtures"""
        self.mock_callback = MagicMock()
        self.mock_settings = MagicMock()
        self.mock_settings.allow_value_edits = True

    def test_dict_with_list_values_and_index(self):
        """Test dictionary with list values and an 'index' key"""
        value_dict = {
            "index": ["row1", "row2", "row3"],
            "unit_id": [1, 2, 3],
            "firing_rate": [12.5, 8.3, 15.2],
            "label": ["good", "noise", "good"],
        }

        metric = MetricValue(
            name="test_metric",
            description="Test metric",
            tags={},
            stage="test",
            modality="test",
            value=value_dict,
            status="Pass",
            callback=self.mock_callback,
            settings=self.mock_settings,
        )

        # Verify a DataFrame widget was created
        self.assertIsInstance(metric.value_widget, pn.pane.DataFrame)

        # Verify the DataFrame has the correct structure
        df = metric.value_widget.object
        self.assertEqual(len(df), 3)
        self.assertEqual(list(df.columns), ["unit_id", "firing_rate", "label"])

        # Verify the index is set correctly
        self.assertEqual(list(df.index), ["row1", "row2", "row3"])

        # Verify values are correct
        self.assertEqual(list(df["unit_id"]), [1, 2, 3])
        self.assertEqual(list(df["firing_rate"]), [12.5, 8.3, 15.2])
        self.assertEqual(list(df["label"]), ["good", "noise", "good"])

    def test_dict_with_scalar_values_and_index(self):
        """Test dictionary with scalar values and an 'index' key"""
        value_dict = {
            "index": "summary",
            "mean": 12.5,
            "std": 2.3,
            "count": 100,
        }

        metric = MetricValue(
            name="test_metric",
            description="Test metric",
            tags={},
            stage="test",
            modality="test",
            value=value_dict,
            status="Pass",
            callback=self.mock_callback,
            settings=self.mock_settings,
        )

        # Verify a DataFrame widget was created
        self.assertIsInstance(metric.value_widget, pn.pane.DataFrame)

        # Verify the DataFrame has the correct structure
        df = metric.value_widget.object
        self.assertEqual(len(df), 1)
        self.assertEqual(list(df.columns), ["mean", "std", "count"])

        # Verify the index is set correctly (scalar converted to list)
        self.assertEqual(list(df.index), ["summary"])

        # Verify values are correct
        self.assertEqual(df.loc["summary", "mean"], 12.5)
        self.assertEqual(df.loc["summary", "std"], 2.3)
        self.assertEqual(df.loc["summary", "count"], 100)

    def test_dict_with_list_values_no_index(self):
        """Test dictionary with list values but no 'index' key (default behavior)"""
        value_dict = {
            "unit_id": [1, 2, 3],
            "firing_rate": [12.5, 8.3, 15.2],
        }

        metric = MetricValue(
            name="test_metric",
            description="Test metric",
            tags={},
            stage="test",
            modality="test",
            value=value_dict,
            status="Pass",
            callback=self.mock_callback,
            settings=self.mock_settings,
        )

        # Verify a DataFrame widget was created
        self.assertIsInstance(metric.value_widget, pn.pane.DataFrame)

        # Verify the DataFrame has the correct structure
        df = metric.value_widget.object
        self.assertEqual(len(df), 3)
        self.assertEqual(list(df.columns), ["unit_id", "firing_rate"])

        # Verify default integer index is used
        self.assertEqual(list(df.index), [0, 1, 2])

    def test_dict_with_scalar_values_no_index(self):
        """Test dictionary with scalar values but no 'index' key (default behavior)"""
        value_dict = {
            "mean": 12.5,
            "std": 2.3,
        }

        metric = MetricValue(
            name="test_metric",
            description="Test metric",
            tags={},
            stage="test",
            modality="test",
            value=value_dict,
            status="Pass",
            callback=self.mock_callback,
            settings=self.mock_settings,
        )

        # Verify a DataFrame widget was created
        self.assertIsInstance(metric.value_widget, pn.pane.DataFrame)

        # Verify the DataFrame has the correct structure
        df = metric.value_widget.object
        self.assertEqual(len(df), 1)
        self.assertEqual(list(df.columns), ["mean", "std"])

        # Verify default integer index is used
        self.assertEqual(list(df.index), [0])

    def test_dict_with_index_length_mismatch(self):
        """Test dictionary where index length doesn't match data length"""
        value_dict = {
            "index": ["row1", "row2"],  # Only 2 index values
            "unit_id": [1, 2, 3],  # But 3 data values
            "firing_rate": [12.5, 8.3, 15.2],
        }

        metric = MetricValue(
            name="test_metric",
            description="Test metric",
            tags={},
            stage="test",
            modality="test",
            value=value_dict,
            status="Pass",
            callback=self.mock_callback,
            settings=self.mock_settings,
        )

        # Verify a DataFrame widget was created
        self.assertIsInstance(metric.value_widget, pn.pane.DataFrame)

        # When lengths don't match, the default integer index should be used
        df = metric.value_widget.object
        self.assertEqual(list(df.index), [0, 1, 2])

    def test_dict_with_numeric_index(self):
        """Test dictionary with numeric index values"""
        value_dict = {
            "index": [10, 20, 30],
            "value": [100, 200, 300],
        }

        metric = MetricValue(
            name="test_metric",
            description="Test metric",
            tags={},
            stage="test",
            modality="test",
            value=value_dict,
            status="Pass",
            callback=self.mock_callback,
            settings=self.mock_settings,
        )

        # Verify a DataFrame widget was created
        self.assertIsInstance(metric.value_widget, pn.pane.DataFrame)

        # Verify the DataFrame has the correct structure
        df = metric.value_widget.object
        self.assertEqual(len(df), 3)
        self.assertEqual(list(df.columns), ["value"])

        # Verify the numeric index is set correctly
        self.assertEqual(list(df.index), [10, 20, 30])

    def test_dict_with_only_index_key(self):
        """Test dictionary with only an 'index' key and no other data"""
        value_dict = {"index": ["row1", "row2"]}

        metric = MetricValue(
            name="test_metric",
            description="Test metric",
            tags={},
            stage="test",
            modality="test",
            value=value_dict,
            status="Pass",
            callback=self.mock_callback,
            settings=self.mock_settings,
        )

        # With only an index key, the dict should be treated as having no valid data
        # and should fall back to JSONEditor
        self.assertIsInstance(metric.value_widget, pn.widgets.JSONEditor)

    def test_dict_with_uppercase_index(self):
        """Test dictionary with 'INDEX' key (case-insensitive)"""
        value_dict = {
            "INDEX": ["row1", "row2", "row3"],
            "unit_id": [1, 2, 3],
            "firing_rate": [12.5, 8.3, 15.2],
        }

        metric = MetricValue(
            name="test_metric",
            description="Test metric",
            tags={},
            stage="test",
            modality="test",
            value=value_dict,
            status="Pass",
            callback=self.mock_callback,
            settings=self.mock_settings,
        )

        # Verify a DataFrame widget was created
        self.assertIsInstance(metric.value_widget, pn.pane.DataFrame)

        # Verify the DataFrame has the correct structure
        df = metric.value_widget.object
        self.assertEqual(len(df), 3)
        self.assertEqual(list(df.columns), ["unit_id", "firing_rate"])

        # Verify the index is set correctly
        self.assertEqual(list(df.index), ["row1", "row2", "row3"])

    def test_dict_with_title_case_index(self):
        """Test dictionary with 'Index' key (case-insensitive)"""
        value_dict = {
            "Index": ["a", "b"],
            "mean": [12.5, 8.3],
            "std": [2.3, 1.5],
        }

        metric = MetricValue(
            name="test_metric",
            description="Test metric",
            tags={},
            stage="test",
            modality="test",
            value=value_dict,
            status="Pass",
            callback=self.mock_callback,
            settings=self.mock_settings,
        )

        # Verify a DataFrame widget was created
        self.assertIsInstance(metric.value_widget, pn.pane.DataFrame)

        # Verify the DataFrame has the correct structure
        df = metric.value_widget.object
        self.assertEqual(len(df), 2)
        self.assertEqual(list(df.columns), ["mean", "std"])

        # Verify the index is set correctly
        self.assertEqual(list(df.index), ["a", "b"])

    def test_dict_with_mixed_case_index(self):
        """Test dictionary with 'InDeX' key (case-insensitive)"""
        value_dict = {
            "InDeX": "summary",
            "mean": 12.5,
            "count": 100,
        }

        metric = MetricValue(
            name="test_metric",
            description="Test metric",
            tags={},
            stage="test",
            modality="test",
            value=value_dict,
            status="Pass",
            callback=self.mock_callback,
            settings=self.mock_settings,
        )

        # Verify a DataFrame widget was created
        self.assertIsInstance(metric.value_widget, pn.pane.DataFrame)

        # Verify the DataFrame has the correct structure
        df = metric.value_widget.object
        self.assertEqual(len(df), 1)
        self.assertEqual(list(df.columns), ["mean", "count"])

        # Verify the index is set correctly
        self.assertEqual(list(df.index), ["summary"])


if __name__ == "__main__":
    unittest.main()
