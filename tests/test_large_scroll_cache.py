"""Regression tests for VRAM pattern cache and name-table ownership."""
import random
import unittest

def simulate(screen_tw=40, width_tw=128, height_tw=70, moves="", old=False):
    cache_w=screen_tw+(3 if old else 6)
    cache_h=31 if old else 32
    patterns={}
    nametable={}
    def upload(sx,sy):
        slot=(sy%cache_h)*cache_w+(sx%cache_w)+1
        if sx>=width_tw or sy>=height_tw:
            slot=0
        else:
            patterns[slot]=(sx,sy)
        nametable[(sx%64,sy%32)]=slot
    for y in range(cache_h):
        for x in range(cache_w):
            upload(x,y)
    x=y=0
    for step,direction in enumerate(moves):
        prev=(x,y)
        if direction=="R":x=min(x+2,(width_tw-screen_tw)*8)
        if direction=="L":x=max(0,x-2)
        if direction=="D":y=min(y+2,(height_tw-28)*8)
        if direction=="U":y=max(0,y-2)
        if (x,y)==prev:continue
        tx,ty=x//8,y//8
        if old:
            if direction=="R" and x%8==0 and x>=16:
                for sy in range(ty,ty+31):upload(tx+screen_tw+1,sy)
            if direction=="L" and x%8==6 and x>=8:
                for sy in range(ty,ty+31):upload(tx-1,sy)
            if direction=="D" and y%8==0 and y>=16:
                for sx in range(tx,tx+cache_w):upload(sx,ty+29)
            if direction=="U" and y%8==6 and y>=8:
                for sx in range(tx,tx+cache_w):upload(sx,ty-1)
        else:
            if direction=="R" and x%8==0 and x>=24:
                for sy in range(max(0,ty-2),max(0,ty-2)+32):
                    upload(tx+screen_tw+3,sy)
            if direction=="L" and x%8==6 and x>=16:
                for sy in range(max(0,ty-2),max(0,ty-2)+32):
                    upload(tx-2,sy)
            if direction=="D" and y%8==0 and y>=24:
                for sx in range(max(0,tx-2),max(0,tx-2)+cache_w):
                    upload(sx,ty+29)
            if direction=="U" and y%8==6 and y>=16:
                for sx in range(max(0,tx-2),max(0,tx-2)+cache_w):
                    upload(sx,ty-2)
        for sy in range(ty,(y+223)//8+1):
            for sx in range(tx,(x+screen_tw*8-1)//8+1):
                slot=nametable.get((sx%64,sy%32))
                if patterns.get(slot)!=(sx,sy):
                    return (step,direction,x,y,sx,sy,slot,patterns.get(slot))
    return None

class LargeScrollCacheTest(unittest.TestCase):
    def test_old_loader_fails_after_mixed_axis_scroll(self):
        seq="R"*400+"D"*190+"L"*220+"U"*120
        self.assertIsNotNone(simulate(moves=seq,old=True))
        self.assertIsNone(simulate(moves=seq))
    def test_reverse_and_cross_all_name_table_wraps(self):
        seq=("R"*400+"D"*190+"L"*220+"U"*120+
             "R"*250+"D"*100+"L"*370+"U"*160)*2
        for tw in (32,40):
            with self.subTest(tw=tw):
                self.assertIsNone(simulate(screen_tw=tw,moves=seq))
    def test_random_direction_changes_large_canvas(self):
        for tw in (32,40):
            for seed in range(12):
                rng=random.Random(seed)
                seq="".join(rng.choice("RLDU")*rng.randrange(18,112)
                            for _ in range(100))
                with self.subTest(tw=tw,seed=seed):
                    self.assertIsNone(simulate(screen_tw=tw,moves=seq))
    def test_cache_fits_before_plane_a(self):
        for tw in (32,40):
            self.assertLessEqual(1+(tw+6)*32,1536)

if __name__=="__main__":
    unittest.main()
