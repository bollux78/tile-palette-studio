import unittest
import numpy as np
from tile_optimizer import optimize,_flip


def reconstruct(opt,shape):
    ty,tx=shape
    out=np.empty((ty*8,tx*8),np.uint8)
    for k,(i,bits) in enumerate(zip(opt['mapping'],opt['flips'])):
        y,x=divmod(k,tx)
        out[y*8:y*8+8,x*8:x*8+8]=_flip(opt['tiles'][i],int(bits))
    return out


class OptimizerTests(unittest.TestCase):
    def test_global_merge_preserves_rare_outlier(self):
        # First tile is a unique bright detail; the remaining two are almost equal.
        indices=np.repeat(np.array([[1,2,3]],np.uint8),8,axis=0).repeat(8,axis=1)
        pal=np.zeros((1,16,3),np.uint8);pal[0,1]=250;pal[0,2]=0;pal[0,3]=10
        opt=optimize(indices,np.zeros((1,3),np.uint8),budget=2,allow_lossy=True,palettes_rgb=pal)
        self.assertEqual(opt['unique_count'],2)
        result=reconstruct(opt,(1,3))
        np.testing.assert_array_equal(pal[0][result[:,:8]],pal[0][indices[:,:8]])
        self.assertLess(np.mean((pal[0][result].astype(float)-pal[0][indices])**2),40)

    def test_lossless_flips_unchanged(self):
        tile=np.arange(64,dtype=np.uint8).reshape(8,8)%15+1
        indices=np.concatenate([tile,tile[:,::-1],tile[::-1]],axis=1)
        opt=optimize(indices,np.array([[0,1,0]]))
        self.assertEqual(opt['unique_count'],1)
        np.testing.assert_array_equal(reconstruct(opt,(1,3)),indices)

    def test_reserved_zero_mask_is_preserved(self):
        rng=np.random.default_rng(5)
        tile=rng.integers(1,16,(8,8),dtype=np.uint8);tile[:2,:]=0
        other=tile.copy();other[4:,:]=1
        indices=np.concatenate([tile,other],axis=1)
        pal=np.repeat(np.arange(16,dtype=np.uint8)[None,:,None]*15,3,axis=2)
        opt=optimize(indices,np.array([[0,0]]),budget=1,allow_lossy=True,palettes_rgb=pal)
        self.assertTrue(opt['fits_budget'])
        np.testing.assert_array_equal(reconstruct(opt,(1,2))==0,indices==0)

    def test_distinct_transparency_masks_do_not_merge(self):
        indices=np.ones((8,16),np.uint8);indices[0,0]=0
        pal=np.repeat(np.arange(16,dtype=np.uint8)[None,:,None]*15,3,axis=2)
        opt=optimize(indices,np.array([[0,0]]),budget=1,allow_lossy=True,palettes_rgb=pal)
        self.assertFalse(opt['fits_budget'])

    def test_sms_opaque_zero_can_be_used(self):
        indices=np.ones((8,16),np.uint8);indices[:,8:]=2
        pal=np.zeros((1,16,3),np.uint8);pal[0,1]=85;pal[0,2]=170
        opt=optimize(indices,np.array([[0,0]]),budget=1,allow_lossy=True,palettes_rgb=pal,reserve_zero=False)
        self.assertTrue(opt['fits_budget'])
        self.assertLessEqual(int(opt['tiles'].max()),15)

    def test_cholirede_sms_448_quality(self):
        from pathlib import Path
        from PIL import Image,ImageOps
        from sms_quantizer import quantize,Settings
        original=Image.open(Path(__file__).resolve().parents[1]/'cholirede.png').convert('RGBA')
        fitted=ImageOps.contain(original,(256,192),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(256,192),(0,0,0,255))
        canvas.alpha_composite(fitted,((256-fitted.width)//2,(192-fitted.height)//2))
        r=quantize(canvas,Settings(dither='vertical4',dither_strength=.38))
        opt=optimize(r.indices,r.tile_palettes,budget=448,allow_lossy=True,palettes_rgb=r.palettes_rgb,reserve_zero=False)
        self.assertTrue(opt['fits_budget'])
        reduced=reconstruct(opt,r.tile_palettes.shape)
        rgb=np.empty((192,256,3),np.uint8)
        for y in range(24):
            for x in range(32):
                rgb[y*8:y*8+8,x*8:x*8+8]=r.palettes_rgb[r.tile_palettes[y,x]][reduced[y*8:y*8+8,x*8:x*8+8]]
        mse=np.mean((rgb.astype(float)-np.asarray(r.preview)[:,:,:3])**2)
        # Old frequency-first replacement scores about 1297 here.
        self.assertLess(mse,600)
