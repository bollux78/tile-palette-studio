"""Mega Drive tile optimization: exact deduplication, free H/V flips, then optional
palette-aware global visual clustering and budget-limited lossy replacement.
The approximation is original code inspired by OrionSoft's optimization workflow.
"""
import numpy as np

FLIPS = (0, 0x0800, 0x1000, 0x1800)
def _flip(tile, bits):
    if bits & 0x0800: tile = tile[:, ::-1]
    if bits & 0x1000: tile = tile[::-1, :]
    return tile

def optimize(indices, tile_palettes, budget=None, allow_lossy=False, palettes_rgb=None, reserve_zero=True):
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
        counts = np.bincount(mapping, minlength=len(unique)).astype(np.float64)
        uses = [set() for _ in unique]
        for i, pal in zip(mapping, pids):
            uses[int(i)].add(int(pal))
        active = set(range(len(unique)))
        # Merge the globally least costly pair, not the first infrequent tile.
        # Cluster means retain ALL original samples, so successive merges never
        # measure an already degraded replacement as though it were the source.
        n = len(unique)
        if n > 4096:
            raise ValueError("A substituição visual aceita até 4096 tiles únicos por imagem. Reduza a resolução ou divida o mapa.")
        zero_masks = np.asarray(unique) == 0
        means = np.zeros((n,8,8,3), dtype=np.float64)
        groups = np.full(n,-1,dtype=np.int16)
        weights = np.array([.299,.587,.114],dtype=np.float64)
        for i in range(n):
            if len(uses[i]) == 1:
                groups[i] = next(iter(uses[i]))
                means[i] = palette[groups[i]][unique[i]]
        # Patterns shared across palettes stay exact: their visual meaning is
        # different under each palette and cannot be averaged in one RGB space.
        distances = np.full((n,n),np.inf,dtype=np.float64)
        orientations = np.zeros((n,n),np.uint16)
        def update_row(i, candidates):
            candidates=np.asarray(candidates,dtype=np.intp)
            if not len(candidates):return
            best=np.full(len(candidates),np.inf)
            flips_best=np.zeros(len(candidates),np.uint16)
            for bits in FLIPS:
                batch=means[candidates]
                if bits&0x0800:batch=batch[:,:,::-1,:]
                if bits&0x1000:batch=batch[:,::-1,:,:]
                delta=means[i]-batch
                error=np.sum(delta*delta*weights,axis=(1,2,3))
                if reserve_zero:
                    masks=zero_masks[candidates]
                    if bits&0x0800:masks=masks[:,:,::-1]
                    if bits&0x1000:masks=masks[:,::-1,:]
                    error[np.any(masks!=zero_masks[i],axis=(1,2))]=np.inf
                better=error<best
                best[better]=error[better];flips_best[better]=bits
            costs=best*counts[i]*counts[candidates]/(counts[i]+counts[candidates])
            distances[i,candidates]=costs;distances[candidates,i]=costs
            orientations[i,candidates]=flips_best;orientations[candidates,i]=flips_best
        for i in range(n):
            if groups[i]>=0:
                update_row(i,np.flatnonzero((groups==groups[i])&(np.arange(n)>i)))
        while len(active)>budget:
            flat=int(np.argmin(distances))
            i,j=divmod(flat,n)
            if not np.isfinite(distances[i,j]):break
            bits=int(orientations[i,j])
            other=means[j]
            if bits&0x0800:other=other[:,::-1,:]
            if bits&0x1000:other=other[::-1,:,:]
            means[i]=(means[i]*counts[i]+other*counts[j])/(counts[i]+counts[j])
            counts[i]+=counts[j]
            affected=mapping==j
            mapping[affected]=i;flips[affected]^=bits
            active.remove(j);merges+=1
            distances[j,:]=np.inf;distances[:,j]=np.inf
            candidates=[k for k in sorted(active) if k!=i and groups[k]==groups[i]]
            update_row(i,candidates)
            distances[i,i]=np.inf
        # New representative patterns use only the existing hardware palette.
        for i in active:
            if groups[i]>=0:
                colors=palette[groups[i]].astype(np.float64)
                delta=means[i][:,:,None,:]-colors[None,None,:,:]
                errors=np.sum(delta*delta*weights,axis=3)
                if reserve_zero:errors[:,:,0]=np.inf
                unique[i]=np.argmin(errors,axis=2).astype(np.uint8)
                if reserve_zero:unique[i][zero_masks[i]]=0
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
