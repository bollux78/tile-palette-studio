"""Headless Z80+VDP-memory harness for generated SMS ROMs, backed by z80."""
import z80
import numpy as np


class SMSMachine:
    def __init__(self,rom):
        self.rom=rom;self.cpu=z80.Z80Machine()
        self.cpu.set_memory_block(0,rom[:0xc000])
        self.vram=bytearray(16384);self.cram=bytearray(32);self.regs=[0]*16
        self.latch=None;self.address=0;self.code=0;self.keys=0
        self.reference=None;self.applied_camera=(0,0);self.write_count=0;self.midwrite_checks=0
        self.cpu.set_input_callback(self.input)
        self.cpu.set_output_callback(self.output)
        self.cpu.set_write_callback(self.write)
        self.cpu.mark_addrs(0xfffc,4,self.cpu.WRITE_MARK)
        self.loop=int.from_bytes(rom[0x80:0x82],'little')
        self.cpu.set_breakpoint(self.loop)
        self.until_loop()

    def write(self,address,value):
        self.cpu.memory[address]=value
        if address==0xffff:
            start=(value%(len(self.rom)//16384))*16384
            self.cpu.set_memory_block(0x8000,self.rom[start:start+16384])
        if address==0xfffd:self.cpu.set_memory_block(0,self.rom[value*16384:(value+1)*16384])
        if address==0xfffe:self.cpu.set_memory_block(0x4000,self.rom[value*16384:(value+1)*16384])

    def input(self,port):
        port&=255
        if port==0xbf:return 0x80
        if port==0xdc:return (~self.keys)&255
        return 255

    def output(self,port,value):
        port&=255
        if port==0xbf:
            if self.latch is None:self.latch=value;return
            self.code=value>>6
            if self.code==2:
                self.regs[value&15]=self.latch
                if value&15==9:self.applied_camera=self.camera
            else:self.address=((value&63)<<8)|self.latch
            self.latch=None
        elif port==0xbe:
            mem=self.cram if self.code==3 else self.vram
            mem[self.address%len(mem)]=value
            self.address=(self.address+1)&0x3fff
            self.write_count+=1
            if self.reference is not None and self.regs[1]&0x40 and self.write_count%128==0:
                x,y=self.applied_camera
                np.testing.assert_array_equal(self.render(),self.reference[y:y+192,x:x+248])
                self.midwrite_checks+=1

    def until_loop(self):
        for _ in range(1000):
            self.cpu.ticks_to_stop=200000
            events=self.cpu.run()
            if events&self.cpu._BREAKPOINT_HIT:return
        raise AssertionError(f'Z80 loader did not reach frame loop; PC={self.cpu.pc:04x}')

    def frame(self,keys=0):
        self.keys=keys
        self.cpu.clear_breakpoint(self.loop)
        self.cpu.ticks_to_stop=1
        self.cpu.run()
        self.cpu.set_breakpoint(self.loop)
        self.until_loop()

    @property
    def camera(self):return tuple(int.from_bytes(self.cpu.memory[a:a+2],'little') for a in (0xc000,0xc002))

    def render(self):
        # Decode independently from native VDP bytes, including circular table,
        # palette bits and H/V flips. Return the unmasked 248x192 image area.
        planes=np.frombuffer(self.vram,np.uint8)[:14336].reshape(448,8,4)
        patterns=np.zeros((448,8,8),np.uint8)
        for bit in range(4):patterns|=np.unpackbits(planes[:,:,bit,None],axis=2)<<bit
        raw=np.frombuffer(self.cram,np.uint8).reshape(2,16)
        pal=np.stack([raw&3,(raw>>2)&3,(raw>>4)&3],axis=2)*85
        attrs=np.frombuffer(self.vram,np.dtype('<u2'),count=896,offset=0x3800).reshape(28,32)
        ys=(np.arange(192)+self.regs[9])%224
        xs=(np.arange(8,256)-self.regs[8])%256
        a=attrs[ys[:,None]//8,xs[None,:]//8]
        py=np.broadcast_to(ys[:,None]%8,a.shape).copy()
        px=np.broadcast_to(xs[None,:]%8,a.shape).copy()
        py=np.where((a&0x400)!=0,7-py,py)
        px=np.where((a&0x200)!=0,7-px,px)
        indices=patterns[a&511,py,px]
        return pal[(a>>11)&1,indices]
