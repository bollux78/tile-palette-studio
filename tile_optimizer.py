"""Mega Drive 4bpp tile deduplication, H/V flip reuse and optional lossy merge.
Operates on palette-local indices. Palette identity is kept in tilemap attributes.
"""
import numpy as np

def _variants(tile):
    yield tile, 0
    yield tile[:, ::-1], 0x0800
    yield tile[::-1, :], 0x1000
    yield tile[::-1, ::-1], 0x1800

def optimize(indices, tile_palettes, budget=None, allow_lossy=False):
    ty, tx = tile_palettes.shape
    tiles = indices.reshape(ty, 8, tx, 8).transpose(0, 2, 1, 3).reshape(-1, 8, 8)
    palettes = tile_palettes.ravel()
    canonical = {}
    unique = []
    mapping = []
    flips = []
    for tile in tiles:
        found = None
        for variant, flag in _variants(tile):
            key = variant.tobytes()
            if key in canonical:
                found = (canonical[key], flag)
                break
        if found is None:
            idx = len(unique)
            unique.append(tile.copy())
            canonical[tile.tobytes()] = idx
            mapping.append(idx)
            flips.append(0)
        else:
            mapping.append(found[0])
            flips.append(found[1])
    before = len(unique)
    replacements = 0
    # Approximate similar-tile replacement only when requested and necessary.
    # Palette-independent pixel indices are compared only between tiles with
    # the same palette ID, preventing cross-palette color mismatches.
    if allow_lossy and budget is not None and len(unique) > budget:
        counts = np.bincount(np.array(mapping), minlength=len(unique))
        representatives = np.array([int(palettes[np.flatnonzero(np.array(mapping)==i)[0]]) for i in range(len(unique))])
        active = set(range(len(unique)))
        # Merge the least-used tiles first into the closest compatible surviving
        # tile, evaluating all four flips. Deterministic, quality-first within
        # a least-used tier; no arbitrary color changes to the palette.
        while len(active) > budget:
            best = None
            for i in sorted(active, key=lambda k:(counts[k],k)):
                candidates = [j for j in active if j != i and representatives[j] == representatives[i]]
                if not candidates:
                    continue
                tile = unique[i].astype(np.int16)
                for j in candidates:
                    for variant, flag in _variants(unique[j]):
                        d = int(np.sum((tile-variant.astype(np.int16))**2))
                        score = (d * max(1,int(counts[i])), d, i, j, flag)
                        if best is None or score < best[0]:
                            best = (score,i,j,flag)
                if best is not None and best[0][0] == 0:
                    break
            if best is None:
                break
            _,i,j,flag = best
            # Mapping flags represent transforms of stored canonical tiles.
            # Compose flips by XOR; H and V commute.
            for k in range(len(mapping)):
                if mapping[k] == i:
                    mapping[k] = j
                    flips[k] ^= flag
            counts[j] += counts[i]
            active.remove(i)
            replacements += 1
        retained = sorted(active)
        remap = {old:new for new,old in enumerate(retained)}
        unique = [unique[i] for i in retained]
        mapping = [remap[i] for i in mapping]
    unique_array = np.stack(unique) if unique else np.empty((0,8,8),dtype=np.uint8)
    return {
        'tiles': unique_array.astype(np.uint8),
        'mapping': np.asarray(mapping,dtype=np.uint16),
        'flips': np.asarray(flips,dtype=np.uint16),
        'original_positions': len(tiles),
        'lossless_unique': before,
        'unique_count': len(unique),
        'lossy_merges': replacements,
        'fits_budget': budget is None or len(unique) <= budget,
    }
