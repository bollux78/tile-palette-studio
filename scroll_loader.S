/* Minimal Sega Genesis scrollable ROM template, Motorola 68000.
 * Image graphics, palette attributes and scroll row commands are appended
 * and pointers patched at 0x1D0 by scroll_rom.py.
 * Directional pad pans the viewport in 8-pixel increments.
 */
        .section .text
        .org 0
        .long 0x00ffff00
        .long start
        .rept 28
        .long hang
        .endr
        .long vblank_irq
        .rept 33
        .long hang
        .endr
        .org 0x100
        .ascii "SEGA MEGA DRIVE "
        .org 0x110
        .ascii "(C) AMINO 2026"
        .org 0x120
        .ascii "TILE PALETTE STUDIO SCROLL ROM"
        .org 0x150
        .ascii "TILE PALETTE STUDIO SCROLL ROM"
        .org 0x180
        .ascii "GM 00000000-00"
        .org 0x18e
        .word 0
        .org 0x1a0
        .long 0
        .long 0x0001ffff
        .long 0x00ff0000
        .long 0x00ffffff
        .org 0x1d0
image_tw: .word 0
image_th: .word 0
screen_tw: .word 0
screen_th: .word 28
tiles_ptr: .long 0
attrs_ptr: .long 0
cram_ptr:  .long 0
commands_ptr: .long 0
        .org 0x1f0
        .ascii "JUE"

        .org 0x200
/* Hardware scrolling viewer: VDP HScroll table + VSRAM.
 * A circular tile cache is 46x32 (H40) / 38x32 (H32).
 * Plane A is always 64x32, and new 8x8 tiles are uploaded only
 * when the camera crosses a tile boundary. Scroll steps are 2 px.
 */
start:
        move.w #0x2700,%sr
        move.b 0x00a10001,%d0
        andi.b #15,%d0
        beq tmss_done
        move.l #0x53454741,0x00a14000
tmss_done:
        move.w #0x8004,0x00c00004
        move.w #0x8104,0x00c00004
        move.w #0x8230,0x00c00004
        move.w #0x8334,0x00c00004
        move.w #0x8407,0x00c00004
        move.w #0x8578,0x00c00004
        move.w #0x8700,0x00c00004
        move.w #0x8a00,0x00c00004
        move.w #0x8b00,0x00c00004
        cmpi.w #40,0x000001d4
        bne h32_mode
        move.w #0x8c81,0x00c00004
        bra mode_ready
h32_mode:
        move.w #0x8c00,0x00c00004
mode_ready:
        move.w #0x8d3e,0x00c00004
        move.w #0x8f02,0x00c00004
        move.w #0x9001,0x00c00004  /* 64x32 plane in both modes */
        move.w #0x9100,0x00c00004
        move.w #0x9200,0x00c00004
        move.b #0x40,0x00a10009
        move.b #0x40,0x00a10003
        /* Clear VRAM, including plane B, SAT, and H-scroll table. */
        move.l #0x40000000,0x00c00004
        move.w #32767,%d0
clear_vram:
        move.w #0,0x00c00000
        dbra %d0,clear_vram
        move.l #0x40000010,0x00c00004
        move.w #39,%d0
clear_vsram:
        move.w #0,0x00c00000
        dbra %d0,clear_vsram
        movea.l 0x000001e0,%a0
        move.l #0xc0000000,0x00c00004
        move.w #63,%d0
load_cram:
        move.w (%a0)+,0x00c00000
        dbra %d0,load_cram
        clr.w 0x00ff0000          /* camera x in pixels */
        clr.w 0x00ff0002          /* camera y in pixels */

        /* Preload a halo on the initial top/left boundary:
         * screenTW+6 columns and all 32 name-table rows. 32 rows is
         * crucial: loading row 32 now would overwrite visible row 0. */
        clr.w %d1
        move.w #31,%d7
preload_row:
        clr.w %d0
        move.w 0x000001d4,%d6
        addq.w #6,%d6
        subq.w #1,%d6
preload_col:
        bsr upload_tile_with_map
        addq.w #1,%d0
        dbra %d6,preload_col
        addq.w #1,%d1
        dbra %d7,preload_row
        bsr apply_hardware_scroll
        /* Enable VBlank IRQ after graphics initialization for X7 menu. */
        move.w #0x8164,0x00c00004
        move.w #0x2000,%sr

mainloop:
        bsr wait_vblank_start
        move.b 0x00a10003,%d0
        not.b %d0
        andi.w #0x000f,%d0
        beq mainloop
        btst #0,%d0
        bne go_up
        btst #1,%d0
        bne go_down
        btst #2,%d0
        bne go_left
        btst #3,%d0
        bne go_right
        bra mainloop

go_right:
        move.w 0x000001d0,%d1
        sub.w 0x000001d4,%d1
        lsl.w #3,%d1
        move.w 0x00ff0000,%d2
        cmp.w %d1,%d2
        bhs mainloop
        addq.w #2,%d2
        move.w %d2,0x00ff0000
        andi.w #7,%d2
        bne apply_camera
        /* 46-column halo holds 2 spare columns behind the camera.
         * At tile 3, add column tileX+screenTW+3 (outside viewport). */
        move.w 0x00ff0000,%d0
        cmpi.w #24,%d0
        blo apply_camera
        lsr.w #3,%d0
        add.w 0x000001d4,%d0
        addq.w #3,%d0
        move.w 0x00ff0002,%d1
        lsr.w #3,%d1
        bsr apply_hardware_scroll
        bsr upload_new_col
        bra mainloop

go_left:
        move.w 0x00ff0000,%d2
        beq mainloop
        subq.w #2,%d2
        move.w %d2,0x00ff0000
        andi.w #7,%d2
        cmpi.w #6,%d2
        bne apply_camera
        /* Reload tileX-2 into the left halo before it becomes visible,
         * including rows loaded later by vertical movement. */
        move.w 0x00ff0000,%d0
        cmpi.w #16,%d0
        blo apply_camera
        lsr.w #3,%d0
        subq.w #2,%d0
        move.w 0x00ff0002,%d1
        lsr.w #3,%d1
        bsr apply_hardware_scroll
        bsr upload_new_col
        bra mainloop

go_down:
        move.w 0x000001d2,%d1
        sub.w #28,%d1
        lsl.w #3,%d1
        move.w 0x00ff0002,%d2
        cmp.w %d1,%d2
        bhs mainloop
        addq.w #2,%d2
        move.w %d2,0x00ff0002
        andi.w #7,%d2
        bne apply_camera
        move.w 0x00ff0002,%d1
        cmpi.w #24,%d1
        blo apply_camera
        lsr.w #3,%d1
        add.w #29,%d1
        move.w 0x00ff0000,%d0
        lsr.w #3,%d0
        bsr apply_hardware_scroll
        bsr upload_new_row
        bra mainloop

go_up:
        move.w 0x00ff0002,%d2
        beq mainloop
        subq.w #2,%d2
        move.w %d2,0x00ff0002
        andi.w #7,%d2
        cmpi.w #6,%d2
        bne apply_camera
        /* Refill tileY-2 in the upper halo before it becomes visible. */
        move.w 0x00ff0002,%d1
        cmpi.w #16,%d1
        blo apply_camera
        lsr.w #3,%d1
        subq.w #2,%d1
        move.w 0x00ff0000,%d0
        lsr.w #3,%d0
        bsr apply_hardware_scroll
        bsr upload_new_row
        bra mainloop

upload_new_col:
        /* Include 2 rows above the current camera after changing axes.
         * At the top edge, clamp to 0 (never unsigned-wrap). */
        cmpi.w #2,%d1
        blo col_top
        subq.w #2,%d1
        bra col_start
col_top:
        clr.w %d1
col_start:
        move.w #31,%d7
col_loop:
        bsr upload_tile_with_map
        addq.w #1,%d1
        dbra %d7,col_loop
        rts

upload_new_row:
        /* Include 2 columns to the left, including when x/y
         * movement happens in either order. */
        cmpi.w #2,%d0
        blo row_left
        subq.w #2,%d0
        bra row_start
row_left:
        clr.w %d0
row_start:
        move.w 0x000001d4,%d7
        addq.w #6,%d7
        subq.w #1,%d7
row_loop:
        bsr upload_tile_with_map
        addq.w #1,%d0
        dbra %d7,row_loop
        rts

apply_camera:
        bsr apply_hardware_scroll
        bra mainloop

wait_vblank_start:
vb_active:
        move.w 0x00c00004,%d6
        btst #3,%d6
        bne vb_active
vb_wait:
        move.w 0x00c00004,%d6
        btst #3,%d6
        beq vb_wait
        rts

apply_hardware_scroll:
        /* VRAM $F800: HScroll plane A, plane B. */
        move.l #0x78000003,0x00c00004
        move.w 0x00ff0000,%d6
        neg.w %d6
        move.w %d6,0x00c00000
        move.w #0,0x00c00000
        /* VSRAM: VScroll plane A, plane B. */
        move.l #0x40000010,0x00c00004
        move.w 0x00ff0002,%d6
        /* Genesis VScroll sign is opposite to HScroll:
         * positive VScroll shifts the plane UP as camera Y increases. */
        move.w %d6,0x00c00000
        move.w #0,0x00c00000
        rts

/* Input: D0 = source tile x, D1 = source tile y.
 * Uses source ROM pixel tiles and tile attributes. A physical tile in
 * VRAM has cache coordinates x%(screenTW+6), y%32; the name table
 * position is x%64,y%32. Tile 0 is always kept black/blank.
 */
upload_tile_with_map:
        movem.l %d2-%d6/%a0-%a1,-(%sp)
        moveq #0,%d6
        cmp.w 0x000001d0,%d0
        bhs empty_tile
        cmp.w 0x000001d2,%d1
        bhs empty_tile
        moveq #0,%d2
        move.w %d1,%d2
        mulu.w 0x000001d0,%d2
        add.w %d0,%d2
        move.l %d2,%d3
        lsl.l #5,%d3
        movea.l 0x000001d8,%a0
        adda.l %d3,%a0
        add.l %d2,%d2
        movea.l 0x000001dc,%a1
        adda.l %d2,%a1
        move.w (%a1),%d6
        andi.w #0xe000,%d6
        /* Pattern cache ring coordinates. */
        moveq #0,%d2
        move.w %d1,%d2
        andi.l #31,%d2
        move.w 0x000001d4,%d5
        addq.w #6,%d5
        mulu.w %d5,%d2
        moveq #0,%d3
        move.w %d0,%d3
        divu.w %d5,%d3
        swap %d3
        andi.l #0x0000ffff,%d3
        add.w %d3,%d2
        addq.w #1,%d2
        /* Pattern VRAM address = tile index * 32. */
        move.l %d2,%d3
        lsl.l #5,%d3
        bsr issue_vram_write
        move.w #15,%d5
upload_words:
        move.w (%a0)+,0x00c00000
        dbra %d5,upload_words
        bra upload_map
empty_tile:
        moveq #0,%d2
upload_map:
        /* Plane A 64x32, each entry is a 2-byte tile attribute. */
        moveq #0,%d3
        move.w %d1,%d3
        andi.l #31,%d3
        lsl.l #7,%d3
        moveq #0,%d4
        move.w %d0,%d4
        andi.w #63,%d4
        add.w %d4,%d4
        add.l %d4,%d3
        addi.l #0x0000c000,%d3
        bsr issue_vram_write
        or.w %d2,%d6
        move.w %d6,0x00c00000
        movem.l (%sp)+,%d2-%d6/%a0-%a1
        rts

/* Encode VDP VRAM write command from D3 byte address. */
issue_vram_write:
        move.l %d3,%d4
        andi.l #0x00003fff,%d4
        swap %d4
        move.l %d3,%d5
        lsr.l #8,%d5
        lsr.l #6,%d5
        andi.l #3,%d5
        or.l %d5,%d4
        ori.l #0x40000000,%d4
        move.l %d4,0x00c00004
        rts
vblank_irq:
        move.l %d0,-(%sp)
        /* 3-button controller polling: TH low exposes START,
         * TH high exposes the D-pad. Both bus reads occur every
         * VBlank so an X7 can see Down+Start just as with a game. */
        move.b #0x00,0x00a10003
        nop
        nop
        move.b 0x00a10003,%d0
        move.b #0x40,0x00a10003
        nop
        nop
        move.b 0x00a10003,%d0
        move.w 0x00c00004,%d0
        move.l (%sp)+,%d0
        rte

hang:
        bra hang
