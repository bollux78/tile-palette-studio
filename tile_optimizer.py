"""Mega Drive tile optimization: exact deduplication, free H/V flips, then optional
palette-aware perceptual correlation and budget-limited lossy replacement.
The approximation is original code inspired by OrionSoft's optimization workflow.
"""
import numpy as np

FLIPS = (0, 0x0800, 0x1000, 0x1800)
def _flip(tile, bits):
    if bits & 0x0800: tile = tile[:, ::-1]
    if bits & 0x1000: tile = tile[::-1, :]
    return tile

def optimize(indices, tile_palettes, budget=None, allow_lossy=False, palettes_rgb=None):
    ty, tx = tile_palettes.shape
    if indices.shape != (ty*8, tx*8):
        raise ValueError('Dimensões de tiles e mapa incompatíveis')
    if budget is not None and budget < 1:
        raise ValueError('Orçamento de tiles deve ser positivo')
    positions = indices.reshape(ty, 8, tx, 8).transpose(0,2,1,3).reshape(-1,8,8)
    pids = tile_palettes.ravel()
    # A shared pattern can be reused across palettes because the tilemap
    # independently selects its CRAM palette.
    lookup, unique, mapping, flips = {}, [], [], []
    for tile in positions:
        found = None
        for bits in FLIPS:
            key = _flip(tile, bits).tobytes()
            if key in lookup:
                found = (lookup[key], bits)
                break
        if found is None:
            idx = len(unique)
            unique.append(tile.copy())
            lookup[tile.tobytes()] = idx
            mapping.append(idx)
            flips.append(0)
        else:
            mapping.append(found[0])
            flips.append(found[1])
    lossless_count = len(unique)
    merges = 0
    if allow_lossy and budget is not None and len(unique) > budget:
        if palettes_rgb is None:
            raise ValueError('A redução perceptual requer as paletas RGB finais')
        palette = np.asarray(palettes_rgb, dtype=np.float32)
        if palette.ndim != 3 or palette.shape[2] != 3:
            raise ValueError('Formato de paletas RGB inválido')
        mapping = np.asarray(mapping, dtype=np.int32)
        flips = np.asarray(flips, dtype=np.uint16)
        counts = np.bincount(mapping, minlength=len(unique)).astype(np.int32)
        # Exact deduplication across palettes is lossless. Approximation across
        # differently colored palettes is permitted only when BOTH tile patterns
        # are used under the same single palette, preventing mismatched colors.
        uses = [set() for _ in unique]
        for i, pal in zip(mapping, pids):
            uses[int(i)].add(int(pal))
        active = set(range(len(unique)))
        weights = np.array([.299,.587,.114],dtype=np.float32)
        # Precompute color-space tile representations for single-palette patterns.
        visual = {}
        for i in active:
            if len(uses[i]) == 1:
                p = next(iter(uses[i]))
                visual[i] = palette[p][unique[i]].astype(np.float32)
        while len(active) > budget:
            selected = None
            # Least-used patterns first to reduce visible impact.
            for i in sorted(active, key=lambda k:(counts[k],k)):
                if i not in visual:
                    continue
                candidates = [j for j in active if j != i and j in visual and uses[j] == uses[i]]
                if not candidates:
                    continue
                # Frequency shortlist, then RGB-weighted comparison over all flips.
                candidates.sort(key=lambda j:(-counts[j],j))
                best = None
                source = visual[i]
                for j in candidates[:64]:
                    for bits in FLIPS:
                        diff = source - _flip(visual[j], bits)
                        distance = float(np.sum(diff*diff*weights))
                        score = (distance, -int(counts[j]), j, bits)
                        if best is None or score < best[0]:
                            best = (score,j,bits)
                if best is not None:
                    selected = (i,best[1],best[2])
                    break
            if selected is None:
                break
            i,j,bits = selected
            affected = mapping == i
            mapping[affected] = j
            flips[affected] ^= bits
            counts[j] += counts[i]
            uses[j].update(uses[i])
            active.remove(i)
            merges += 1
        retained = sorted(active)
        reindex = {old:new for new,old in enumerate(retained)}
        unique = [unique[i] for i in retained]
        mapping = np.asarray([reindex[int(i)] for i in mapping],dtype=np.uint16)
    return {
        'tiles': np.stack(unique).astype(np.uint8),
        'mapping': np.asarray(mapping,dtype=np.uint16),
        'flips': np.asarray(flips,dtype=np.uint16),
        'original_positions': len(positions),
        'lossless_unique': lossless_count,
        'unique_count': len(unique),
        'lossy_merges': merges,
        'fits_budget': budget is None or len(unique) <= budget,
    }
