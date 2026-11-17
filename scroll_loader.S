/* Minimal Sega Genesis scrollable ROM template, Motorola 68000.
 * Image graphics, palette attributes and scroll row commands are appended
 * and pointers patched at 0x1D0 by scroll_rom.py.
 * Directional pad pans the viewport in 8-pixel increments.
 */
        .section .text
        .org 0
        .long 0x00ffff00
        .long start
        .rept 62
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
start:
        move.w #0x2700,%sr
        move.b 0x00a10001,%d0
        andi.b #15,%d0
        beq 1f
        move.l #0x53454741,0x00a14000
1:
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
        move.w #0x9001,0x00c00004
        bra mode_done
h32_mode:
        move.w #0x8c00,0x00c00004
        move.w #0x9000,0x00c00004
mode_done:
        move.w #0x8d3e,0x00c00004
        move.w #0x8f02,0x00c00004
        move.w #0x9100,0x00c00004
        move.w #0x9200,0x00c00004
        /* Controller port 1 TH is an output. */
        move.b #0x40,0x00a10009
        move.b #0x40,0x00a10003
        /* Clear all 64 KiB of VRAM and VSRAM. */
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
        /* Copy 64 CRAM words (4 palettes). */
        movea.l 0x000001e0,%a0
        move.l #0xc0000000,0x00c00004
        move.w #63,%d0
copy_cram:
        move.w (%a0)+,0x00c00000
        dbra %d0,copy_cram
        /* Scroll position in tiles in work RAM. */
        clr.w 0x00ff0000
        clr.w 0x00ff0002
        bsr render_frame
mainloop:
        /* TH=1 reads UDLR on bits 0-3, all active low. */
        move.b 0x00a10003,%d0
        not.b %d0
        andi.w #0x000f,%d0
        beq mainloop
        btst #0,%d0
        bne key_up
        btst #1,%d0
        bne key_down
        btst #2,%d0
        bne key_left
        btst #3,%d0
        bne key_right
        bra mainloop
key_up:
        move.w 0x00ff0002,%d1
        beq mainloop
        subq.w #1,%d1
        move.w %d1,0x00ff0002
        moveq #0,%d7
        bra moved
key_down:
        move.w 0x00ff0002,%d1
        move.w 0x000001d2,%d2
        sub.w #28,%d2
        cmp.w %d2,%d1
        bhs mainloop
        addq.w #1,%d1
        move.w %d1,0x00ff0002
        moveq #1,%d7
        bra moved
key_left:
        move.w 0x00ff0000,%d1
        beq mainloop
        subq.w #1,%d1
        move.w %d1,0x00ff0000
        moveq #2,%d7
        bra moved
key_right:
        move.w 0x00ff0000,%d1
        move.w 0x000001d0,%d2
        sub.w 0x000001d4,%d2
        cmp.w %d2,%d1
        bhs mainloop
        addq.w #1,%d1
        move.w %d1,0x00ff0000
        moveq #3,%d7
moved:
        bsr update_visible_stripe
        /* Modest key repeat delay; ROM is intentionally a simple viewer. */
        move.w #0xffff,%d0
delay:
        dbra %d0,delay
        bra mainloop

/* Redraw whole viewport into VRAM with screen blanked. Tiles are stored in
 * source-image raster order in ROM. A screen position maps to exactly one
 * pattern slot 1..1120 (H40) or 1..896 (H32). No lossy tile merging.
 */
render_frame:
        move.w #0x8104,0x00c00004
        /* Compute start source tile index = scrollY * imageTW + scrollX. */
        moveq #0,%d0
        move.w 0x00ff0002,%d0
        mulu.w 0x000001d0,%d0
        add.w 0x00ff0000,%d0
        /* Pattern pointer offset = startTile * 32. */
        move.l %d0,%d1
        lsl.l #5,%d1
        movea.l 0x000001d8,%a0
        adda.l %d1,%a0
        /* Pitch between viewport tile rows, in bytes. */
        move.w 0x000001d0,%d6
        sub.w 0x000001d4,%d6
        lsl.w #5,%d6
        /* Words in one screen row, minus one. */
        move.w 0x000001d4,%d5
        lsl.w #4,%d5
        subq.w #1,%d5
        move.w #27,%d3
        move.l #0x40200000,0x00c00004
tile_row:
        move.w %d5,%d0
tile_words:
        move.w (%a0)+,0x00c00000
        dbra %d0,tile_words
        adda.w %d6,%a0
        dbra %d3,tile_row

        bsr paint_map
        move.w #0x8144,0x00c00004
        rts

/* When moving just one 8px tile, only upload the entering row/column.
 * Use a 40x28/32x28 ring of VRAM pattern slots. The display remains ON
 * while scrolling: no black frames and much less transferred data.
 */
update_visible_stripe:
        /* Wait for start of vertical blanking, then upload the new strip. */
wait_active:
        move.w 0x00c00004,%d2
        btst #3,%d2
        bne wait_active
wait_blank:
        move.w 0x00c00004,%d2
        btst #3,%d2
        beq wait_blank
        cmpi.w #2,%d7
        bhs change_horizontal
        /* Up / down: upload one entering row across screen width. */
        move.w 0x00ff0002,%d1
        tst.w %d7
        beq vertical_ready
        add.w #27,%d1
vertical_ready:
        move.w 0x00ff0000,%d0
        move.w 0x000001d4,%d7
        subq.w #1,%d7
vertical_loop:
        bsr upload_tile
        addq.w #1,%d0
        dbra %d7,vertical_loop
        bra stripe_done
change_horizontal:
        /* Left / right: upload one entering column across 28 rows. */
        move.w 0x00ff0000,%d0
        cmpi.w #3,%d7
        bne horizontal_ready
        add.w 0x000001d4,%d0
        subq.w #1,%d0
horizontal_ready:
        move.w 0x00ff0002,%d1
        move.w #27,%d7
horizontal_loop:
        bsr upload_tile
        addq.w #1,%d1
        dbra %d7,horizontal_loop
stripe_done:
        bsr paint_map
        rts

/* Upload a single 8x8 tile to circular VRAM pattern slot.
 * Input D0=source tile X, D1=source tile Y. Preserve D0,D1,D7.
 */
upload_tile:
        moveq #0,%d2
        move.w %d1,%d2
        mulu.w 0x000001d0,%d2
        add.w %d0,%d2
        lsl.l #5,%d2
        movea.l 0x000001d8,%a0
        adda.l %d2,%a0
        /* VDP pattern index = 1 + (y mod 28)*screenTW + (x mod screenTW). */
        moveq #0,%d3
        move.w %d1,%d3
        divu.w #28,%d3
        swap %d3
        andi.l #0x0000ffff,%d3
        mulu.w 0x000001d4,%d3
        moveq #0,%d4
        move.w %d0,%d4
        divu.w 0x000001d4,%d4
        swap %d4
        andi.l #0x0000ffff,%d4
        add.l %d4,%d3
        addq.l #1,%d3
        lsl.l #5,%d3
        /* Encode VRAM write command from byte address D3. */
        move.l %d3,%d4
        andi.l #0x00003fff,%d4
        swap %d4
        move.l %d3,%d5
        lsr.l #14,%d5
        andi.l #3,%d5
        or.l %d5,%d4
        ori.l #0x40000000,%d4
        move.l %d4,0x00c00004
        move.w #15,%d6
single_tile_words:
        move.w (%a0)+,0x00c00000
        dbra %d6,single_tile_words
        rts

/* Redraw only name-table references, not the 35 KB pattern buffer.
 * Each destination screen tile points at its source coordinate's ring
 * buffer slot and keeps its source CRAM palette selection.
 */
paint_map:
        moveq #0,%d0
        move.w 0x00ff0002,%d0
        mulu.w 0x000001d0,%d0
        add.w 0x00ff0000,%d0
        add.l %d0,%d0
        movea.l 0x000001dc,%a1
        adda.l %d0,%a1
        movea.l 0x000001e4,%a2
        move.w 0x000001d0,%d6
        sub.w 0x000001d4,%d6
        add.w %d6,%d6
        move.w 0x000001d4,%d5
        subq.w #1,%d5
        move.w #27,%d3
        /* Ring row and ring x origin, both reduced modulo dimensions. */
        moveq #0,%d7
        move.w 0x00ff0002,%d7
        divu.w #28,%d7
        swap %d7
        andi.l #0x0000ffff,%d7
        moveq #0,%d2
        move.w 0x00ff0000,%d2
        divu.w 0x000001d4,%d2
        swap %d2
        move.w %d2,0x00ff0004
map_ring_row:
        move.l (%a2)+,0x00c00004
        move.w %d7,%d1
        mulu.w 0x000001d4,%d1
        addq.w #1,%d1
        move.w 0x00ff0004,%d2
        move.w %d5,%d0
map_ring_col:
        move.w (%a1)+,%d4
        add.w %d1,%d4
        add.w %d2,%d4
        move.w %d4,0x00c00000
        addq.w #1,%d2
        cmp.w 0x000001d4,%d2
        blo map_no_x_wrap
        clr.w %d2
map_no_x_wrap:
        dbra %d0,map_ring_col
        adda.w %d6,%a1
        addq.w #1,%d7
        cmpi.w #28,%d7
        blo map_no_y_wrap
        clr.w %d7
map_no_y_wrap:
        dbra %d3,map_ring_row
        rts
hang:
        bra hang
