import copy
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, mock_open, patch

from scripts.replace_qc_tags.clear_smartspim_qc import ASSET_NAMES, clear_qc


class TestClearSmartspimQc(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"name": name, "quality_control": {"metrics": ["original"]}, "other": "kept"}
            for name in ASSET_NAMES
        ]
        self.client = MagicMock()
        self.client.retrieve_docdb_records.side_effect = [
            [record] for record in self.records
        ]
        self.stdout = redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)

    def test_preview_does_not_write(self):
        originals = copy.deepcopy(self.records)
        clear_qc(self.client)
        self.client.upsert_one_docdb_record.assert_not_called()
        self.assertEqual(self.records, originals)
        self.assertEqual(
            self.client.retrieve_docdb_records.call_args_list,
            [unittest.mock.call(filter_query={"name": name}) for name in ASSET_NAMES],
        )

    @patch("scripts.replace_qc_tags.clear_smartspim_qc.Path.open", new_callable=mock_open)
    def test_apply_backs_up_and_clears_only_qc(self, backup_open):
        clear_qc(self.client, apply=True)
        backup_open.assert_called_once_with("x")
        backup_text = "".join(
            call.args[0] for call in backup_open().write.call_args_list
        )
        self.assertIn("original", backup_text)
        self.assertEqual(self.client.upsert_one_docdb_record.call_count, 3)
        for record in self.records:
            self.assertEqual(record["quality_control"], {})
            self.assertEqual(record["other"], "kept")

    def test_missing_record_prevents_all_writes(self):
        self.client.retrieve_docdb_records.side_effect = [[self.records[0]], []]
        with self.assertRaises(RuntimeError):
            clear_qc(self.client, apply=True)
        self.client.upsert_one_docdb_record.assert_not_called()


if __name__ == "__main__":
    unittest.main()