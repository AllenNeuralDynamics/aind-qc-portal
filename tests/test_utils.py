import unittest
from datetime import datetime
from unittest.mock import patch
import pandas as pd
import numpy as np
from aind_data_schema.core.quality_control import Status

from aind_qc_portal.utils import (
    format_link,
    format_css_background,
    qc_status_html,
    df_timestamp_range,
    replace_markdown_with_html,
    qc_status_color_css,
    bincount2D,
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
        self.assertEqual(
            qc_status_color_css("No QC"), "background-color: #FFB71B"
        )
        self.assertEqual(
            qc_status_color_css("Pass"), "background-color: #1D8649"
        )
        self.assertEqual(
            qc_status_color_css("Fail"), "background-color: #FF5733"
        )
        self.assertEqual(
            qc_status_color_css("Pending"), "background-color: #2A7DE1"
        )

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
        mock_pn.state.location.query_params = (
            {}
        )  # Mock query_params to ensure no background param
        format_css_background()
        self.assertIn(
            "background-color: #003057", mock_pn.config.raw_css[0]
        )  # Default dark_blue color

        mock_pn.config.raw_css = []  # Reset mock raw_css
        mock_pn.state.location.query_params = {
            "background": "light_blue"
        }  # Mock query_params with light_blue
        format_css_background()
        self.assertIn(
            "background-color: #2A7DE1", mock_pn.config.raw_css[0]
        )  # light_blue color


if __name__ == "__main__":
    unittest.main()
