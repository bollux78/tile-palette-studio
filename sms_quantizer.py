"""Tile Palette Studio — native per-tile Master System palette optimizer.

Clean-room NumPy implementation inspired by tiledpalettequant's *task*, not a
Python translation of its algorithm. The original project is MIT licensed.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw


@dataclass
class Settings:
    palettes: int = 2
    colors: int = 16
    tile_size: int = 8
    iterations: int = 10
    dither: str = "off"  # off or six Rilden patterns
    dither_strength: float = 0.35
    transparent: bool = False
    alpha_threshold: int = 128
    background: str = "#000000"
    base_tile: int = 0
    seed: int = 42
    vram_budget_tiles: int = 448  # User-configurable estimate; actual VRAM usage is game-specific
    allow_lossy_tiles: bool = False


@dataclass
class Result:
    preview: Image.Image
    palettes_rgb: np.ndarray       # (P,C,3) RGB in 0,85,170,255
    tile_palettes: np.ndarray      # (tile_rows,tile_cols)
    indices: np.ndarray            # padded H,W of palette-local 4bpp indices
    settings: Settings
    source_size: tuple[int, int]
    padded_size: tuple[int, int]
    history: list[float]
    mean_squared_error: float
    transparent_pixels: int


_RGB_CODES = np.arange(64, dtype=np.uint16)
_RGB3 = np.stack(((_RGB_CODES >> 4) & 3, (_RGB_CODES >> 2) & 3, _RGB_CODES & 3), axis=-1).astype(np.float32)
_WEIGHT = np.array([1.0, 1.28, 0.72], dtype=np.float32)
_BAYER2 = np.array([[0, 2], [3, 1]], dtype=np.float32)
_BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32)
_BAYER8 = np.kron(_BAYER4, np.ones((2, 2), np.float32)) * 4 + np.tile(_BAYER2, (4, 4))
# Exact 2x2 ordering matrices from rilden/tiledpalettequant worker.js (MIT).
_RILDEN_PATTERNS = {
    'diagonal4': np.array([[0, 2], [3, 1]], dtype=np.uint8),
    'horizontal4': np.array([[0, 3], [1, 2]], dtype=np.uint8),
    'vertical4': np.array([[0, 1], [3, 2]], dtype=np.uint8),
    'diagonal2': np.array([[0, 1], [1, 0]], dtype=np.uint8),
    'horizontal2': np.array([[0, 1], [0, 1]], dtype=np.uint8),
    'vertical2': np.array([[0, 0], [1, 1]], dtype=np.uint8),
}
# Matrices above are indexed [x,y], as in rilden/tiledpalettequant worker.js (MIT).



def _rgb_from_hex(color: str) -> np.ndarray:
    color = color.lstrip('#')
    if len(color) != 6:
        raise ValueError('A cor deve estar em hexadecimal #RRGGBB')
    return np.array([int(color[k:k+2], 16) for k in (0, 2, 4)], dtype=np.uint8)


def _distance(codes: np.ndarray, colors: np.ndarray) -> np.ndarray:
    """CIE-inspired weighted RGB distances in 2-bit channel space."""
    a = codes.astype(np.float32)
    b = colors.astype(np.float32)
    return np.sum((a[:, None, :] - b[None, :, :]) ** 2 * _WEIGHT, axis=2)


def _seed_groups(features: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    count = len(features)
    if count == 1 or k == 1:
        return np.zeros(count, dtype=np.int16)
    k = min(k, count)
    centers = np.empty((k, features.shape[1]), dtype=np.float32)
    centers[0] = features[int(rng.integers(count))]
    dist = np.sum((features - centers[0]) ** 2, axis=1)
    for j in range(1, k):
        if float(dist.sum()) <= 0:
            centers[j] = features[int(rng.integers(count))]
        else:
            centers[j] = features[int(rng.choice(count, p=dist / dist.sum()))]
        dist = np.minimum(dist, np.sum((features - centers[j]) ** 2, axis=1))
    labels = np.zeros(count, dtype=np.int16)
    for _ in range(22):
        distances = np.sum((features[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        labels_new = np.argmin(distances, axis=1).astype(np.int16)
        if np.array_equal(labels, labels_new) and _ > 0:
            break
        labels = labels_new
        for p in range(k):
            subset = features[labels == p]
            if len(subset):
                centers[p] = subset.mean(axis=0)
            else:
                centers[p] = features[int(np.argmax(np.min(distances, axis=1)))]
    return labels


def _fit_palette(hist: np.ndarray, num_colors: int, zero: np.ndarray,
                 rng: np.random.Generator, zero_reserved: bool) -> np.ndarray:
    codes = np.flatnonzero(hist)
    out = np.zeros((num_colors, 3), dtype=np.float32)
    out[0] = zero
    if not len(codes):
        return out.astype(np.uint8)
    weights = hist[codes].astype(np.float64)
    colors = _RGB3[codes]
    slots = num_colors - 1 if zero_reserved else num_colors
    if slots <= 0:
        return out.astype(np.uint8)
    # Preserve palette entry 0 as common background/transparent, and fit all
    # remaining slots to actual colors. Weighted k-means++ + Lloyd refinement.
    centers = np.empty((slots, 3), np.float32)
    centers[0] = colors[int(rng.choice(len(codes), p=weights / weights.sum()))]
    best_dist = _distance(colors, centers[:1])[:, 0].astype(np.float64)
    for j in range(1, slots):
        prob = weights * np.maximum(best_dist, 0)
        if float(prob.sum()) < 1e-12:
            centers[j] = colors[int(rng.choice(len(codes), p=weights / weights.sum()))]
        else:
            centers[j] = colors[int(rng.choice(len(codes), p=prob/prob.sum()))]
        best_dist = np.minimum(best_dist, _distance(colors, centers[j:j+1])[:, 0])
    for _ in range(15):
        dist = _distance(colors, centers)
        labels = np.argmin(dist, axis=1)
        changed = False
        for j in range(slots):
            m = labels == j
            if np.any(m):
                center = np.average(colors[m], axis=0, weights=weights[m])
                if np.max(np.abs(center - centers[j])) > 0.04:
                    changed = True
                centers[j] = center
            else:
                err = weights * np.min(dist, axis=1)
                centers[j] = colors[int(np.argmax(err))]
                changed = True
        if not changed:
            break
    picks = np.rint(centers).clip(0, 3).astype(np.uint8)
    # Repair quantization duplicates with the colors carrying the most error.
    used: set[tuple[int, int, int]] = {tuple(map(int, zero))} if zero_reserved else set()
    for j in range(slots):
        key = tuple(map(int, picks[j]))
        if key in used:
            occupied = np.asarray(list(used), dtype=np.float32) if used else np.zeros((1, 3), np.float32)
            residual = _distance(colors, occupied).min(axis=1) * weights
            for c in np.argsort(-residual):
                key = tuple(map(int, colors[int(c)]))
                if key not in used:
                    picks[j] = colors[int(c)].astype(np.uint8)
                    break
        used.add(tuple(map(int, picks[j])))
    out[1 if zero_reserved else 0:] = picks
    return out.astype(np.uint8)


def vram_usage(width, height, base_tile=0, budget_tiles=448):
    count=((width+7)//8)*((height+7)//8)
    return {'tiles':count,'tile_bytes':count*32,'vram_bytes':16384,
            'budget_tiles':budget_tiles,'base_tile':base_tile,
            'fits_vdp':base_tile+count<=448,'over_budget':count>budget_tiles}


def _floyd_steinberg(rgb: np.ndarray, valid: np.ndarray, pix_palette: np.ndarray,
                     palettes: np.ndarray, transparent: bool, strength: float,
                     indices: np.ndarray, preview_arr: np.ndarray) -> None:
    """Serpentine Floyd–Steinberg in RGB, constrained to each tile's palette.

    Error only crosses into an opaque pixel using the same palette. Keeps
    tile/transparent boundaries from contaminating unrelated colors.
    """
    h, w = valid.shape
    pal = (palettes.astype(np.float32) * 85.0).tolist()
    start = 1 if transparent else 0
    curr = np.zeros((w+2, 3), dtype=np.float32)
    nxt = np.zeros_like(curr)
    for y in range(h):
        forward = y % 2 == 0
        xiter = range(w) if forward else range(w-1, -1, -1)
        for x in xiter:
            if not valid[y, x]:
                continue
            pid = int(pix_palette[y, x]); colors = pal[pid]
            old = rgb[y, x]
            rr = min(255.0, max(0.0, float(old[0]) + float(curr[x+1, 0])))
            gg = min(255.0, max(0.0, float(old[1]) + float(curr[x+1, 1])))
            bb = min(255.0, max(0.0, float(old[2]) + float(curr[x+1, 2])))
            best = start; mind = float('inf')
            for j in range(start, len(colors)):
                c = colors[j]
                dr, dg, db = rr-c[0], gg-c[1], bb-c[2]
                d = dr*dr + 1.28*dg*dg + .72*db*db
                if d < mind:
                    mind = d; best = j
            indices[y, x] = best
            col = colors[best]
            preview_arr[y, x, :3] = col
            if strength <= 0:
                continue
            er = (rr-col[0])*strength
            eg = (gg-col[1])*strength
            eb = (bb-col[2])*strength
            direction = 1 if forward else -1
            nx = x + direction
            if 0 <= nx < w and valid[y, nx] and pix_palette[y, nx] == pid:
                curr[nx+1, 0] += er*7/16
                curr[nx+1, 1] += eg*7/16
                curr[nx+1, 2] += eb*7/16
            if y+1 < h:
                for dx, weight in ((-direction, 3/16), (0, 5/16), (direction, 1/16)):
                    xx = x + dx
                    if 0 <= xx < w and valid[y+1, xx] and pix_palette[y+1, xx] == pid:
                        nxt[xx+1, 0] += er*weight
                        nxt[xx+1, 1] += eg*weight
                        nxt[xx+1, 2] += eb*weight
        curr, nxt = nxt, curr
        nxt.fill(0)


def quantize(image: Image.Image, config: Settings,
             on_progress: Callable[[int, str], None] | None = None) -> Result:
    if not 0 <= config.base_tile <= 447:
        raise ValueError('Índice inicial VDP deve estar entre 0 e 447')
    if not 1 <= config.vram_budget_tiles <= 448:
        raise ValueError('Orçamento VRAM deve ser de 1 a 448 tiles')
    if not 1 <= config.palettes <= 2:
        raise ValueError('Master System oferece até 2 paletas simultâneas')
    if not 2 <= config.colors <= 16:
        raise ValueError('Até 16 cores por paleta no Master System')
    if config.tile_size != 8:
        raise ValueError('Os tiles do Master System têm 8x8 pixels')
    if not 1 <= config.iterations <= 40:
        raise ValueError('Iterações: 1 a 40')
    if not 0 <= config.dither_strength <= 1:
        raise ValueError('Dithering: intensidade de 0 a 1')
    if config.dither not in ('off', 'diagonal4', 'horizontal4', 'vertical4', 'diagonal2', 'horizontal2', 'vertical2', 'floyd'):
        raise ValueError('Padrão de dithering inválido')

    def update(percent: int, msg: str):
        if on_progress:
            on_progress(percent, msg)

    original = image.convert('RGBA')
    width, height = original.size
    if width <= 0 or height <= 0:
        raise ValueError('Imagem inválida')
    if width * height > 16_000_000:
        raise ValueError('Limite de 16 megapixels nesta versão')
    pw = (width + 7) & ~7
    ph = (height + 7) & ~7
    raw = np.asarray(original, dtype=np.uint8)
    rgb = np.zeros((ph, pw, 3), np.uint8)
    alpha = np.zeros((ph, pw), np.uint8)
    rgb[:height, :width] = raw[..., :3]
    alpha[:height, :width] = raw[..., 3]
    valid = np.zeros((ph, pw), np.bool_)
    valid[:height, :width] = True
    if config.transparent:
        valid[:height, :width] &= alpha[:height, :width] >= config.alpha_threshold
    zero_rgb = _rgb_from_hex(config.background)
    zero = np.clip(np.rint(zero_rgb.astype(np.float32) / 85), 0, 3).astype(np.uint8)

    update(5, 'Preparando histograma por tile…')
    q3 = np.clip(np.rint(rgb.astype(np.float32) / 85), 0, 3).astype(np.uint16)
    codes = (q3[:, :, 0] << 4) | (q3[:, :, 1] << 2) | q3[:, :, 2]
    tw, th = pw // 8, ph // 8
    tile_ids = np.repeat(np.arange(th) * tw, 8)[:, None] + np.repeat(np.arange(tw), 8)[None, :]
    tile_ids = np.broadcast_to(tile_ids, (ph, pw))
    hist = np.zeros((tw * th, 64), np.float32)
    np.add.at(hist, (tile_ids[valid], codes[valid]), 1)
    active = hist.sum(axis=1)
    # Compact 4x4x4 RGB bins (histogram shape of each tile) initializes tile grouping.
    coarse = np.zeros((tw * th, 64), np.float32)
    coarse_id = _RGB_CODES.astype(np.intp)
    for c in range(64):
        coarse[:, coarse_id[c]] += hist[:, c]
    coarse /= np.maximum(active[:, None], 1)
    coarse = np.sqrt(coarse, out=coarse)
    seed = np.random.default_rng(config.seed)
    assignments = _seed_groups(coarse, config.palettes, seed)
    zero_reserved = config.transparent  # Background color 0 is opaque in SMS Mode 4.
    history: list[float] = []
    palettes = np.zeros((config.palettes, config.colors, 3), dtype=np.uint8)
    update(14, 'Otimizando paletas compartilhadas entre tiles…')
    all_colors = _RGB3
    for iteration in range(config.iterations):
        for p in range(config.palettes):
            h = hist[assignments == p].sum(axis=0)
            if not h.any():
                h = hist.sum(axis=0)
            palettes[p] = _fit_palette(h, config.colors, zero, seed, zero_reserved)
        costs = np.empty((64, config.palettes), np.float32)
        for p in range(config.palettes):
            costs[:, p] = _distance(all_colors, palettes[p, 1 if zero_reserved else 0:]).min(axis=1)
        tile_err = hist @ costs
        # Avoid arbitrary thrash of identical tiles by stable argmin.
        new_assignments = np.argmin(tile_err, axis=1).astype(np.int16)
        total_error = float(np.sum(np.min(tile_err, axis=1)) / max(1, active.sum()))
        history.append(total_error)
        update(15 + int(65 * (iteration+1) / config.iterations),
               f'Iteração {iteration+1}/{config.iterations} · erro {total_error:.3f}')
        if np.array_equal(new_assignments, assignments):
            break
        assignments = new_assignments
    # Refit once after last assignment, otherwise palette colors may correspond
    # to the penultimate assignment rather than the final one.
    for p in range(config.palettes):
        h = hist[assignments == p].sum(axis=0)
        if not h.any():
            h = hist.sum(axis=0)
        palettes[p] = _fit_palette(h, config.colors, zero, seed, zero_reserved)
    update(85, 'Aplicando cores finais e dithering…')
    pix_palette = assignments[tile_ids]
    rgbfloat = rgb.astype(np.float32)
    pattern = _RILDEN_PATTERNS.get(config.dither)
    indices = np.zeros((ph, pw), np.uint8)
    preview_arr = np.zeros((ph, pw, 4), np.uint8)
    preview_arr[..., 3] = 255
    if config.transparent:
        preview_arr[~valid, 3] = 0
    if config.dither == 'floyd':
        _floyd_steinberg(rgbfloat, valid, pix_palette, palettes,
                         config.transparent, config.dither_strength,
                         indices, preview_arr)
    else:
        for p in range(config.palettes):
            mask = valid & (pix_palette == p)
            coords = np.flatnonzero(mask)
            if not len(coords):
                continue
            colors = np.rint(palettes[p].astype(np.float32) * 85).astype(np.uint8)
            src_flat = rgbfloat.reshape(-1, 3)
            ind_flat = indices.reshape(-1)
            dst_flat = preview_arr.reshape(-1, 4)
            for ch in np.array_split(coords, max(1, (len(coords)+4095)//4096)):
                original = src_flat[ch]
                if pattern is None or config.dither_strength <= 0:
                    dif = original[:, None, :] - colors[None, :, :].astype(np.float32)
                    dist = np.sum(dif*dif*np.array([2,4,1],np.float32),axis=2)
                    if zero_reserved: dist[:,0] = np.inf
                    chosen = np.argmin(dist,axis=1).astype(np.uint8)
                else:
                    # Rilden's iterative candidate generation in linear (squared RGB)
                    # space; sorted by brightness and selected via pattern[x][y].
                    n = 2 if config.dither.endswith('2') else 4
                    linear = original*original
                    error = np.zeros_like(linear)
                    choices = []
                    brightnesses = []
                    bright_weights = np.array([.299,.587,.114],np.float32)
                    palette_linear = colors.astype(np.float32)**2
                    for k in range(n):
                        sample = np.sqrt(np.clip(linear+error*config.dither_strength,0,65025))
                        diff = sample[:,None,:]-colors[None,:,:].astype(np.float32)
                        distance = np.sum(diff*diff*np.array([2,4,1],np.float32),axis=2)
                        if zero_reserved: distance[:,0] = np.inf
                        candidate = np.argmin(distance,axis=1).astype(np.uint8)
                        choices.append(candidate)
                        brightnesses.append(np.sum(palette_linear[candidate]*bright_weights,axis=1))
                        error += linear-palette_linear[candidate]
                    order = np.argsort(np.stack(brightnesses,axis=1),axis=1,kind='stable')
                    ordered = np.take_along_axis(np.stack(choices,axis=1),order,axis=1)
                    x = ch % pw
                    y = ch // pw
                    rank = pattern[x%2,y%2]
                    chosen = ordered[np.arange(len(ch)),rank]
                ind_flat[ch] = chosen
                dst_flat[ch,:3] = colors[chosen]
    # Outside the source rectangle, map to color zero for clean tile padding.
    preview = Image.fromarray(preview_arr[:height, :width], 'RGBA')
    # RGB error on visible, opaque pixels (reconstruction compared with original)
    vis = valid[:height, :width]
    if np.any(vis):
        delta = preview_arr[:height, :width, :3][vis].astype(np.float32) - rgb[:height, :width][vis].astype(np.float32)
        mse = float(np.mean(delta**2))
    else:
        mse = 0.0
    update(100, 'Concluído')
    return Result(preview, palettes.astype(np.uint8)*85,
                  assignments.reshape(th, tw), indices, config, (width, height),
                  (pw, ph), history, mse, int(np.count_nonzero(~vis)))



def hardware_data(result):
    """Encode Mode 4 bitplanes, 9-bit pattern indexes and 6-bit CRAM."""
    from tile_optimizer import optimize
    cfg=result.settings
    available=min(cfg.vram_budget_tiles,448-cfg.base_tile)
    opt=optimize(result.indices,result.tile_palettes,budget=available,
                 allow_lossy=cfg.allow_lossy_tiles,palettes_rgb=result.palettes_rgb,reserve_zero=cfg.transparent)
    if not opt['fits_budget']:
        raise ValueError(f"{opt['unique_count']} tiles únicos excedem o orçamento de {available}. Ative a substituição de tiles similares, reduza a imagem ou aumente o orçamento.")
    tiles=opt['tiles']
    planes=np.zeros((len(tiles),8,4),np.uint8)
    for bit in range(4):
        planes[:,:,bit]=np.packbits((tiles>>bit)&1,axis=2)[:,:,0]
    attrs=(opt['mapping'].astype(np.uint16)+cfg.base_tile
           | ((opt['flips']&0x0800)>>2) | ((opt['flips']&0x1000)>>2)
           | (result.tile_palettes.ravel().astype(np.uint16)<<11)).astype('<u2')
    cram=np.zeros((2,16),np.uint8)
    for p in range(cfg.palettes):
        colors=np.rint(result.palettes_rgb[p]/85).astype(np.uint8)
        cram[p,:cfg.colors]=colors[:,0]|(colors[:,1]<<2)|(colors[:,2]<<4)
    return planes.tobytes(),attrs.tobytes(),cram.tobytes(),opt


def export(result,destination,prefix='art'):
    """Export native SMS data and C arrays ready for devkitSMS/SMSlib."""
    tiles,tilemap,cram,opt=hardware_data(result)
    prefix=''.join(c for c in prefix if c.isascii() and (c.isalnum() or c=='_')) or 'art'
    if prefix[0].isdigit():prefix='art_'+prefix
    output=Path(destination);output.mkdir(parents=True,exist_ok=True)
    files=[]
    def write(name,data):
        p=output/name;p.write_bytes(data);files.append(p)
    write(prefix+'.tiles.sms.bin',tiles)
    write(prefix+'.map.le.bin',tilemap)
    write(prefix+'.palettes.sms.bin',cram)
    preview=output/(prefix+'.png');result.preview.save(preview);files.append(preview)
    palette=Image.new('RGB',(16*24,2*24))
    draw=ImageDraw.Draw(palette)
    for p in range(result.settings.palettes):
        for c in range(result.settings.colors):
            draw.rectangle((c*24,p*24,c*24+23,p*24+23),fill=tuple(map(int,result.palettes_rgb[p,c])))
    p=output/(prefix+'_palettes.png');palette.save(p);files.append(p)
    tx,ty=result.tile_palettes.shape[1],result.tile_palettes.shape[0]
    manifest={'format':'Sega Master System Mode 4','source_size':result.source_size,
              'padded_size':result.padded_size,'tiles_x':tx,'tiles_y':ty,
              'unique_tiles':opt['unique_count'],'base_tile':result.settings.base_tile,
              'lossy_merges':opt['lossy_merges'],'palette_count':result.settings.palettes,
              'colors_per_palette':result.settings.colors,'vram_bytes':16384,
              'tile_limit':448,'name_table_address':'0x3800 (192-line mode)',
              'tiles':'8x8, 32 bytes, rows of 4 bitplanes, LSB plane first, left pixel bit 7',
              'map':'little-endian 16-bit: index 0-8, H flip 9, V flip 10, palette 11, priority 12=0',
              'cram':'32 bytes, 00BBGGRR, 2 palettes of 16 colors',
              'alpha':'Background color 0 is opaque; optional source alpha maps to configured color 0.',
              'note':'Two palettes for backgrounds use the sprite palette too. Larger maps require game-side streaming. Extended screen modes require SMS II VDP and a different VRAM layout.'}
    write(prefix+'.json',(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode())
    arrays={'tiles':tiles,'map':tilemap,'palettes':cram}
    header=['/* Native SMS Mode 4 assets. Include once. */','#include <SMSlib.h>']
    for name,data in arrays.items():
        header.append(f'static const unsigned char {prefix}_{name}[] = {{')
        header.extend('  '+','.join(f'0x{v:02x}' for v in data[i:i+16])+',' for i in range(0,len(data),16))
        header.append('};')
    header.extend([f'#define {prefix}_WIDTH_TILES {tx}',f'#define {prefix}_HEIGHT_TILES {ty}',f'#define {prefix}_BASE_TILE {result.settings.base_tile}'])
    write(prefix+'.h',('\n'.join(header)+'\n').encode())
    example=f'''/* Include {prefix}.h in your game. Use while the display is off. */
#include "{prefix}.h"
void load_{prefix}(void) {{
    SMS_loadTiles({prefix}_tiles, {prefix}_BASE_TILE, sizeof({prefix}_tiles));
    SMS_loadBGPalette({prefix}_palettes);
    SMS_loadSpritePalette({prefix}_palettes + 16);
'''
    if tx<=32 and ty<=24:
        example+=f'    SMS_loadTileMapArea(0, 0, {prefix}_map, {tx}, {ty});\n'
    else:example+='    /* Map larger than 256x192: stream visible rows/columns in your engine. */\n'
    example+='}\n'
    write(prefix+'_example.c',example.encode())
    guide='''TILE PALETTE STUDIO — MASTER SYSTEM
Tiles: formato planar Mode 4, 32 bytes/tile. Mapa: palavras little-endian.
Paletas: 32 bytes CRAM (00BBGGRR), incluindo paleta de sprites.
O header .h contém arrays C; o exemplo usa SMSlib/devkitSMS.
O limite padrão de 448 tiles reserva VRAM a partir de 0x3800 para o tilemap.
O orçamento e o tile inicial devem respeitar os recursos já usados pelo seu jogo.
Imagens maiores são assets para seu motor, não cabem de uma só vez na tela.
Transparência do PNG não é transparência do plano de fundo no hardware.
A ROM de teste aceita apenas 256x192; não contém rolagem ou sprites.
'''
    write(prefix+'_COMO_USAR.txt',guide.encode())
    return files
