"""Standalone Mega Drive / Genesis test ROM generator.

No SGDK runtime or external compiler required. Builds a small 68000 loader
and appends 4bpp graphics, plane A map and CRAM directly into the ROM.
Only 256x224 (H32) and 320x224 (H40) are supported initially.
"""
import struct
import numpy as np
from quantizer import _genesis_cram_word

ROM_SIZE = 128 * 1024
PLANE_A = 0xC000
TILE_LIMIT = PLANE_A // 32  # 1536 tiles; reserve VRAM above for name tables

def _be16(value):
    return struct.pack('>H', value & 0xffff)

def _be32(value):
    return struct.pack('>I', value & 0xffffffff)

def _vdp_cmd(address, target='vram'):
    # VDP control port: CD1 CD0 A13..A0 in first word;
    # CD5 CD4 CD3 CD2 0..0 A15 A14 in second word.
    command = ((address & 0x3fff) << 16) | ((address >> 14) & 3)
    return command | (0xC0000000 if target == 'cram' else 0x40000000)

def build_test_rom(result):
    width, height = result.source_size
    if (width, height) not in ((256,224), (320,224)):
        raise ValueError('ROM de teste: selecione H32 256×224 ou H40 320×224.')
    ty, tx = result.tile_palettes.shape
    if ty != 28 or tx != width//8:
        raise ValueError('Dimensões de tilemap incompatíveis com a ROM de teste.')
    # The test ROM is a static full-screen image: 320x224 has 1120
    # positions; 256x224 has 896. Both fit before the plane-A table
    # at 0xC000 (1536 4bpp tiles). Preserve each tile exactly and
    # avoid deduplication, flips and approximate replacement.
    count = ty * tx
    if count + 1 > TILE_LIMIT:
        raise ValueError('Imagem excede o espaço de tiles da ROM de teste (tile zero reservado).')
    if result.indices.shape != (ty*8,tx*8):
        raise ValueError('Índices de pixels incompatíveis com o tilemap.')
    if not np.issubdtype(result.indices.dtype,np.integer):
        raise ValueError('Os índices dos tiles devem ser inteiros.')
    if np.any(result.indices > 15) or np.any(result.indices < 0):
        raise ValueError('Índice de cor inválido para tiles 4bpp.')
    tiled = result.indices.reshape(ty,8,tx,8).transpose(0,2,1,3).reshape(count,8,8)
    # Tile 0 must be blank: an unused plane B references pattern 0, and
    # VDP color index 0 in plane A is transparent to the underlying plane.
    packed = bytes(32) + ((tiled[:,:,::2] << 4) | tiled[:,:,1::2]).astype(np.uint8).tobytes()
    # Plane A is 64x32 in H40 or 32x32 in H32. The tile number is
    # the raster position + 1 (tile 0 blank), with no H/V flips.
    stride = 64 if width == 320 else 32
    plane = np.zeros((32,stride),dtype='>u2')
    attrs = (np.arange(1,count+1,dtype=np.uint16) |
             (result.tile_palettes.ravel().astype(np.uint16)<<13))
    plane[:ty,:tx] = attrs.reshape(ty,tx)
    map_bytes = plane.tobytes()
    cram = np.zeros((4,16),dtype='>u2')
    for p in range(result.settings.palettes):
        for c in range(result.settings.colors):
            cram[p,c] = _genesis_cram_word(result.palettes_rgb[p,c])
    palette_bytes = cram.tobytes()

    code = bytearray()
    def word(v): code.extend(_be16(v))
    def long(v): code.extend(_be32(v))
    def vdp_register(reg,value):
        # MOVE.W #$8rxx, $C00004
        word(0x33fc);word(0x8000 | (reg<<8) | value);long(0x00c00004)
    def vdp_address(addr,target='vram'):
        # MOVE.L #command, $C00004
        word(0x23fc);long(_vdp_cmd(addr,target));long(0x00c00004)
    patches=[]
    def copy_words(length):
        if length%2 or not 0 < length//2 <= 32768:
            raise ValueError('Bloco de transferência inválido')
        # LEA source_address.L,A0 (patch source address later)
        word(0x41f9);patches.append(len(code));long(0)
        # MOVE.W #(number_of_words-1),D0
        word(0x303c);word(length//2-1)
        # MOVE.W (A0)+,$C00000
        loop_start = len(code)
        word(0x33d8);long(0x00c00000)
        # DBRA displacement is relative to opcode + 2.
        word(0x51c8);word(loop_start-len(code))
    # Interrupts masked. Unlock TMSS on Mega Drive models with security HW.
    # MOVE.B $A10001,D0 ; ANDI.B #15,D0 ; BEQ.S +10
    # MOVE.L #$53454741,$A14000 ("SEGA")
    word(0x46fc);word(0x2700)  # MOVE #$2700,SR
    word(0x1039);long(0x00a10001)
    word(0x0200);word(0x000f)
    word(0x670a)
    word(0x23fc);long(0x53454741);long(0x00a14000)
    registers = {
        0:0x04,1:0x04,2:0x30,3:0x34,4:0x07,5:0x78,6:0x00,
        7:0x00,10:0x00,11:0x00,12:(0x81 if width==320 else 0x00),
        13:0x3e,15:0x02,16:(0x01 if width==320 else 0x00),
        17:0x00,18:0x00
    }
    for reg,value in registers.items():
        vdp_register(reg,value)
    # Clear all VRAM before loading; otherwise old tiles and scroll tables
    # may make a static image appear corrupted or invisible.
    vdp_address(0x0000)
    word(0x303c);word(0x7fff)  # 32768 words - 1 in D0
    loop_start=len(code)
    word(0x33fc);word(0);long(0x00c00000)  # MOVE.W #0,$C00000
    word(0x51c8);word(loop_start-len(code))
    # Clear vertical scroll registers too.
    word(0x23fc);long(0x40000010);long(0x00c00004)
    word(0x303c);word(39)  # 40 VSRAM words
    loop_start=len(code)
    word(0x33fc);word(0);long(0x00c00000)
    word(0x51c8);word(loop_start-len(code))
    vdp_address(0x0000);copy_words(len(packed))
    vdp_address(PLANE_A);copy_words(len(map_bytes))
    vdp_address(0x0000,'cram');copy_words(len(palette_bytes))
    # Display ON + Mode 5 + VBlank interrupt enabled (VDP reg 1 bit 5).
    # Mega EverDrive X7's in-game menu relies on VBlank interrupts.
    vdp_register(1,0x64)
    word(0x46fc);word(0x2000)  # Allow IRQs after initializing the image.
    word(0x60fe)  # BRA.S * : static forever
    irq_address = 0x200 + len(code)
    # Preserve D0; acknowledge VDP VBlank interrupt; return from exception.
    word(0x2f00)  # MOVE.L D0,-(SP)
    word(0x3039);long(0x00c00004)  # MOVE.W $C00004,D0
    word(0x201f)  # MOVE.L (SP)+,D0
    word(0x4e73)  # RTE

    rom=bytearray(ROM_SIZE)
    # 68000 vectors: stack pointer, reset PC. Unused vectors point to loop.
    rom[0:4]=_be32(0x00ffff00)
    rom[4:8]=_be32(0x00000200)
    # Common vector handler: infinite loop at end of loader.
    idle_addr=0x200+len(code)-2
    for offset in range(8,0x100,4):
        rom[offset:offset+4]=_be32(idle_addr)
    rom[0x78:0x7c]=_be32(irq_address)  # 68000 level-6 VBlank autovector
    def header(offset,text,length):
        rom[offset:offset+length]=text.encode('ascii')[:length].ljust(length,b' ')
    header(0x100,'SEGA MEGA DRIVE ',16)
    header(0x110,'(C) AMINO 2026.NOV',16)
    header(0x120,'TILE PALETTE STUDIO TEST IMAGE',48)
    header(0x150,'TILE PALETTE STUDIO TEST IMAGE',48)
    header(0x180,'GM 00000000-00',14)
    header(0x190,'J',2)
    rom[0x1a0:0x1a4]=_be32(0)
    rom[0x1a4:0x1a8]=_be32(ROM_SIZE-1)
    rom[0x1a8:0x1ac]=_be32(0x00ff0000)
    rom[0x1ac:0x1b0]=_be32(0x00ffffff)
    header(0x1f0,'JUE',3)
    code_start=0x200
    data_start=(code_start+len(code)+1)&~1
    offsets=[]
    cursor=data_start
    for blob in (packed,map_bytes,palette_bytes):
        offsets.append(cursor)
        rom[cursor:cursor+len(blob)]=blob
        cursor+=len(blob)
    if cursor>ROM_SIZE:
        raise ValueError('Dados não cabem na ROM de teste')
    for patch,address in zip(patches,offsets):
        code[patch:patch+4]=_be32(address)
    rom[code_start:code_start+len(code)]=code
    checksum=sum(struct.unpack('>'+str((ROM_SIZE-0x200)//2)+'H',rom[0x200:])) & 0xffff
    rom[0x18e:0x190]=_be16(checksum)
    # Minimal sanity check on the hardware's reset-entry vectors.
    assert rom[0:4] == _be32(0x00ffff00) and rom[4:8] == _be32(0x00000200)
    return bytes(rom), {'tiles':count+1,'image_tiles':count,'width':width,'height':height,'size':ROM_SIZE}
