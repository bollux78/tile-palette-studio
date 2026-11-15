import unittest
import struct
from types import SimpleNamespace
import numpy as np
from rom_test import build_test_rom, _vdp_cmd

class RomTest(unittest.TestCase):
    def make_result(self,width):
        tx=width//8
        indices=np.zeros((224,width),dtype=np.uint8)
        indices[:,8:16]=1
        palettes=np.zeros((4,16,3),dtype=np.uint8)
        palettes[:,1]=[238,102,34]
        return SimpleNamespace(
            source_size=(width,224),
            indices=indices,
            tile_palettes=np.zeros((28,tx),dtype=np.uint8),
            palettes_rgb=palettes,
            settings=SimpleNamespace(allow_lossy_tiles=False,palettes=4,colors=16))
    def test_h40(self):
        rom,info=build_test_rom(self.make_result(320))
        self.assertEqual(len(rom),131072)
        self.assertEqual(int.from_bytes(rom[4:8],'big'),0x200)
        self.assertEqual(rom[0x100:0x104],b'SEGA')
        self.assertLess(info['tiles'],1536)
        self.assertEqual(int.from_bytes(rom[:4],'big'),0x00ffff00)
        self.assertIn(b'SEGA',rom[0x200:0x300])
        self.assert_valid_loops(rom)
    def assert_valid_loops(self,rom):
        # Every DBRA D0 must branch to an instruction start, not the middle
        # of the preceding MOVE.W or its address extension.
        code=rom[0x200:0x600]
        seen=0
        for offset in range(0,len(code)-4,2):
            if code[offset:offset+2] != bytes.fromhex('51c8'):
                continue
            disp=struct.unpack('>h',code[offset+2:offset+4])[0]
            target=offset+2+disp
            self.assertGreaterEqual(target,0)
            self.assertIn(code[target:target+2],
                          (bytes.fromhex('33d8'),bytes.fromhex('33fc')))
            seen+=1
        self.assertEqual(seen,5)

    def test_h32(self):
        rom,info=build_test_rom(self.make_result(256))
        self.assertEqual(len(rom),131072)
        self.assertEqual(info['width'],256)
        self.assert_valid_loops(rom)
    def test_rom_uses_unmodified_tiles_and_identity_tilemap(self):
        obj=self.make_result(320)
        obj.indices[:8,:8]=3
        obj.indices[:8,8:16]=2
        obj.tile_palettes[0,0]=1
        obj.tile_palettes[0,1]=2
        rom,info=build_test_rom(obj)
        self.assertEqual(info['tiles'],1121)
        pointers=[]
        pos=0x200
        while True:
            pos=rom.find(bytes.fromhex('41f9'),pos,0x600)
            if pos<0:break
            pointers.append(int.from_bytes(rom[pos+2:pos+6],'big'))
            pos+=6
        self.assertEqual(len(pointers),3)
        tiles_start,map_start,_=pointers
        self.assertEqual(rom[tiles_start:tiles_start+32],bytes(32))
        self.assertEqual(rom[tiles_start+32:tiles_start+64],bytes([0x33])*32)
        self.assertEqual(rom[tiles_start+64:tiles_start+96],bytes([0x22])*32)
        self.assertEqual(int.from_bytes(rom[map_start:map_start+2],'big'),0x2001)
        self.assertEqual(int.from_bytes(rom[map_start+2:map_start+4],'big'),0x4002)
        self.assertEqual(int.from_bytes(rom[map_start+128:map_start+130],'big'),41)

    def test_h32_rom_keeps_all_896_tiles(self):
        obj=self.make_result(256)
        obj.settings.allow_lossy_tiles=True  # flag has no effect on a test ROM
        _,info=build_test_rom(obj)
        self.assertEqual(info['tiles'],897)

    def test_opaque_quantization_never_uses_transparent_index_zero(self):
        from PIL import Image
        from quantizer import Settings,quantize
        img=Image.new('RGB',(16,16),(70,112,158))
        res=quantize(img,Settings(palettes=2,colors=16,iterations=1,dither='vertical4'))
        self.assertTrue(np.all(res.indices>0))
        res_floyd=quantize(img,Settings(palettes=2,colors=16,iterations=1,dither='floyd'))
        self.assertTrue(np.all(res_floyd.indices>0))

    def test_invalid_dimensions(self):
        obj=self.make_result(320)
        obj.source_size=(320,240)
        with self.assertRaises(ValueError):build_test_rom(obj)
    def test_vdp_commands(self):
        self.assertEqual(_vdp_cmd(0x0000),0x40000000)
        self.assertEqual(_vdp_cmd(0xc000),0x40000003)
        self.assertEqual(_vdp_cmd(0x0000,'cram'),0xc0000000)

if __name__=='__main__':
    unittest.main()
