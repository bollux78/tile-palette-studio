"""Standalone 32 KiB SMS Mode 4 test ROM, no external assembler required.

Z80 boot disables IRQs; uploads native patterns, CRAM and a 32x28 name table;
terminates the sprite list; enables the display. Only standard 256x192 mode.
"""
from sms_quantizer import hardware_data


def build_test_rom(result):
    if result.source_size != (256,192):
        raise ValueError('A ROM de teste Master System requer 256 × 192 pixels.')
    tiles,tilemap,cram,opt=hardware_data(result)
    rom=bytearray([0xff])*32768
    code=bytearray([0xf3,0x31,0xf0,0xdf])  # DI; LD SP,$DFF0
    def emit(*values):code.extend(values)
    def out(value,port):emit(0x3e,value,0xd3,port)
    def reg(index,value):out(value,0xbf);out(0x80|index,0xbf)
    # Screen off, Mode 4, name table $3800, sprite table $3F00.
    for i,v in enumerate([0x04,0x00,0x0e,0xff,0xff,0x7e,0x00,(0x0f if result.settings.rom_border is not None else 0x00),0x00,0x00,0xff]):reg(i,v)
    cursor=0x400
    def upload(data,address,cram_write=False):
        nonlocal cursor
        rom[cursor:cursor+len(data)]=data
        out(address&255,0xbf);out(((address>>8)&0x3f)|(0xc0 if cram_write else 0x40),0xbf)
        emit(0x21,cursor&255,cursor>>8,0x01,len(data)&255,len(data)>>8) # HL source; BC count
        emit(0x7e,0xd3,0xbe,0x23,0x0b,0x78,0xb1,0x20,0xf7) # copy until BC=0
        cursor+=len(data)
    upload(tiles,result.settings.base_tile*32)
    upload(cram,0,True)
    # Invisible extra rows use the first valid tile, preserving nonzero base.
    tilemap+=bytes([result.settings.base_tile&255,result.settings.base_tile>>8])*128
    upload(tilemap,0x3800)
    upload(bytes([0xd0]),0x3f00)
    reg(1,0x40)
    emit(0x18,0xfe)  # idle; IRQs remain disabled
    if len(code)>=0x66:  # reset boot jumps over NMI vector
        rom[:3]=bytes([0xc3,0x00,0x01])
        rom[0x100:0x100+len(code)]=code
    else:rom[:len(code)]=code
    rom[0x66:0x68]=bytes([0xed,0x45]) # RETN for Pause/NMI
    rom[0x7ff0:0x7ff8]=b'TMR SEGA'
    rom[0x7ff8:0x8000]=bytes([0,0,0,0,0,0,0,0x4c])
    checksum=sum(rom[:0x7ff0])&0xffff
    rom[0x7ffa:0x7ffc]=checksum.to_bytes(2,'little')
    return bytes(rom),{'unique_tiles':opt['unique_count'],'mode':'256x192'}
