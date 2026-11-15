"""Generate and audit the web ROM independently of the Mega Drive emulator."""
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from quantizer import Settings, quantize
from rom_test import build_test_rom

out = Path('diagnostics')
out.mkdir(exist_ok=True)
img = Image.open('cholirede.png').convert('RGBA')
cfg = Settings(palettes=4,colors=16,iterations=10,dither='vertical4',
               dither_strength=.38,base_tile=0,vram_budget_tiles=1024)
result = quantize(img,cfg)
rom,meta = build_test_rom(result)
(out/'valentina_test.bin').write_bytes(rom)
result.preview.save(out/'quantized_preview.png')
width,height = result.source_size
tx,ty=width//8,height//8
positions=tx*ty
code=rom[0x200:0x600]
pointers=[]
for i in range(0,len(code)-6,2):
    if code[i:i+2]==b'\x41\xf9':
        pointers.append(int.from_bytes(code[i+2:i+6],'big'))
if len(pointers)!=3:
    raise RuntimeError(f'Expected 3 LEA source pointers, got {pointers}')
tiles_start,map_start,cram_start=pointers
tiles_raw=rom[tiles_start:tiles_start+(positions+1)*32]
map_raw=rom[map_start:map_start+((64 if tx==40 else 32)*32)*2]
cram_raw=rom[cram_start:cram_start+128]
# Unpack tile graphics exactly as the 68000 wrote them.
packed=np.frombuffer(tiles_raw,dtype=np.uint8).reshape(positions+1,8,4)
tiles=np.empty((positions+1,8,8),dtype=np.uint8)
tiles[:,:,0::2]=(packed>>4)&15
tiles[:,:,1::2]=packed&15
stride=64 if tx==40 else 32
attr=np.frombuffer(map_raw,dtype='>u2').reshape(32,stride)
cram=np.frombuffer(cram_raw,dtype='>u2').reshape(4,16)
render=np.zeros((height,width,3),dtype=np.uint8)
for y in range(ty):
    for x in range(tx):
        a=int(attr[y,x])
        index=a&0x7ff
        pal=(a>>13)&3
        t=tiles[index]
        if a&0x0800:t=t[:,::-1]
        if a&0x1000:t=t[::-1,:]
        colors=cram[pal][t]
        render[y*8:y*8+8,x*8:x*8+8,0]=((colors>>1)&7)*34
        render[y*8:y*8+8,x*8:x*8+8,1]=((colors>>5)&7)*34
        render[y*8:y*8+8,x*8:x*8+8,2]=((colors>>9)&7)*34
preview=np.asarray(result.preview.convert('RGB'))
difference=np.abs(render.astype(np.int16)-preview.astype(np.int16))

# Mega Drive plane A treats palette index 0 as transparent independently of
# whether the source image requested transparency. Plane B has a cleared
# name table whose entries all refer to tile index 0. The ROM currently
# writes real image pixels into that tile, so "transparent" foreground
# pixels reveal copies of the image's first tile in plane B.
zero_mask = result.indices[:height,:width] == 0
Image.fromarray((zero_mask.astype(np.uint8)*255),'L').save(out/'index0_mask.png')
tile_zero = tiles[0]
background_codes = cram[0][tile_zero]
background=np.empty((8,8,3),dtype=np.uint8)
background[:,:,0]=((background_codes>>1)&7)*34
background[:,:,1]=((background_codes>>5)&7)*34
background[:,:,2]=((background_codes>>9)&7)*34
tiled_background=np.tile(background,(height//8,width//8,1))
predicted=render.copy()
predicted[zero_mask]=tiled_background[zero_mask]
Image.fromarray(predicted).save(out/'predicted_with_planeB_tile0.png')

Image.fromarray(render).save(out/'decoded_rom.png')
Image.fromarray(np.clip(difference*3,0,255).astype(np.uint8)).save(out/'diff_x3.png')
mismatch=int(np.any(difference!=0,axis=2).sum())
exact=np.array_equal(render,preview)
report={
    'ROM_file_size':len(rom),
    'image_size':[width,height],
    'positions':positions,
    'reserved_blank_tile0':bool(np.all(tiles[0]==0)),
    'first_tilemap_index':int(attr[0,0]),
    'palette_count':cfg.palettes,
    'source_addresses':pointers,
    'tile_bytes':len(tiles_raw),
    'map_bytes':len(map_raw),
    'nonzero_pixels_different_rom_vs_preview':mismatch,
    'max_abs_pixel_difference':int(difference.max()),
    'image_pixels_with_palette_index0_transparent_on_hardware':int(zero_mask.sum()),
    'palette_index0_fraction':float(zero_mask.mean()),
    'pattern0_unique_colors':int(len(np.unique(tiles[0]))),
    'pixel_exact_ROM_data_vs_Python_preview':bool(exact),
    'rom_sprites_table_reg5':hex(0xF000),
    'planeA_base_reg2':hex(0xC000),
    'notes':'ROM decoded independently from stored 4bpp tiles, attributes and CRAM'
}
(out/'audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
print(json.dumps(report,indent=2,ensure_ascii=False))
