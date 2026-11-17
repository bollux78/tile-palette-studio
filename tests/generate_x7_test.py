"""Generate small experimental X7 compatibility ROMs for cartridge testing.

No personal images are included. Both ROMs use a synthetic colored grid.
"""
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from rom_test import build_test_rom
from scroll_rom import build_scroll_rom

out=Path("diagnostics/x7")
out.mkdir(parents=True,exist_ok=True)
def make(w,h):
    tw,th=w//8,h//8
    yy,xx=np.indices((h,w))
    indices=(1+((xx//8)+(yy//8)*3+xx%8//3)%15).astype(np.uint8)
    tile_palettes=np.fromfunction(lambda y,x:(x//5+y//4)%4,(th,tw),dtype=int).astype(np.uint8)
    palette=np.zeros((4,16,3),dtype=np.uint8)
    for p in range(4):
        for c in range(1,16):
            palette[p,c]=[34*((c+p)%8),34*((2*c+p)%8),34*((3*c+p)%8)]
    return SimpleNamespace(
        source_size=(w,h),indices=indices,tile_palettes=tile_palettes,
        palettes_rgb=palette,settings=SimpleNamespace(palettes=4,colors=16))
static,info=build_test_rom(make(320,224))
(out/"x7_static_test.bin").write_bytes(static)
print("static",info)
scroll,info=build_scroll_rom(make(512,256),320)
(out/"x7_scroll_test.bin").write_bytes(scroll)
print("scroll",info)
