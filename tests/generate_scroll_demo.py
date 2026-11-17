"""Make a diagnostic large-image ROM with known, asymmetric colored tile content."""
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from scroll_rom import build_scroll_rom

out=Path('diagnostics/scroll_rom')
out.mkdir(parents=True,exist_ok=True)
width,height=512,256
tw,th=width//8,height//8
index=np.empty((height,width),dtype=np.uint8)
tilepal=np.empty((th,tw),dtype=np.uint8)
rgb=np.zeros((4,16,3),dtype=np.uint8)
for p in range(4):
    for c in range(1,16):
        rgb[p,c]=[(c*34)%256,((c+2*p)%8)*34,((c+3*p)%8)*34]
for ty in range(th):
    for tx in range(tw):
        # Discrete 8x8 patterns and tiles with several colors.
        yy,xx=np.mgrid[:8,:8]
        index[ty*8:(ty+1)*8,tx*8:(tx+1)*8] = 1+(tx+ty+xx//3+yy//3)%15
        tilepal[ty,tx]=(tx//6+ty//5)%4
result=SimpleNamespace(
    source_size=(width,height),indices=index,
    tile_palettes=tilepal,palettes_rgb=rgb,
    settings=SimpleNamespace(colors=16,palettes=4))
for mode in (320,256):
    rom,info=build_scroll_rom(result,mode)
    (out/f'test_{mode}.bin').write_bytes(rom)
    # Produce expected viewport PNGs independently of the assembler.
    for offset in (0,8,16,24):
        tpx=offset
        colors=np.empty((224,mode,3),dtype=np.uint8)
        for py in range(224):
            for px in range(mode):
                x=px+tpx
                p=int(tilepal[py//8,x//8])
                c=int(index[py,x])
                colors[py,px]=rgb[p,c]
        Image.fromarray(colors,'RGB').save(out/f'expected_{mode}_x{offset}.png')
    print(mode,info)
