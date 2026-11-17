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
        .ascii "(C) AMINO 2026.NOV"
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
        bra moved
key_down:
        move.w 0x00ff0002,%d1
        move.w 0x000001d2,%d2
        sub.w #28,%d2
        cmp.w %d2,%d1
        bhs mainloop
        addq.w #1,%d1
        move.w %d1,0x00ff0002
        bra moved
key_left:
        move.w 0x00ff0000,%d1
        beq mainloop
        subq.w #1,%d1
        move.w %d1,0x00ff0000
        bra moved
key_right:
        move.w 0x00ff0000,%d1
        move.w 0x000001d0,%d2
        sub.w 0x000001d4,%d2
        cmp.w %d2,%d1
        bhs mainloop
        addq.w #1,%d1
        move.w %d1,0x00ff0000
moved:
        bsr render_frame
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

        /* Name table attributes already contain CRAM selection bits;
         * hardware tile index is viewport position + 1, no flip bits.
         */
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
        moveq #1,%d4
map_row:
        move.l (%a2)+,0x00c00004
        move.w %d5,%d0
map_col:
        move.w (%a1)+,%d1
        or.w %d4,%d1
        move.w %d1,0x00c00000
        addq.w #1,%d4
        dbra %d0,map_col
        adda.w %d6,%a1
        dbra %d3,map_row
        move.w #0x8144,0x00c00004
        rts
hang:
        bra hang
