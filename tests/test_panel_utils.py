""" Tests for panel_utils.py """

import unittest
from aind_qc_portal.panel.panel_utils import reference_is_image, reference_is_video, reference_is_pdf


class TestPanelUtils(unittest.TestCase):
    """Test class for panel_utils.py"""

    def test_is_image(self):
        """Test reference_is_image function"""
        # Test valid image extensions
        self.assertTrue(reference_is_image("test.png"))
        self.assertTrue(reference_is_image("test.jpg"))
        self.assertTrue(reference_is_image("test.gif"))
        self.assertTrue(reference_is_image("test.jpeg"))
        self.assertTrue(reference_is_image("test.svg"))
        self.assertTrue(reference_is_image("test.tiff"))
        self.assertTrue(reference_is_image("test.webp"))

        # Test invalid image extensions
        self.assertFalse(reference_is_image("test.txt"))
        self.assertFalse(reference_is_image("test.png.txt"))
        self.assertFalse(reference_is_image("test"))
        self.assertFalse(reference_is_image(""))

    def test_is_video(self):
        """Test reference_is_video function"""
        # Test valid video extensions
        self.assertTrue(reference_is_video("test.mp4"))
        self.assertTrue(reference_is_video("test.avi"))
        self.assertTrue(reference_is_video("test.webm"))

        # Test invalid video extensions
        self.assertFalse(reference_is_video("test.txt"))
        self.assertFalse(reference_is_video("test.mp4.txt"))
        self.assertFalse(reference_is_video(""))
        self.assertFalse(reference_is_video("test"))

    def test_is_pdf(self):
        """Test reference_is_pdf function"""
        # Test valid PDF extension
        self.assertTrue(reference_is_pdf("test.pdf"))

        # Test invalid PDF extensions
        self.assertFalse(reference_is_pdf("test.txt"))
        self.assertFalse(reference_is_pdf("test.pdf.txt"))
        self.assertFalse(reference_is_pdf(""))
        self.assertFalse(reference_is_pdf("test"))
