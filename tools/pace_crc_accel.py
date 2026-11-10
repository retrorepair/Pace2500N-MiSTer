"""Opt-in, exact-code-guarded CRC loop acceleration with IRQ deadline bounds.

Computes CRC over actual guest bytes; never replaces validation results. It
preserves every modified GPR and the exact13 retired instructions per byte.
"""
import zlib
REVERSE=bytes(int(f'{n:08b}'[::-1],2) for n in range(256))
CODE=bytes.fromhex('6764100b3260a5e0f6003362ebee3368b729e76d9b604d01eb4e651e4eff61f2e8206743')
def reverse32(n):return int.from_bytes(n.to_bytes(4,'big').translate(REVERSE)[::-1],'big')
def crc(data,initial=0):
    return reverse32(zlib.crc32(data.translate(REVERSE),reverse32(initial)^0xffffffff)^0xffffffff)
def table_bytes():
    out=[]
    for n in range(256):
        v=n<<24
        for _ in range(8):v=((v<<1)^(0x04c11db7 if v&0x80000000 else 0))&0xffffffff
        out.append(v.to_bytes(4,'big'))
    return b''.join(out)
TABLE=table_bytes()

class CrcLoopMixin:
    def __init__(self,*args,fast_crc=False,**kwargs):
        super().__init__(*args,**kwargs)
        self.fast_crc=fast_crc;self.crc_skipped_instructions=0
        self.crc_guard=(self.flash[0x129e4:0x12a08]==CODE and self.flash[0x1bae0:0x1bee0]==TABLE and
                        self.flash[0x12a98:0x12a9c]==bytes.fromhex('9fc1bae0'))

    def skip_pure_loop(self,limit):
        if not self.fast_crc or not self.crc_guard or not self.mode16 or self.pc not in (0x9fc129fe,0xbfc129fe):return False
        if self.branch is not None or self.delay_origin is not None or self.cp0.get(13,0)&0xff00:return False
        count=min(self.r[6],(limit-self.steps)//13)
        if self.timer_armed:
            distance=(self.cp0.get(11,0)-self.cp0.get(9,0))&0xffffffff
            count=min(count,max(0,(distance-1)//(13*self.counter_ticks)))
        if hasattr(self,'timer_regs') and self.timer_regs[0xb000d030]&1:
            count=min(count,max(0,(self.timer_remaining-1)//(13*self.peripheral_ticks)))
        if getattr(self,'clock_due',None) is not None:
            count=min(count,max(0,(self.clock_due-self.steps-1)//13))
        if count<1:return False
        address=self.r[5];kind=self.memory_kind(address,count)
        if kind=='ram':data=bytes(self.ram[address&0xffffff:(address&0xffffff)+count])
        elif kind=='flash':
            physical=address&0x1fffffff
            if 0x1fc00000<=physical and physical+count<=0x1fe00000:
                data=self.flash[physical-0x1fc00000:physical-0x1fc00000+count]
            elif hasattr(self,'nor') and 0x1f800000<=physical<0x1fc00000:
                bank=self.nor[(physical-0x1f800000)>>21];offset=physical&0x1fffff
                if bank.identify:return False
                data=bank.data[offset:offset+count]
            else:return False
        else:return False
        if len(data)!=count:return False
        old_remaining=self.r[6];initial=self.r[3]
        before_last=crc(data[:-1],initial)
        self.r[2]=(before_last<<8)&0xffffffff
        self.r[3]=crc(data,initial);self.r[5]=(address+count)&0xffffffff
        self.r[6]=old_remaining-count;self.r[7]=0x9fc1bae0;self.r[24]=old_remaining-count+1
        retired=13*count;self.steps+=retired;self.mips16_count+=retired
        self.extended_count+=count;self.crc_skipped_instructions+=retired
        base=self.pc&0xffe00000
        for offset in (0x129fe,0x12a00,0x12a02,0x129e8,0x129ea,0x129ec,0x129f0,0x129f2,0x129f4,0x129f6,0x129f8,0x129fa,0x129fc):
            pc=base+offset;self.unique16.add(pc);self.visits[pc]+=count
        self.recent.append(f'{self.steps:8d} exact CRC loop {count} bytes / {retired} instructions')
        self.advance_counter(retired)
        return True

    def report(self):
        r=super().report();r['crc_acceleration']=dict(enabled=self.fast_crc,guard=self.crc_guard,instructions=self.crc_skipped_instructions)
        return r
