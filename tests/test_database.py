"""Test database class."""

import unittest

from aind_qc_portal.docdb.database import get_sessions, get_subjects


class DocDBTest(unittest.TestCase):
    """Test the DocDB calls"""

    # def setUp(self):

    def test_get_subjects(self):
        """Get the subjects list, check that some known subjects are in it"""
        self.assertIn(596930, get_subjects())

    def test_get_sessions(self):
        """Get data from the test subject's sessions"""
        self.assertEqual(1, len(get_sessions(596930)))


if __name__ == "__main__":
    unittest.main()
