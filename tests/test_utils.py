"""Unit tests for utils.py"""

import unittest
from unittest.mock import patch

from aind_data_schema.core.quality_control import Status

from aind_qc_portal.utils import (
    _qc_status_color,
    df_scalar_to_list,
    format_css_background,
    format_link,
    get_user_name,
    qc_status_color,
    qc_status_color_css,
    qc_status_html,
    qc_status_link_html,
    raw_name_from_derived,
    replace_markdown_with_html,
)


class TestRawNameFromDerived(unittest.TestCase):
    """Tests for raw_name_from_derived function"""

    def test_newer_pattern(self):
        """Test newer derived asset name pattern without platform"""
        result = raw_name_from_derived("subj_20231201_120000_proc_20231202_130000")
        self.assertEqual(result, "subj_20231201_120000")

    def test_older_pattern(self):
        """Test older derived asset name pattern with platform"""
        result = raw_name_from_derived("plat_subj_20231201_120000_proc_20231202_130000")
        self.assertEqual(result, "plat_subj_20231201_120000")

    def test_empty_string(self):
        """Test empty derived asset name"""
        with self.assertRaises(ValueError):
            raw_name_from_derived("")

    def test_invalid_format(self):
        """Test derived asset name with invalid format"""
        with self.assertRaises(ValueError):
            raw_name_from_derived("invalid_format")


class TestFormatLink(unittest.TestCase):
    """Tests for format_link function"""

    def test_default_text(self):
        """Test link formatting with default text"""
        result = format_link("http://example.com")
        self.assertEqual(result, '<a href="http://example.com" target="_blank">link</a>')

    def test_custom_text(self):
        """Test link formatting with custom text"""
        result = format_link("http://example.com", "click here")
        self.assertEqual(result, '<a href="http://example.com" target="_blank">click here</a>')


class TestGetUserName(unittest.TestCase):
    """Tests for get_user_name function"""

    @patch('aind_qc_portal.utils.pn.state')
    def test_with_user(self, mock_state):
        """Test when a user is logged in"""
        mock_state.user = "testuser"
        result = get_user_name()
        self.assertEqual(result, "testuser")

    @patch('aind_qc_portal.utils.pn.state')
    def test_guest(self, mock_state):
        """Test when no user is logged in (guest)"""
        mock_state.user = None
        result = get_user_name()
        self.assertEqual(result, "guest")


class TestFormatCssBackground(unittest.TestCase):
    """Tests for format_css_background function"""

    @patch('aind_qc_portal.utils.pn.state')
    @patch('aind_qc_portal.utils.pn.config')
    def test_default_background(self, mock_config, mock_state):
        """Test default background color when no query param is set"""
        mock_state.location.query_params = {}
        mock_config.raw_css = []
        format_css_background()
        self.assertEqual(len(mock_config.raw_css), 1)
        self.assertIn("#003057", mock_config.raw_css[0])

    @patch('aind_qc_portal.utils.pn.state')
    @patch('aind_qc_portal.utils.pn.config')
    def test_custom_background(self, mock_config, mock_state):
        """Test custom background color from query param"""
        mock_state.location.query_params = {"background": "green"}
        mock_config.raw_css = []
        format_css_background()
        self.assertEqual(len(mock_config.raw_css), 1)
        self.assertIn("#1D8649", mock_config.raw_css[0])


class TestQcStatusColorHelper(unittest.TestCase):
    """Tests for _qc_status_color helper function"""

    def test_no_qc(self):
        """Test No QC status color"""
        result = _qc_status_color("No QC")
        self.assertEqual(result, "#FFB71B")

    def test_unknown_status(self):
        """Test unknown status color"""
        result = _qc_status_color("Unknown")
        self.assertEqual(result, "#7C7C7F")


class TestQcStatusColor(unittest.TestCase):
    """Tests for qc_status_color function"""

    def test_pass_status(self):
        """Test Pass status color"""
        result = qc_status_color(Status.PASS)
        self.assertEqual(result, "#1D8649")

    def test_fail_status(self):
        """Test Fail status color"""
        result = qc_status_color(Status.FAIL)
        self.assertEqual(result, "#FF5733")

    def test_pending_status(self):
        """Test Pending status color"""
        result = qc_status_color(Status.PENDING)
        self.assertEqual(result, "#2A7DE1")


class TestQcStatusColorCss(unittest.TestCase):
    """Tests for qc_status_color_css function"""

    def test_pass_status(self):
        """Test Pass status CSS"""
        result = qc_status_color_css("Pass")
        self.assertEqual(result, "background-color: #1D8649; color: white;")

    def test_fail_status(self):
        """Test Fail status CSS"""
        result = qc_status_color_css("Fail")
        self.assertEqual(result, "background-color: #FF5733; color: white;")


class TestQcStatusHtml(unittest.TestCase):
    """Tests for qc_status_html function"""

    def test_status_enum(self):
        """Test with Status enum"""
        result = qc_status_html(Status.PASS)
        self.assertEqual(result, '<span style="color:#1D8649;">Pass</span>')

    def test_status_string(self):
        """Test with status string"""
        result = qc_status_html("Pass")
        self.assertEqual(result, '<span style="color:#1D8649;">Pass</span>')

    def test_custom_text(self):
        """Test with custom text"""
        result = qc_status_html(Status.PASS, "Success")
        self.assertEqual(result, '<span style="color:#1D8649;">Success</span>')

    def test_empty_text_uses_status(self):
        """Test that empty text uses status value"""
        result = qc_status_html("Fail", "")
        self.assertEqual(result, '<span style="color:#FF5733;">Fail</span>')


class TestQcStatusLinkHtml(unittest.TestCase):
    """Tests for qc_status_link_html function"""

    def test_basic(self):
        """Test basic QC status link HTML"""
        result = qc_status_link_html("Pass", "http://example.com", "view")
        self.assertEqual(
            result,
            '<span style="background-color:#1D8649;"><a href="http://example.com" target="_blank">view</a></span>',
        )


class TestReplaceMarkdownWithHtml(unittest.TestCase):
    """Tests for replace_markdown_with_html function"""

    def test_single_link(self):
        """Test replacing a single markdown link"""
        result = replace_markdown_with_html(12, "[text](http://example.com)")
        self.assertEqual(
            result,
            '<span style="font-size:12pt"><a href="http://example.com" target="_blank">text</a></span>',
        )

    def test_multiple_links(self):
        """Test replacing multiple markdown links"""
        result = replace_markdown_with_html(14, "[first](http://one.com) and [second](http://two.com)")
        self.assertIn('<a href="http://one.com" target="_blank">first</a>', result)
        self.assertIn('<a href="http://two.com" target="_blank">second</a>', result)
        self.assertIn('font-size:14pt', result)

    def test_no_links(self):
        """Test string with no markdown links"""
        result = replace_markdown_with_html(12, "plain text")
        self.assertEqual(result, '<span style="font-size:12pt">plain text</span>')


class TestDfScalarToList(unittest.TestCase):
    """Tests for df_scalar_to_list function"""

    def test_scalars(self):
        """Test converting scalars to lists"""
        result = df_scalar_to_list({"a": 1, "b": "text"})
        self.assertEqual(result, {"a": [1], "b": ["text"]})

    def test_existing_list(self):
        """Test that existing lists remain unchanged"""
        result = df_scalar_to_list({"a": [1, 2], "b": "text"})
        self.assertEqual(result, {"a": [1, 2], "b": ["text"]})

    def test_empty_dict(self):
        """Test empty dictionary"""
        result = df_scalar_to_list({})
        self.assertEqual(result, {})


if __name__ == "__main__":
    """Run the unit tests"""
    unittest.main()
