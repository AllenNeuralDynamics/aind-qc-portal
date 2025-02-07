import unittest
from aind_qc_portal.panel.panel_utils import _is_image, _is_video, _is_pdf

class TestPanelUtils(unittest.TestCase):
    def test_is_image(self):
        # Test valid image extensions
        self.assertTrue(_is_image("test.png"))
        self.assertTrue(_is_image("test.jpg"))
        self.assertTrue(_is_image("test.gif"))
        self.assertTrue(_is_image("test.jpeg"))
        self.assertTrue(_is_image("test.svg"))
        self.assertTrue(_is_image("test.tiff"))
        self.assertTrue(_is_image("test.webp"))
        
        # Test invalid image extensions
        self.assertFalse(_is_image("test.txt"))
        self.assertFalse(_is_image("test.png.txt"))
        self.assertFalse(_is_image("test"))
        self.assertFalse(_is_image(""))

    def test_is_video(self):
        # Test valid video extensions
        self.assertTrue(_is_video("test.mp4"))
        self.assertTrue(_is_video("test.avi"))
        self.assertTrue(_is_video("test.webm"))
        
        # Test invalid video extensions
        self.assertFalse(_is_video("test.txt"))
        self.assertFalse(_is_video("test.mp4.txt"))
        self.assertFalse(_is_video(""))
        self.assertFalse(_is_video("test"))

    def test_is_pdf(self):
        # Test valid PDF extension
        self.assertTrue(_is_pdf("test.pdf"))
        
        # Test invalid PDF extensions
        self.assertFalse(_is_pdf("test.txt"))
        self.assertFalse(_is_pdf("test.pdf.txt"))
        self.assertFalse(_is_pdf(""))
        self.assertFalse(_is_pdf("test")) 