import struct
import unittest
from types import SimpleNamespace
import numpy as np

from scroll_rom import build_scroll_rom

class ScrollRomTests(unittest.TestCase):
    def image(self,w=512,h=256):
        ty,tx=(h+7)//8,(w+7)//8
        indices=np.zeros((ty*8,tx*8),dtype=np.uint8)
        palettes=np.zeros((4,16,3),dtype=np.uint8)
        for p in range(4):
            for c in range(1,16):
                palettes[p,c]=[34*((c+p)%8),34*((2*c+p)%8),34*((3*c+p)%8)]
        palette_ids=np.zeros((ty,tx),dtype=np.uint8)
        for y in range(ty):
            for x in range(tx):
                indices[y*8:(y+1)*8,x*8:(x+1)*8] = 1 + (x+2*y)%15
                palette_ids[y,x] = (x//8+y//8)%4
        return SimpleNamespace(
            source_size=(w,h), indices=indices,tile_palettes=palette_ids,
            palettes_rgb=palettes,
            settings=SimpleNamespace(colors=16,palettes=4))
    def test_h40_rom_metadata_tiles_attrs(self):
        obj=self.image()
        blob,info=build_scroll_rom(obj,320)
        self.assertEqual(info['screen_size'],[320,224])
        self.assertEqual(info['scroll_range_pixels'],[192,32])
        self.assertEqual(info['step_pixels'],2)
        self.assertEqual(len(blob),131072)
        self.assertEqual(int.from_bytes(blob[4:8],"big"),0x200)
        tx,ty,sw,sh,gfx,attrs,cram,commands=struct.unpack_from('>HHHHLLLL',blob,0x1d0)
        self.assertEqual((tx,ty,sw,sh),(64,32,40,28))
        self.assertEqual(blob[gfx:gfx+32],bytes([0x11])*32)
        self.assertEqual(blob[gfx+32:gfx+64],bytes([0x22])*32)
        self.assertEqual(attrs, gfx + tx*ty*32)
        self.assertEqual(int.from_bytes(blob[attrs:attrs+2],'big'),0)
        self.assertEqual(int.from_bytes(blob[commands:commands+4],'big'),0x40000003)
    def test_x7_vblank_vector_in_scroll_rom(self):
        for width in (256,320):
            blob,_=build_scroll_rom(self.image(512,256),width)
            vector=int.from_bytes(blob[0x78:0x7c],'big')
            self.assertGreaterEqual(vector,0x200)
            self.assertLess(vector,0x2000)
            self.assertEqual(blob[vector:vector+2],bytes.fromhex('2f00'))
            self.assertEqual(blob[vector+8:vector+12],bytes.fromhex('201f4e73'))
            self.assertIn(bytes.fromhex('8164'),blob[0x200:0x2000])
            self.assertIn(bytes.fromhex('2000'),blob[0x200:0x2000])

    def test_h32_rom(self):
        blob,info=build_scroll_rom(self.image(256,320),256)
        self.assertEqual(info['screen_size'],[256,224])
        self.assertEqual(info['scroll_range_pixels'],[0,96])
        tx,ty,sw,sh,gfx,attrs,cram,commands=struct.unpack_from('>HHHHLLLL',blob,0x1d0)
        self.assertEqual((tx,ty,sw,sh),(32,40,32,28))
        self.assertEqual(int.from_bytes(blob[commands+4:commands+8],'big'),0x40400003)
    def test_small_canvas_rejected(self):
        with self.assertRaisesRegex(ValueError,"pelo menos"):
            build_scroll_rom(self.image(256,256),320)
    def test_native_size_rejected(self):
        with self.assertRaisesRegex(ValueError,"estática"):
            build_scroll_rom(self.image(320,224),320)
    def test_size_limit(self):
        with self.assertRaisesRegex(ValueError,"máximo"):
            build_scroll_rom(self.image(1032,256),320)
    def test_invalid_pixel_indices(self):
        obj=self.image()
        obj.indices[0,0]=16
        with self.assertRaisesRegex(ValueError,"Índice de cor"):
            build_scroll_rom(obj,320)

if __name__=="__main__":
    unittest.main()
