"""Standalone scrollable Mega Drive test ROM builder.

A small preassembled 68000 viewer is embedded as text (scroll_loader.b64).
The viewer redraws a fixed 320x224 or 256x224 viewport as the user presses
the directional pad, moving 8 pixels per step. Source tiles stay in ROM.
No SGDK, no external compilation, no compression or inaccurate flip reuse.
"""
from pathlib import Path
import base64
import struct
import numpy as np

from quantizer import _genesis_cram_word
from rom_test import _vdp_cmd

TILE_DATA_ADDR = 0x2000
ROM_LIMIT = 2 * 1024 * 1024
MAX_EDGE = 1024

def build_scroll_rom(result, screen_width=320):
    width, height = map(int, result.source_size)
    if screen_width not in (256, 320):
        raise ValueError('Tela da ROM deve ser H32 256×224 ou H40 320×224.')
    if width < screen_width or height < 224:
        raise ValueError(
            'ROM com direcional: a imagem deve ter pelo menos '
            f'{screen_width}×224 pixels. Use H32 ou aumente o canvas.'
        )
    if width == screen_width and height == 224:
        raise ValueError('A imagem já cabe na tela; use a ROM estática.')
    if width > MAX_EDGE or height > MAX_EDGE:
        raise ValueError(f'ROM com scroll: máximo {MAX_EDGE}×{MAX_EDGE} pixels.')
    if result.settings.colors > 16 or result.settings.palettes > 4:
        raise ValueError('Número de paletas/cores excede o Mega Drive.')
    ty, tx = result.tile_palettes.shape
    if (ty, tx) != ((height + 7)//8, (width + 7)//8):
        raise ValueError('Dimensões do tilemap incompatíveis com a imagem.')
    if result.indices.shape != (ty*8, tx*8):
        raise ValueError('Índices não correspondem ao tilemap.')
    if not np.issubdtype(result.indices.dtype, np.integer):
        raise ValueError('Os pixels quantizados devem ter índices inteiros.')
    if np.any(result.indices < 0) or np.any(result.indices > 15):
        raise ValueError('Índice de cor deve estar entre 0 e 15.')
    if np.any(result.tile_palettes > 3):
        raise ValueError('Índice de paleta deve estar entre 0 e 3.')
    n = tx * ty
    tiles = result.indices.reshape(ty,8,tx,8).transpose(0,2,1,3).reshape(n,8,8)
    packed = ((tiles[:,:,::2]<<4)|tiles[:,:,1::2]).astype(np.uint8).tobytes()
    # VDP pattern zero stays blank because the 68000 clears VRAM at boot.
    # The first payload tile is loaded directly into pattern slot 1.
    attrs = (result.tile_palettes.astype(np.uint16).reshape(-1)<<13).astype('>u2').tobytes()
    palette = np.zeros((4,16),dtype='>u2')
    for p in range(result.settings.palettes):
        for c in range(result.settings.colors):
            palette[p,c] = _genesis_cram_word(result.palettes_rgb[p,c])
    cram = palette.tobytes()
    stride = 64 if screen_width == 320 else 32
    commands = b''.join(struct.pack('>I',_vdp_cmd(0xC000 + y*stride*2)) for y in range(28))
    try:
        loader_text = Path(__file__).with_name('scroll_loader.b64').read_text(encoding='ascii').strip()
        loader = base64.b64decode(loader_text,validate=True)
    except (FileNotFoundError,ValueError) as exc:
        raise ValueError('Carregador 68000 da ROM com direcional indisponível.') from exc
    if not 0x200 < len(loader) <= TILE_DATA_ADDR:
        raise ValueError('Carregador de rolagem é maior que a região reservada.')
    if loader[0:4] != b'\x00\xff\xff\x00' or loader[4:8] != struct.pack('>I',0x200):
        raise ValueError('Cabeçalho inválido no carregador de rolagem.')
    graphics_ptr = TILE_DATA_ADDR
    attrs_ptr = graphics_ptr + len(packed)
    cram_ptr = attrs_ptr + len(attrs)
    commands_ptr = cram_ptr + len(cram)
    end = commands_ptr + len(commands)
    size = max(128*1024,1 << (end-1).bit_length())
    if size > ROM_LIMIT:
        raise ValueError('Imagem muito grande para a ROM de teste de 2 MiB.')
    rom = bytearray(size)
    rom[:len(loader)] = loader
    rom[graphics_ptr:attrs_ptr] = packed
    rom[attrs_ptr:cram_ptr] = attrs
    rom[cram_ptr:commands_ptr] = cram
    rom[commands_ptr:end] = commands
    # ROM-resident parameters read directly by the 68000 loader.
    struct.pack_into('>HHHHLLLL',rom,0x1d0,
                     tx,ty,screen_width//8,28,graphics_ptr,
                     attrs_ptr,cram_ptr,commands_ptr)
    struct.pack_into('>I',rom,0x1a4,size-1)
    checksum = sum(struct.unpack_from(f'>{(size-0x200)//2}H',rom,0x200)) & 0xffff
    struct.pack_into('>H',rom,0x18e,checksum)
    info = {
        'image_size':[width,height], 'screen_size':[screen_width,224],
        'scroll_range_pixels':[(tx-screen_width//8)*8,(ty-28)*8],
        'step_pixels':8, 'image_tiles':n, 'rom_bytes':size,
        'graphics_ptr':graphics_ptr, 'attributes_ptr':attrs_ptr,
        'palette_ptr':cram_ptr, 'commands_ptr':commands_ptr,
    }
    return bytes(rom),info
