import base64
import random
import unittest
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
from sms_quantizer import Settings,Result,quantize
from sms_scroll_rom import build_scroll_rom
try:
    from sms_emulator import SMSMachine
except ImportError:
    SMSMachine=None


def fixture(width,height,dynamic=False,vertical=False,base=0):
    ty,tx=(height+7)//8,(width+7)//8
    rng=np.random.default_rng(8)
    n=480 if vertical else 600 if dynamic else 16
    patterns=rng.integers(0,16,(n,8,8),dtype=np.uint8)
    palette=np.array([[(i%4)*85,((i//4)%4)*85,(i%2)*170] for i in range(16)],np.uint8)[None,:,:]
    ids=np.empty((ty,tx),np.uint16)
    for y in range(ty):
        for x in range(tx):
            ids[y,x]=(y//16)*120+((y%16*tx+x)%120) if vertical else (x//32)*200+((y*32+x%32)%200) if dynamic else (x+y)%16
    indices=patterns[ids].transpose(0,2,1,3).reshape(ty*8,tx*8)
    rgb=palette[0][indices][:height,:width]
    return Result(Image.fromarray(rgb).convert('RGBA'),palette,np.zeros((ty,tx),np.uint8),indices,
                  Settings(palettes=1,base_tile=base),(width,height),(tx*8,ty*8),[],0,0)


class ScrollBuilderTests(unittest.TestCase):
    def test_mapper_header_and_checksum(self):
        rom,info=build_scroll_rom(fixture(512,384))
        self.assertEqual(info['viewport_size'],[248,192])
        self.assertEqual(info['scroll_range_pixels'],[264,192])
        self.assertEqual(rom[0x7ff0:0x7ff8],b'TMR SEGA')
        self.assertEqual(int.from_bytes(rom[0x7ffa:0x7ffc],'little'),(sum(rom[:0x7ff0])+sum(rom[0x8000:]))&65535)
        loader=base64.b64decode(Path(__file__).resolve().parents[1].joinpath('sms_scroll_loader.b64').read_text())
        self.assertEqual(rom[:len(loader)],loader)

    def test_more_than_448_total_patterns(self):
        _,info=build_scroll_rom(fixture(768,224,dynamic=True))
        self.assertEqual(info['unique_tiles'],600)
        self.assertEqual(info['peak_cache_tiles'],400)
        self.assertFalse(info['resident_atlas'])

    def test_local_vram_limit_rejects_detailed_window(self):
        r=fixture(256,224)
        rng=np.random.default_rng(7)
        r.indices=rng.integers(0,16,r.indices.shape,dtype=np.uint8)
        with self.assertRaisesRegex(ValueError,'região da imagem'):
            build_scroll_rom(r)

    def test_cholirede_with_authorized_lossy_reduction(self):
        im=Image.open(Path(__file__).resolve().parents[1]/'cholirede.png').convert('RGBA')
        im=ImageOps.fit(im,(256,224),Image.Resampling.LANCZOS)
        r=quantize(im,Settings(dither='vertical4',dither_strength=.38,allow_lossy_tiles=True))
        _,info=build_scroll_rom(r)
        self.assertLessEqual(info['peak_cache_tiles'],448)
        self.assertGreater(info['lossy_merges'],0)

    def test_size_limits_and_malformed_data(self):
        for size in [(256,192),(248,224),(256,184)]:
            with self.subTest(size=size):
                with self.assertRaises(ValueError):build_scroll_rom(fixture(*size))
        r=fixture(256,224);r.source_size=(1025,224)
        with self.assertRaises(ValueError):build_scroll_rom(r)
        r=fixture(768,384)
        with self.assertRaises(ValueError):build_scroll_rom(r)
        r=fixture(256,224);r.indices[0,0]=16
        with self.assertRaises(ValueError):build_scroll_rom(r)


@unittest.skipIf(SMSMachine is None,'Install z80 to run actual Z80 ROM tests')
class ScrollZ80Tests(unittest.TestCase):
    def exercise(self,r,paths,check_midwrites=False):
        rom,info=build_scroll_rom(r)
        m=SMSMachine(rom)
        reference=np.asarray(r.preview)[:,:,:3]
        if check_midwrites:m.reference=reference
        def check():
            x,y=m.camera
            np.testing.assert_array_equal(m.render(),reference[y:y+192,x:x+248])
        check()
        for keys,count in paths:
            for _ in range(count):
                m.frame(keys);check()
        return m,info

    def test_resident_atlas_ring_wrap_and_diagonals(self):
        r=fixture(768,336,base=7)
        paths=[(8,270),(2,80),(4,270),(1,80),(10,270),(5,270)]
        m,_=self.exercise(r,paths)
        self.assertEqual(m.camera,(0,0))

    def test_dynamic_horizontal_streaming_and_offscreen_uploads(self):
        r=fixture(768,224,dynamic=True)
        paths=[(8,265),(2,20),(4,265),(1,20),(10,265),(5,265)]
        m,info=self.exercise(r,paths,True)
        self.assertGreater(m.midwrite_checks,50)
        self.assertGreater(info['unique_tiles'],448)
        self.assertEqual(m.camera,(0,0))

    def test_dynamic_vertical_streaming_wraps_at_row_28(self):
        r=fixture(384,512,vertical=True,base=5)
        m,info=self.exercise(r,[(2,165),(8,70),(1,165),(4,70),(10,165),(5,165)],True)
        self.assertFalse(info['resident_atlas'])
        self.assertEqual(m.camera,(0,0))

    def test_odd_dimensions_bounds_and_direction_reversal(self):
        r=fixture(319,257)
        paths=[(10,45),(5,45),(10,45),(5,45)]
        rng=random.Random(42)
        paths.extend((rng.choice([1,2,4,8,5,6,9,10,0]),rng.randrange(1,7)) for _ in range(60))
        m,_=self.exercise(r,paths)
        x,y=m.camera
        self.assertTrue(0<=x<=71 and 0<=y<=65)
