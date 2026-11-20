import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from sms_quantizer import Settings,quantize,hardware_data,export
from sms_rom import build_test_rom


def decode_tiles(data):
    planes=np.frombuffer(data,np.uint8).reshape(-1,8,4)
    out=np.zeros((len(planes),8,8),np.uint8)
    for bit in range(4):
        out|=np.unpackbits(planes[:,:,bit,None],axis=2).astype(np.uint8)<<bit
    return out


def render_hardware(tiles,attrs,cram,width,height,base=0):
    patterns=decode_tiles(tiles)
    attrs=np.frombuffer(attrs,dtype='<u2').reshape(height//8,width//8)
    colors=np.frombuffer(cram,np.uint8).reshape(2,16)
    palette=np.stack([colors&3,(colors>>2)&3,(colors>>4)&3],axis=-1)*85
    rgb=np.zeros((height,width,3),np.uint8)
    for y,row in enumerate(attrs):
        for x,a in enumerate(row):
            tile=patterns[(int(a)&511)-base]
            if a&0x200:tile=tile[:,::-1]
            if a&0x400:tile=tile[::-1,:]
            rgb[y*8:y*8+8,x*8:x*8+8]=palette[(a>>11)&1][tile]
    return rgb


class SMSTests(unittest.TestCase):
    def image(self):
        # Sixteen exact hardware colors, including opaque palette entry zero.
        colors=np.array([(r*85,g*85,0) for r in range(4) for g in range(4)],np.uint8)
        return Image.fromarray(np.tile(colors.reshape(4,4,3),(4,4,1)))

    def test_full_sixteen_colors_and_zero(self):
        r=quantize(self.image(),Settings(palettes=1,iterations=3))
        self.assertEqual(r.mean_squared_error,0)
        self.assertEqual(len(np.unique(r.indices)),16)
        self.assertTrue(np.all(r.palettes_rgb%85==0))

    def test_all_dithers_round_trip(self):
        for d in ['off','floyd','vertical4','horizontal4','diagonal4','vertical2','horizontal2','diagonal2']:
            with self.subTest(dither=d):
                r=quantize(self.image(),Settings(dither=d,iterations=2,base_tile=5))
                tiles,attrs,cram,opt=hardware_data(r)
                rgb=render_hardware(tiles,attrs,cram,16,16,5)
                np.testing.assert_array_equal(rgb,np.array(r.preview)[:,:,:3])
                self.assertEqual(len(cram),32)
                self.assertTrue(all(c<64 for c in cram))

    def test_flip_and_palette_attributes(self):
        r=quantize(Image.new('RGB',(16,8)),Settings(iterations=1))
        tile=np.arange(64,dtype=np.uint8).reshape(8,8)%16
        r.indices=np.concatenate([tile,tile[:,::-1]],axis=1)
        r.tile_palettes=np.array([[0,1]],np.int16)
        tiles,attrs,_,opt=hardware_data(r)
        words=np.frombuffer(attrs,dtype='<u2')
        self.assertEqual(opt['unique_count'],1)
        self.assertEqual(int(words[1]),0x0a00)
        np.testing.assert_array_equal(decode_tiles(tiles)[0],tile)

    def test_transparent_pixels_reserve_zero(self):
        im=Image.new('RGBA',(8,8),(255,0,0,255));im.putpixel((0,0),(0,0,0,0))
        r=quantize(im,Settings(transparent=True,background='#55aaff',iterations=1))
        self.assertEqual(r.indices[0,0],0)
        self.assertTrue(np.all(r.indices[1:]>0))
        self.assertEqual(r.preview.getpixel((0,0))[3],0)
        np.testing.assert_array_equal(r.palettes_rgb[:,0],[[85,170,255]]*2)

    def test_limits_and_package(self):
        with self.assertRaises(ValueError):quantize(self.image(),Settings(palettes=3))
        with self.assertRaises(ValueError):quantize(self.image(),Settings(base_tile=448))
        r=quantize(self.image(),Settings(palettes=1,iterations=1))
        with tempfile.TemporaryDirectory() as folder:
            files=export(r,folder,'test')
            manifest=json.loads((Path(folder)/'test.json').read_text())
            self.assertEqual(manifest['format'],'Sega Master System Mode 4')
            self.assertEqual(len(files),9)
            self.assertIn('SMS_loadTileMapArea',(Path(folder)/'test_example.c').read_text())
        with self.assertRaises(ValueError):build_test_rom(r)

    def test_over_budget_rejects_export(self):
        rng=np.random.default_rng(7)
        r=quantize(Image.fromarray(rng.integers(0,256,(16,16,3),dtype=np.uint8)),Settings(vram_budget_tiles=1,iterations=1))
        with self.assertRaises(ValueError):hardware_data(r)

    def test_z80_boot_upload_and_checksum(self):
        r=quantize(Image.new('RGB',(256,192),(255,85,170)),Settings(iterations=1,base_tile=3))
        rom,_=build_test_rom(r)
        self.assertEqual(len(rom),32768)
        self.assertEqual(rom[0x7ff0:0x7ff8],b'TMR SEGA')
        self.assertEqual(int.from_bytes(rom[0x7ffa:0x7ffc],'little'),sum(rom[:0x7ff0])&65535)
        # Execute the emitted Z80 subset and decode actual VDP port writes.
        pc=a=b=c=hl=0;zero=False;ctrl=None;address=0;is_cram=False
        vram=bytearray(16384);cram=bytearray(32);regs={}
        def output(port,value):
            nonlocal ctrl,address,is_cram
            if port==0xbf:
                if ctrl is None:ctrl=value
                else:
                    if value&0xc0==0x80:regs[value&15]=ctrl
                    else:address=((value&0x3f)<<8)|ctrl;is_cram=value&0xc0==0xc0
                    ctrl=None
            else:
                memory=cram if is_cram else vram
                memory[address%len(memory)]=value;address+=1
        for _ in range(200000):
            op=rom[pc];pc+=1
            if op==0xc3:pc=int.from_bytes(rom[pc:pc+2],'little')
            elif op==0xf3:pass
            elif op==0x31:pc+=2
            elif op==0x3e:a=rom[pc];pc+=1
            elif op==0xd3:output(rom[pc],a);pc+=1
            elif op==0x21:hl=int.from_bytes(rom[pc:pc+2],'little');pc+=2
            elif op==0x01:c,b=rom[pc:pc+2];pc+=2
            elif op==0x7e:a=rom[hl]
            elif op==0x23:hl=(hl+1)&65535
            elif op==0x0b:
                bc=((b<<8)|c)-1;b=(bc>>8)&255;c=bc&255
            elif op==0x78:a=b
            elif op==0xb1:a|=c;zero=a==0
            elif op in (0x20,0x18):
                offset=rom[pc];pc+=1
                if op==0x18 and offset==0xfe:break
                if op==0x18 or not zero:pc+=offset if offset<128 else offset-256
            else:self.fail(f'Unexpected Z80 instruction {op:02x}')
        else:self.fail('Boot did not terminate')
        self.assertEqual(regs[1],0x40)
        self.assertEqual(vram[0x3f00],0xd0)
        tiles,attrs,pal,opt=hardware_data(r)
        self.assertEqual(vram[96:96+len(tiles)],tiles)
        self.assertEqual(vram[0x3800:0x3800+len(attrs)],attrs)
        self.assertEqual(cram,pal)
        rgb=render_hardware(tiles,attrs,pal,256,192,3)
        np.testing.assert_array_equal(rgb,np.asarray(r.preview)[:,:,:3])
