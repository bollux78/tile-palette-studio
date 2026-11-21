import math
import unittest
from PIL import Image,ImageDraw
import numpy as np
from image_prepare import resize_image
from sms_quantizer import quantize,Settings,hardware_data
from sms_rom import build_test_rom


class AspectTests(unittest.TestCase):
    def test_circle_stays_round_on_target_display(self):
        im=Image.new('RGBA',(200,200),'white')
        ImageDraw.Draw(im).ellipse((40,40,159,159),fill='red')
        for width,height,par in [(256,192,1.25),(256,224,1.25),(320,224,1),(320,224,14/15),(256,192,1)]:
            for fit in ['contain','cover']:
                with self.subTest(size=(width,height),par=par,fit=fit):
                    out=resize_image(im,width,height,Image.Resampling.NEAREST,pixel_aspect=par,fit=fit)
                    a=np.asarray(out);ys,xs=np.where((a[:,:,0]>200)&(a[:,:,1]<30))
                    display_w=(xs.max()-xs.min()+1)*par
                    display_h=ys.max()-ys.min()+1
                    self.assertLess(abs(display_w/display_h-1),.025)
                    self.assertEqual(out.size,(width,height))

    def test_full_image_vs_cover_and_no_internal_bands(self):
        im=Image.new('RGBA',(400,300),'white')
        contain=resize_image(im,256,192,Image.Resampling.NEAREST,pixel_aspect=1.25)
        cover=resize_image(im,256,192,Image.Resampling.NEAREST,pixel_aspect=1.25,fit='cover')
        self.assertEqual(contain.getpixel((0,100)),(0,0,0,255))
        self.assertTrue(np.all(np.asarray(cover)==255))
        # Source aspect is preserved AFTER the 1.25 display stretch.
        a=np.asarray(contain);ys,xs=np.where(a[:,:,0]>200)
        self.assertAlmostEqual((xs.max()-xs.min()+1)*1.25/(ys.max()-ys.min()+1),4/3,delta=.01)

    def test_letterbox_alpha_and_background(self):
        im=Image.new('RGBA',(100,100),(255,0,0,128))
        transparent=resize_image(im,256,192,Image.Resampling.NEAREST,pixel_aspect=1.25,preserve_alpha=True)
        self.assertEqual(transparent.getpixel((0,0))[3],0)
        self.assertEqual(transparent.getpixel((128,96))[3],128)
        opaque=resize_image(im,256,192,Image.Resampling.NEAREST,background='#123456')
        self.assertEqual(opaque.getpixel((0,0)),(18,52,86,255))
        self.assertEqual(opaque.getpixel((128,96))[3],255)

    def test_square_pixel_default_compatibility_and_validation(self):
        im=Image.new('RGBA',(320,224),'red')
        out=resize_image(im,320,224,Image.Resampling.NEAREST)
        self.assertEqual(out.tobytes(),im.tobytes())
        for par in [0,float('nan'),float('inf'),5]:
            with self.assertRaises(ValueError):resize_image(im,320,224,Image.Resampling.NEAREST,pixel_aspect=par)
        with self.assertRaises(ValueError):resize_image(im,320,224,Image.Resampling.NEAREST,fit='invalid')

    def test_sms_black_border_is_fitted_without_recoloring_pixels(self):
        from test_sms import render_hardware
        rng=np.random.default_rng(21)
        im=Image.fromarray(rng.integers(0,256,(16,16,3),dtype=np.uint8))
        for alpha in [False,True]:
            r=quantize(im,Settings(rom_border='#000000',transparent=alpha,background='#ffffff',iterations=2))
            np.testing.assert_array_equal(r.palettes_rgb[1,15],[0,0,0])
            if alpha:np.testing.assert_array_equal(r.palettes_rgb[:,0],[[255,255,255]]*2)
            tiles,attrs,cram,_=hardware_data(r)
            self.assertEqual(cram[31],0)
            np.testing.assert_array_equal(render_hardware(tiles,attrs,cram,16,16),np.asarray(r.preview)[:,:,:3])

    def test_static_sms_border_register_uses_reserved_black(self):
        r=quantize(Image.new('RGB',(256,192),'white'),Settings(rom_border='#000000',iterations=1))
        rom,_=build_test_rom(r)
        self.assertIn(bytes([0x3e,15,0xd3,0xbf,0x3e,0x87,0xd3,0xbf]),rom)

    def test_scroll_sms_border_register_and_cram(self):
        from test_sms_scroll import fixture
        from sms_scroll_rom import build_scroll_rom
        try:from sms_emulator import SMSMachine
        except ImportError:self.skipTest('Install z80')
        r=fixture(384,256);r.settings.rom_border='#000000'
        rom,_=build_scroll_rom(r)
        m=SMSMachine(rom)
        self.assertEqual(m.regs[7],15)
        self.assertEqual(m.cram[16+m.regs[7]],0)
        np.testing.assert_array_equal(m.render(),np.asarray(r.preview)[:192,:248,:3])
