import unittest
from PIL import Image
from image_prepare import prepare_image


class PrepareImageTests(unittest.TestCase):
    def test_neutral_preserves_rgba_and_source(self):
        im = Image.new('RGBA', (5, 4), (90, 140, 200, 71))
        self.assertEqual(prepare_image(im, {}).tobytes(), im.tobytes())
        edited = prepare_image(im, {'crop': [1, 1, 4, 3], 'brightness': 2})
        self.assertEqual(edited.size, (3, 2))
        self.assertEqual(edited.getpixel((0, 0)), (180, 255, 255, 71))
        self.assertEqual(im.getpixel((0, 0)), (90, 140, 200, 71))

    def test_invalid_crop_is_rejected(self):
        im = Image.new('RGBA', (4, 4))
        for box in ([0, 0, 5, 4], [-1, 0, 2, 2], [2, 0, 2, 3], [0.5, 0, 2, 3]):
            with self.assertRaises(ValueError):
                prepare_image(im, {'crop': box})

    def test_sharpness_preserves_alpha(self):
        im = Image.new('RGBA', (5, 5), (50, 50, 50, 90))
        im.putpixel((2, 2), (100, 100, 100, 11))
        edited = prepare_image(im, {'sharpness': 3})
        self.assertEqual(edited.getchannel('A').tobytes(), im.getchannel('A').tobytes())
        self.assertGreater(edited.getpixel((2, 2))[0], 100)
