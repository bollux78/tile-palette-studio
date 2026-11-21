"""Master System Mode 4 hardware scrolling with Sega-mapper pattern streaming.

The entire image resides in ROM. A circular 32x28 name table and a 32x25
working window select a resident atlas or an on-demand, reference-counted cache.
The leftmost eight screen pixels are masked (normal SMS horizontal scrolling),
so the usable viewport is 248x192. No re-quantization occurs in the ROM builder.
"""
import base64
import struct
from pathlib import Path
import numpy as np
from tile_optimizer import optimize
from sms_quantizer import cram_data

MAX_EDGE=1024
MAX_MAP_TILES=4096
PARAMETERS=0x3f00


def build_scroll_rom(result):
    width,height=map(int,result.source_size)
    if width<256 or height<192:
        raise ValueError('ROM com rolagem: a imagem deve ter pelo menos 256 × 192 pixels.')
    if (width,height)==(256,192):
        raise ValueError('A imagem cabe em uma tela; use a ROM estática.')
    if width>MAX_EDGE or height>MAX_EDGE:
        raise ValueError('ROM com rolagem: máximo de 1024 pixels por eixo.')
    ty,tx=result.tile_palettes.shape
    if (ty,tx)!=((height+7)//8,(width+7)//8) or result.indices.shape!=(ty*8,tx*8):
        raise ValueError('Índices e dimensões do mapa incompatíveis.')
    if tx*ty>MAX_MAP_TILES:
        raise ValueError('ROM com rolagem: máximo de 4096 posições de tiles (por exemplo, 512 × 512).')
    if not np.issubdtype(result.indices.dtype,np.integer) or np.any(result.indices<0) or np.any(result.indices>=result.settings.colors):
        raise ValueError('Índices de cor inválidos.')
    if not np.issubdtype(result.tile_palettes.dtype,np.integer) or np.any(result.tile_palettes<0) or np.any(result.tile_palettes>=result.settings.palettes):
        raise ValueError('Índices de paleta inválidos.')
    cfg=result.settings
    if not 1<=cfg.palettes<=2 or not 2<=cfg.colors<=16:
        raise ValueError('Paletas incompatíveis com Master System Mode 4.')
    slots=min(cfg.vram_budget_tiles,448-cfg.base_tile)
    if not 0<=cfg.base_tile<448 or slots<1:
        raise ValueError('Orçamento ou tile inicial inválido.')
    # Full-image lossless IDs are ROM addresses, NOT 9-bit VRAM indexes.
    opt=optimize(result.indices,result.tile_palettes)
    mapping=opt['mapping'].reshape(ty,tx)
    n=opt['unique_count']
    resident=n<=slots
    peak=n if resident else 0
    if not resident:
        # Every possible tile-aligned camera position, including reversals and
        # diagonal intermediate states, must fit the 32x25 working set.
        for y in range((height-192)//8+1):
            for x in range((width-248)//8+1):
                count=len(np.unique(mapping[y:min(y+25,ty),x:min(x+32,tx)]))
                peak=max(peak,count)
        if peak>slots and cfg.allow_lossy_tiles:
            opt=optimize(result.indices,result.tile_palettes,budget=slots,allow_lossy=True,
                         palettes_rgb=result.palettes_rgb,reserve_zero=cfg.transparent)
            n=opt['unique_count']
            resident=n<=slots
            if resident:peak=n
        if peak>slots:
            raise ValueError(f'Uma região da imagem precisa de {peak} tiles únicos, mas há {slots} disponíveis. Ative a substituição por similares e quantize novamente, aumente o orçamento ou reduza os detalhes. A rolagem permite mais tiles na ROM, mas não mais tiles simultâneos na VRAM.')
    tiles=opt['tiles']
    planes=np.empty((n,8,4),np.uint8)
    for bit in range(4):planes[:,:,bit]=np.packbits((tiles>>bit)&1,axis=2)[:,:,0]
    world=np.empty((ty*tx,3),np.uint8)
    world[:,0]=opt['mapping']&255
    world[:,1]=opt['mapping']>>8
    world[:,2]=((opt['flips']&0x0800)>>10)|((opt['flips']&0x1000)>>10)|(result.tile_palettes.ravel()<<3)
    cram=cram_data(result)
    try:loader=base64.b64decode(Path(__file__).with_name('sms_scroll_loader.b64').read_text(),validate=False)
    except (OSError,ValueError) as exc:raise ValueError('Carregador Z80 de rolagem indisponível.') from exc
    if not 0x100<len(loader)<0x3e00 or loader[:3]!=bytes([0xc3,0x00,0x01]):
        raise ValueError('Carregador Z80 de rolagem inválido.')
    payload=planes.tobytes()
    size=max(65536,1<<(0x8000+len(payload)-1).bit_length())
    size_codes={65536:0xd,131072:0xe,262144:0xf,524288:0x0}
    if size not in size_codes:raise ValueError('Imagem excede o limite da ROM de rolagem.')
    rom=bytearray([255])*size
    rom[:len(loader)]=loader
    rom[0x3e00:0x3e20]=cram
    struct.pack_into('<BBHHHHBHH',rom,PARAMETERS,tx,ty,width-248,height-192,tx*3,n,int(resident),cfg.base_tile,slots)
    rom[0x3f0f]=15 if cfg.rom_border is not None else 0
    rom[0x4000:0x4000+world.size]=world.tobytes()
    rom[0x8000:0x8000+len(payload)]=payload
    rom[0x7ff0:0x8000]=b'TMR SEGA'+bytes([0,0,0,0,0,0,0,0x40|size_codes[size]])
    checksum=(sum(rom[:0x7ff0])+sum(rom[0x8000:]))&65535
    struct.pack_into('<H',rom,0x7ffa,checksum)
    return bytes(rom),{'mode':'scroll','image_size':[width,height],'screen_size':[256,192],
                       'viewport_size':[248,192],'scroll_range_pixels':[width-248,height-192],
                       'step_pixels':2,'unique_tiles':n,'peak_cache_tiles':peak,
                       'cache_slots':slots,'resident_atlas':resident,'lossy_merges':int(opt['lossy_merges']),'rom_bytes':size}
