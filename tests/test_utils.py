import unittest
from datetime import datetime
from unittest.mock import patch
import pandas as pd
import numpy as np
from aind_data_schema.core.quality_control import Status

from aind_qc_portal.utils import (
    AIND_COLORS,
    FIVE_YEARS,
    ONE_MONTH,
    ONE_WEEK,
    ONE_YEAR,
    _get_scale_and_indices,
    format_link,
    format_css_background,
    qc_status_color,
    qc_status_html,
    df_timestamp_range,
    range_unit_format,
    replace_markdown_with_html,
    qc_status_color_css,
    bincount2D,
    get_user_name,
    timestamp_range,
)


class TestUtils(unittest.TestCase):

    def test_format_link(self):
        self.assertEqual(
            format_link("http://example.com"),
            '<a href="http://example.com" target="_blank">link</a>',
        )
        self.assertEqual(
            format_link("http://example.com", "Example"),
            '<a href="http://example.com" target="_blank">Example</a>',
        )

    def test_status_html(self):
        self.assertEqual(
            qc_status_html(Status.PASS),
            '<span style="color:#1D8649;">Pass</span>',
        )
        self.assertEqual(
            qc_status_html(Status.PENDING),
            '<span style="color:#2A7DE1;">Pending</span>',
        )
        self.assertEqual(
            qc_status_html(Status.FAIL),
            '<span style="color:#FF5733;">Fail</span>',
        )

    def test_df_timestamp_range(self):
        data = {
            "timestamp": [
                datetime(2023, 1, 1),
                datetime(2023, 1, 2),
                datetime(2023, 1, 3),
            ]
        }
        df = pd.DataFrame(data)
        min_range, max_range, unit, fmt = df_timestamp_range(df)
        self.assertEqual(unit, "day")
        self.assertEqual(fmt, "%b %d")

    def test_md_style(self):
        self.assertEqual(
            replace_markdown_with_html(12, "test"),
            '<span style="font-size:12pt">test</span>',
        )

    def test_qc_color(self):
        self.assertEqual(qc_status_color(Status.PASS), AIND_COLORS["green"])

        self.assertEqual(qc_status_color_css("No QC"), "background-color: #FFB71B")
        self.assertEqual(qc_status_color_css("Pass"), "background-color: #1D8649")
        self.assertEqual(qc_status_color_css("Fail"), "background-color: #FF5733")
        self.assertEqual(qc_status_color_css("Pending"), "background-color: #2A7DE1")
        self.assertEqual(qc_status_color_css("Other"), "background-color: #7C7C7F")

    def test_bincount2D(self):
        x = np.array([1, 2, 2, 3])
        y = np.array([4, 5, 5, 6])
        r, xscale, yscale = bincount2D(x, y)
        self.assertEqual(r.shape, (3, 3))
        self.assertTrue(np.array_equal(xscale, np.array([1, 2, 3])))
        self.assertTrue(np.array_equal(yscale, np.array([4, 5, 6])))

    @patch("aind_qc_portal.utils.pn")
    def test_set_background(self, mock_pn):
        mock_pn.config.raw_css = []  # Mock raw_css to ensure a clean state
        mock_pn.state.location.query_params = {}  # Mock query_params to ensure no background param
        format_css_background()
        self.assertIn("background-color: #003057", mock_pn.config.raw_css[0])  # Default dark_blue color

        mock_pn.config.raw_css = []  # Reset mock raw_css
        mock_pn.state.location.query_params = {"background": "light_blue"}  # Mock query_params with light_blue
        format_css_background()
        self.assertIn("background-color: #2A7DE1", mock_pn.config.raw_css[0])  # light_blue color

    def test_qc_status_link_html(self):
        """Test the qc_status_link_html function"""
        from aind_qc_portal.utils import qc_status_link_html

        result = qc_status_link_html("Pass", "http://example.com", "Example")
        expected = (
            '<span style="background-color:#1D8649;"><a href="http://example.com" target="_blank">Example</a></span>'
        )
        self.assertEqual(result, expected)

    def test_range_unit_format(self):
        """Test the range_unit_format function for different time ranges"""

        # Test different time ranges
        test_cases = [
            (ONE_WEEK / 2, ("day", "%b %d")),  # Less than a week
            (ONE_MONTH / 2, ("week", "%b %d")),  # Less than a month
            (ONE_MONTH * 2, ("week", "%b %d")),  # Less than 3 months
            (ONE_YEAR / 2, ("month", "%b")),  # Less than a year
            (ONE_YEAR * 1.5, ("year", "%b")),  # Less than 2 years
            (ONE_YEAR * 3, ("year", "%Y")),  # Less than 5 years
            (ONE_YEAR * 7, ("year", "%Y")),  # More than 5 years
            (FIVE_YEARS * 3, ("year", "%Y")),  # More than 10 years
        ]

        for time_range, expected in test_cases:
            unit, format = range_unit_format(time_range)
            self.assertEqual((unit, format), expected)

    def test_timestamp_range(self):
        """Test the timestamp_range function"""

        test_cases = [
            (datetime(2023, 1, 1), datetime(2023, 1, 3), "day", "%b %d"),
            (datetime(2023, 1, 1), datetime(2023, 1, 15), "week", "%b %d"),
            (datetime(2023, 1, 1), datetime(2023, 2, 15), "week", "%b %d"),
            (datetime(2023, 1, 1), datetime(2023, 6, 1), "month", "%b"),
            (datetime(2023, 1, 1), datetime(2024, 1, 1), "year", "%b"),
            (datetime(2023, 1, 1), datetime(2026, 1, 1), "year", "%Y"),
            (datetime(2023, 1, 1), datetime(2030, 1, 1), "year", "%Y"),
            (datetime(2023, 1, 1), datetime(2050, 1, 1), "year", "%Y"),
        ]

        for min_date, max_date, _, _ in test_cases:
            min_range, max_range, _, _ = timestamp_range(min_date, max_date)
            self.assertTrue(min_range < min_date)  # Should pad before start
            self.assertTrue(max_range > max_date)  # Should pad after end

    def test_qc_status_html_with_custom_text(self):
        """Test qc_status_html with custom display text"""
        result = qc_status_html(Status.PASS, "Custom Text")
        self.assertEqual(result, '<span style="color:#1D8649;">Custom Text</span>')

    def test_replace_markdown_with_html_with_links(self):
        """Test replace_markdown_with_html with actual markdown links"""
        markdown = "Check out [this link](http://example.com) and [another](http://test.com)"
        expected = '<span style="font-size:12pt">Check out <a href="http://example.com" target="_blank">this link</a> and <a href="http://test.com" target="_blank">another</a></span>'  # noqa
        result = replace_markdown_with_html(12, markdown)
        self.assertEqual(result, expected)

    def test_bincount2D_with_weights(self):
        """Test bincount2D with weights and different bin parameters"""
        x = np.array([1, 2, 2, 3])
        y = np.array([4, 5, 5, 6])
        weights = np.array([1, 2, 2, 3])

        # Test with weights
        r, xscale, yscale = bincount2D(x, y, weights=weights)
        self.assertEqual(r.shape, (3, 3))
        self.assertEqual(r[1, 1], 4)  # Sum of weights for x=2, y=5

        # Test with specific bin values
        xbin = np.array([1, 2, 3, 4])
        ybin = np.array([4, 5, 6, 7])
        r, xscale, yscale = bincount2D(x, y, xbin=xbin, ybin=ybin)
        self.assertEqual(r.shape, (4, 4))
        self.assertTrue(np.array_equal(xscale, xbin))
        self.assertTrue(np.array_equal(yscale, ybin))

    @patch("aind_qc_portal.utils.pn")
    def test_get_user_name(self, mock_pn):
        # Test when pn.state.user is set
        mock_pn.state.user = "test_user"
        self.assertEqual(get_user_name(), "test_user")

        # Test when pn.state.user is not set
        mock_pn.state.user = None
        self.assertEqual(get_user_name(), "guest")

    def test_get_scale_and_indices_with_scalar_bin(self):
        v = np.array([1, 2, 3, 4, 5])
        bin_size = 1
        lim = [1, 5]
        scale, ind = _get_scale_and_indices(v, bin_size, lim)
        expected_scale = np.array([1, 2, 3, 4, 5])
        expected_ind = np.array([0, 1, 2, 3, 4])
        np.testing.assert_array_equal(scale, expected_scale)
        np.testing.assert_array_equal(ind, expected_ind)

    def test_get_scale_and_indices_with_nonzero_scalar_bin(self):
        v = np.array([1, 2, 3, 4, 5])
        bin_size = 2
        lim = [1, 5]
        scale, ind = _get_scale_and_indices(v, bin_size, lim)
        expected_scale = np.array([1, 3, 5])
        expected_ind = np.array([0, 0, 1, 1, 2])
        np.testing.assert_array_equal(scale, expected_scale)
        np.testing.assert_array_equal(ind, expected_ind)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
