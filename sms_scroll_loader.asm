; SMS Mode 4 streaming viewer. pyz80 assembler, original implementation.
; Bank 0: code, metadata, CRAM. Bank 1: 3-byte world map entries.
; Bank 2+: native planar patterns. Slot 2 uses the standard Sega mapper.
; 32x25 working window; 32x28 circular name table; optional 448-slot cache.
CAMX: equ 0xc000
CAMY: equ 0xc002
BASEX: equ 0xc004
BASEY: equ 0xc005
INPUT: equ 0xc006
SX: equ 0xc010
SY: equ 0xc011
COUNT: equ 0xc012
AXIS: equ 0xc013
REMAIN: equ 0xc014
MPTR: equ 0xc016
VPTR: equ 0xc018
RPTR: equ 0xc01a
WX: equ 0xc01c
WY: equ 0xc01d
TID: equ 0xc020
FLAGS: equ 0xc022
SLOT: equ 0xc024
INITROW: equ 0xc026
DIRTY: equ 0xc027
CELLS: equ 0xc400
REFS: equ 0xcb00
TAGS: equ 0xce80
TW: equ 0x3f00
TH: equ 0x3f01
MAXX: equ 0x3f02
MAXY: equ 0x3f04
STRIDE: equ 0x3f06
NTILES: equ 0x3f08
STATIC: equ 0x3f0a
TILEBASE: equ 0x3f0b
NSLOTS: equ 0x3f0d

 org 0
 jp boot
 defs 0x66-$
 retn
 defs 0x80-$
 dw main_loop
 defs 0x100-$
boot:
 di
 ld sp,0xdff0
 ; Silence all four PSG channels.
 ld a,0x9f
 out (0x7f),a
 ld a,0xbf
 out (0x7f),a
 ld a,0xdf
 out (0x7f),a
 ld a,0xff
 out (0x7f),a
 xor a
 ld (0xfffc),a
 ld (0xfffd),a
 inc a
 ld (0xfffe),a
 inc a
 ld (0xffff),a
 ; Clear 8 KiB work RAM (including the mapper shadow bytes).
 ld hl,0xc000
 ld de,0xc001
 ld bc,0x1fff
 ld (hl),0
 ldir
 ld hl,CELLS
 ld de,CELLS+1
 ld bc,1791
 ld (hl),0xff
 ldir
 ld hl,TAGS
 ld de,TAGS+1
 ld bc,895
 ld (hl),0xff
 ldir
 ; Mapper was cleared through mirrored work RAM: restore ROM banks.
 xor a
 ld (0xfffc),a
 ld (0xfffd),a
 inc a
 ld (0xfffe),a
 inc a
 ld (0xffff),a
 ld hl,registers
 ld b,11
 ld c,0x80
init_regs:
 ld a,(hl)
 out (0xbf),a
 ld a,c
 out (0xbf),a
 inc hl
 inc c
 djnz init_regs
 ; Hide all sprites.
 ld a,0
 out (0xbf),a
 ld a,0x7f
 out (0xbf),a
 ld a,0xd0
 out (0xbe),a
 ; Upload 32 CRAM bytes.
 xor a
 out (0xbf),a
 ld a,0xc0
 out (0xbf),a
 ld hl,0x3e00
 ld bc,0x20be
 otir
 ld a,(STATIC)
 or a
 jr z,init_map
 ; Resident atlas fits entirely: no pattern uploads while scrolling.
 ld hl,(TILEBASE)
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 ld a,l
 out (0xbf),a
 ld a,h
 or 0x40
 out (0xbf),a
 ld hl,0x8000
 ld de,(NTILES)
init_patterns:
 ld bc,0x20be
 otir
 dec de
 ld a,d
 or e
 jr nz,init_patterns
init_map:
 xor a
 ld (INITROW),a
init_map_row:
 xor a
 ld (SX),a
 ld a,(INITROW)
 ld (SY),a
 ld a,32
 ld (COUNT),a
 ld a,1
 ld (AXIS),a
 call draw_strip
 ld a,(INITROW)
 inc a
 ld (INITROW),a
 cp 25
 jr c,init_map_row
 call scroll_regs
 ld a,0x40
 out (0xbf),a
 ld a,0x81
 out (0xbf),a
main_loop:
 call wait_vblank
 xor a
 ld (DIRTY),a
 in a,(0xdc)
 cpl
 and 0x0f
 ld (INPUT),a
 ; Opposing directions cancel. Horizontal camera advances 2 pixels.
 and 0x0c
 cp 0x04
 jr nz,try_right
 ld hl,(CAMX)
 call decrease
 ld (CAMX),hl
 jr moved_x
try_right:
 cp 0x08
 jr nz,moved_x
 ld hl,(CAMX)
 ld de,(MAXX)
 call increase
 ld (CAMX),hl
moved_x:
 ld hl,(CAMX)
 call pixel_to_tile
 ld b,a
 ld a,(BASEX)
 cp b
 jr z,vertical_input
 jr c,x_forward
 push af
 ld a,1
 ld (DIRTY),a
 pop af
 ; Moving left: release rightmost column, then load new left column.
 add a,31
 ld (SX),a
 ld a,(BASEY)
 ld (SY),a
 ld a,25
 ld (COUNT),a
 xor a
 ld (AXIS),a
 push bc
 call release_strip
 pop bc
 ld a,b
 ld (BASEX),a
 ld (SX),a
 call draw_strip
 jr vertical_input
x_forward:
 push af
 ld a,1
 ld (DIRTY),a
 ; At fine X=0 the entering column is outside the 248-pixel viewport.
 ; Commit the aligned camera first: the outgoing column is now invisible.
 call scroll_regs
 pop af
 ld (SX),a
 ld a,(BASEY)
 ld (SY),a
 ld a,25
 ld (COUNT),a
 xor a
 ld (AXIS),a
 push bc
 call release_strip
 pop bc
 ld a,b
 ld (BASEX),a
 add a,31
 ld (SX),a
 call draw_strip
vertical_input:
 ld a,(INPUT)
 and 0x03
 cp 1
 jr nz,try_down
 ld hl,(CAMY)
 call decrease
 ld (CAMY),hl
 jr moved_y
try_down:
 cp 2
 jr nz,moved_y
 ld hl,(CAMY)
 ld de,(MAXY)
 call increase
 ld (CAMY),hl
moved_y:
 ld hl,(CAMY)
 call pixel_to_tile
 ld b,a
 ld a,(BASEY)
 cp b
 jp z,frame_done
 jr c,y_forward
 push af
 ld a,1
 ld (DIRTY),a
 pop af
 add a,24
 ld (SY),a
 ld a,(BASEX)
 ld (SX),a
 ld a,32
 ld (COUNT),a
 ld a,1
 ld (AXIS),a
 push bc
 call release_strip
 pop bc
 ld a,b
 ld (BASEY),a
 ld (SY),a
 call draw_strip
 jr frame_done
y_forward:
 push af
 ld a,1
 ld (DIRTY),a
 call wait_vblank
 call scroll_regs
 pop af
 ld (SY),a
 ld a,(BASEX)
 ld (SX),a
 ld a,32
 ld (COUNT),a
 ld a,1
 ld (AXIS),a
 push bc
 call release_strip
 pop bc
 ld a,b
 ld (BASEY),a
 add a,24
 ld (SY),a
 call draw_strip
frame_done:
 ld a,(DIRTY)
 or a
 call nz,wait_vblank
 call scroll_regs
 jp main_loop

wait_vblank:
 ; Discard a stale latched flag after a long cache upload, then wait for
 ; the NEXT VBlank edge. Register commits must never happen mid-display.
 in a,(0xbf)
wait_vblank_poll:
 in a,(0xbf)
 and 0x80
 jr z,wait_vblank_poll
 ret
pixel_to_tile:
 srl h
 rr l
 srl h
 rr l
 srl h
 rr l
 ld a,l
 ret
decrease:
 ld a,h
 or l
 ret z
 dec hl
 ld a,l
 and 7
 ret z
 dec hl
 ret
increase:
 inc hl
 ld a,l
 and 7
 jr z,increase_compare
 inc hl
increase_compare:
 or a
 sbc hl,de
 jr c,increase_restore
 ld h,d
 ld l,e
 ret
increase_restore:
 add hl,de
 ret
scroll_regs:
 ld a,(CAMX)
 neg
 add a,8
 out (0xbf),a
 ld a,0x88
 out (0xbf),a
 ld hl,(CAMY)
 ld de,224
scroll_y_mod:
 or a
 sbc hl,de
 jr nc,scroll_y_mod
 add hl,de
 ld a,l
 out (0xbf),a
 ld a,0x89
 out (0xbf),a
 ret

; Compute circular VRAM/ring pointers and ROM source pointer for a strip.
setup_strip:
 ld a,(COUNT)
 ld (REMAIN),a
 ld a,(SY)
 ld c,a
setup_mod_y:
 cp 28
 jr c,setup_mod_done
 sub 28
 jr setup_mod_y
setup_mod_done:
 ld l,a
 ld h,0
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 ld a,(SX)
 and 31
 add a,a
 ld e,a
 ld d,0
 add hl,de
 ld de,0x3800
 add hl,de
 ld (VPTR),hl
 ld de,0x8c00
 add hl,de
 ld (RPTR),hl
 ; Clamp halo tiles at the image's far right and bottom edges.
 ld a,(TW)
 dec a
 ld b,a
 ld a,(SX)
 cp b
 jr c,setup_x_ok
 ld a,b
setup_x_ok:
 ld (WX),a
 ld a,(TH)
 dec a
 ld b,a
 ld a,c
 cp b
 jr c,setup_y_ok
 ld a,b
setup_y_ok:
 ld (WY),a
 ld b,a
 ld hl,0x4000
 ld de,(STRIDE)
 or a
 jr z,setup_row_done
setup_rows:
 add hl,de
 djnz setup_rows
setup_row_done:
 ld a,(WX)
 ld e,a
 ld d,0
 add hl,de
 add hl,de
 add hl,de
 ld (MPTR),hl
 ret

; Advance one cell within the strip. Source clamps; destination wraps 32x28.
next_cell:
 ld a,(AXIS)
 or a
 jr z,next_column
 ld hl,(VPTR)
 inc hl
 inc hl
 ld a,l
 and 0x3f
 jr nz,next_row_vram_ok
 ld de,64
 or a
 sbc hl,de
next_row_vram_ok:
 ld (VPTR),hl
 ld de,0x8c00
 add hl,de
 ld (RPTR),hl
 ld a,(TW)
 dec a
 ld b,a
 ld a,(WX)
 cp b
 jr nc,next_count
 inc a
 ld (WX),a
 ld hl,(MPTR)
 inc hl
 inc hl
 inc hl
 ld (MPTR),hl
 jr next_count
next_column:
 ld hl,(VPTR)
 ld de,64
 add hl,de
 ld a,h
 cp 0x3f
 jr c,next_col_vram_ok
 ld hl,0x3800
 ld de,(VPTR)
 ld a,e
 and 0x3f
 ld l,a
next_col_vram_ok:
 ld (VPTR),hl
 ld de,0x8c00
 add hl,de
 ld (RPTR),hl
 ld a,(TH)
 dec a
 ld b,a
 ld a,(WY)
 cp b
 jr nc,next_count
 inc a
 ld (WY),a
 ld hl,(MPTR)
 ld de,(STRIDE)
 add hl,de
 ld (MPTR),hl
next_count:
 ld a,(REMAIN)
 dec a
 ld (REMAIN),a
 ret

release_strip:
 ld a,(STATIC)
 or a
 ret nz
 call setup_strip
release_cell:
 ld hl,(RPTR)
 ld e,(hl)
 inc hl
 ld d,(hl)
 ld a,d
 cp 0xff
 jr z,release_next
 ld (hl),0xff
 dec hl
 ld (hl),0xff
 ex de,hl
 add hl,hl
 ld de,REFS
 add hl,de
 ld e,(hl)
 inc hl
 ld d,(hl)
 dec de
 ld (hl),d
 dec hl
 ld (hl),e
release_next:
 call next_cell
 jr nz,release_cell
 ret

draw_strip:
 call setup_strip
draw_cell:
 ld hl,(MPTR)
 ld e,(hl)
 inc hl
 ld d,(hl)
 inc hl
 ld a,(hl)
 ld (FLAGS),a
 ld (TID),de
 ld a,(STATIC)
 or a
 jr nz,resident_slot
 call find_slot
 jr draw_slot
resident_slot:
 ex de,hl
draw_slot:
 ld (SLOT),hl
 ld a,(STATIC)
 or a
 jr nz,write_tilemap
 ; Add reference and store the cache slot in the RAM ring.
 push hl
 add hl,hl
 ld de,REFS
 add hl,de
 ld e,(hl)
 inc hl
 ld d,(hl)
 inc de
 ld (hl),d
 dec hl
 ld (hl),e
 pop de
 ld hl,(RPTR)
 ld (hl),e
 inc hl
 ld (hl),d
write_tilemap:
 ld hl,(VPTR)
 ld a,l
 out (0xbf),a
 ld a,h
 or 0x40
 out (0xbf),a
 ld hl,(SLOT)
 ld de,(TILEBASE)
 add hl,de
 ld a,l
 out (0xbe),a
 ld a,(FLAGS)
 or h
 out (0xbe),a
 call next_cell
 jp nz,draw_cell
 ret

; Reuse a cached global ID, otherwise overwrite an unreferenced pattern slot.
find_slot:
 ld hl,TAGS
 ld bc,0
find_tag:
 ld a,(hl)
 inc hl
 cp e
 jr nz,find_tag_skip
 ld a,(hl)
 cp d
 jr z,find_tag_hit
find_tag_skip:
 inc hl
 inc bc
 push hl
 ld hl,(NSLOTS)
 or a
 sbc hl,bc
 pop hl
 jr nz,find_tag
 ; No hit. Select an unreferenced slot.
 ld hl,REFS
 ld bc,0
find_free:
 ld a,(hl)
 inc hl
 or (hl)
 jr z,free_found
 inc hl
 inc bc
 jr find_free
free_found:
 ld h,b
 ld l,c
 ld (SLOT),hl
 add hl,hl
 ld de,TAGS
 add hl,de
 ld de,(TID)
 ld (hl),e
 inc hl
 ld (hl),d
 call upload_pattern
 ld hl,(SLOT)
 ret
find_tag_hit:
 ld h,b
 ld l,c
 ret
upload_pattern:
 ld hl,(SLOT)
 ld de,(TILEBASE)
 add hl,de
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 ld a,l
 out (0xbf),a
 ld a,h
 or 0x40
 out (0xbf),a
 ld hl,(TID)
 ld a,h
 srl a
 add a,2
 ld (0xffff),a
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 add hl,hl
 ld a,h
 and 0x3f
 or 0x80
 ld h,a
 ld bc,0x20be
 otir
 ret
registers:
 db 0x24,0x00,0x0e,0xff,0xff,0x7e,0x00,0x00,0x00,0x00,0xff
