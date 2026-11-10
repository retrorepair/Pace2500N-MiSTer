"""Research demux register scaffold, inferred from the original boot driver."""
from pace_probe_boot_fifo import BootFifoProbe
from pace_probe import StopProbe
from pace_transport import SectionAssembler,crc32_mpeg
from pace_nor import NorBank
from pathlib import Path

class DemuxProbe(BootFifoProbe):
    def __init__(self,*args,nor_profile='MBM29LV160B',**kwargs):
        super().__init__(*args,**kwargs)
        self.demux_regs={};self.demux_banks={0x124:{},0x144:{}}
        self.dma_events=[];self.stop_before_dma=False
        self.demux_input=[];self.dma_completed=False
        self.section_assembler=SectionAssembler();self.demux_outputs=[]
        self.crc_dropped=0;self.dma_transfers=[]
        self.board_latch=0;self.board_latch_writes=[]
        self.nor=[NorBank(self.flash,nor_profile),NorBank((Path(__file__).resolve().parents[1]/'firmware/FLASH_U203.bin').read_bytes(),nor_profile)]

    @staticmethod
    def memory_kind(address,size):
        if address&0xc0000000==0x80000000 and 0x1f800000<=(address&0x1fffffff) and (address&0x1fffffff)+size<=0x1fc00000:return 'flash'
        if address==0xb4180000 and size==1:return 'mmio'
        return BootFifoProbe.memory_kind(address,size)

    def physical_read(self,address,size):
        if 0<=address and address+size<=len(self.ram):return bytes(self.ram[address:address+size])
        if 0x1fc00000<=address and address+size<=0x1fc00000+len(self.flash):
            return self.flash[address-0x1fc00000:address-0x1fc00000+size]
        raise StopProbe(f'Unmodelled DMA source {address:08X}+{size:X}')

    def start_dma(self):
        descriptor=self.demux_regs.get(0xb0009090,0)
        if not descriptor:return
        raw=self.physical_read(descriptor,40)
        words=[int.from_bytes(raw[n:n+4],'big') for n in range(0,40,4)]
        start,end=words[3],words[8]
        if end<start or end-start>=0x100000:raise StopProbe('Unsupported DMA descriptor bounds')
        data=self.physical_read(start,end-start+1)
        self.demux_input.append(data);self.dma_completed=True
        self.dma_transfers.append(dict(descriptor=f'{descriptor:08X}',source=f'{start:08X}',bytes=len(data)))
        self.process_demux()

    def process_demux(self):
        if self.demux_regs.get(0,0)&0xe00!=0xe00:return
        bank=self.demux_banks[0x144];pointers=self.demux_banks[0x124]
        while self.demux_input:
            data=self.demux_input.pop(0)
            for pid,section in self.section_assembler.feed(data):
                if crc32_mpeg(section)!=0:self.crc_dropped+=1;continue
                # Driver table skips section_length bytes; remaining header
                # bytes are compared with programmed value/mask pairs.
                compared=section[:1]+section[3:10]
                for source_slot in range(2):
                    source=self.demux_regs.get(0x14+source_slot*4,0)
                    if not source&0x10000 or source&0x1fff!=pid:continue
                    enabled=bank.get(0x80+source_slot,0)
                    for output in range(2):
                        if not enabled&(1<<output):continue
                        match=True
                        for n,byte in enumerate(compared):
                            pair=(bank.get(n*16+output//2,0)>>(16*(output%2)))&0xffff
                            value,mask=pair>>8,pair&255
                            if byte&mask!=value&mask:match=False;break
                        if not match:continue
                        index=output*4;pointer=pointers.get(index,0);limit=pointers.get(index+2,0)
                        payload=section+bytes([output]);payload+=bytes((-len(payload))%4)
                        if pointer+len(payload)>limit:raise StopProbe('Demux output ring full/unsupported wrap')
                        base=(self.demux_regs.get(0x120,0)&0xffff)<<16
                        destination=base+pointer
                        if destination+len(payload)>len(self.ram):raise StopProbe('Demux DMA output outside guest RAM')
                        self.ram[destination:destination+len(payload)]=payload
                        pointers[index]=pointer+len(payload)
                        self.demux_outputs.append(dict(pid=pid,output=output,destination=f'{destination:08X}',bytes=len(payload),section_bytes=len(section)))
    def write(self,address,value,size=4):
        physical=address&0x1fffffff
        if address&0xc0000000==0x80000000 and 0x1f800000<=physical<0x1fc00000:
            offset=physical-0x1f800000
            return self.nor[offset>>21].write(offset&0x1fffff,value,size)
        super().write(address,value,size)
        if address==0xb4180000 and size==1:
            self.board_latch=value&255
            self.board_latch_writes.append(dict(step=self.steps,pc=f'{self.pc:08X}',value=f'{value&255:02X}'))
        if size!=4:return
        if 0xb000a000<=address<0xb000a200:
            offset=address-0xb000a000
            self.demux_regs[offset]=value&0xffffffff
            if offset in self.demux_banks:
                index=value&0x3fff;bank=self.demux_banks[offset]
                if value&0x8000:bank[index]=self.demux_regs.get(offset+4,0)
                else:self.demux_regs[offset+4]=bank.get(index,0)
                self.demux_regs[offset]=value&~0x4000
            if offset==0:self.process_demux()
        if 0xb0009000<=address<0xb0009200:
            self.demux_regs[address]=value&0xffffffff
            self.dma_events.append(dict(step=self.steps,pc=f'{self.pc:08X}',address=f'{address:08X}',value=f'{value:08X}'))
            if address==0xb0009010 and value&0x20:self.start_dma()
    def read(self,address,size=4):
        physical=address&0x1fffffff
        if address&0xc0000000==0x80000000 and 0x1f800000<=physical<0x1fc00000:
            offset=physical-0x1f800000
            return self.nor[offset>>21].read(offset&0x1fffff,size)
        if address==0xb4180000:raise StopProbe('Board output latch read semantics unmodelled')
        if address==0xb0009120 and self.dma_completed:self.read_overrides[address]=0x20
        if 0xb000a000<=address<0xb000a200 and size==4:
            self.read_overrides[address]=self.demux_regs.get(address-0xb000a000,0)
        return super().read(address,size)
    def step16(self):
        if self.stop_before_dma and self.pc==0xbfc0b118:
            raise StopProbe('Paused at configured boot DMA start')
        return super().step16()

    def report(self):
        r=super().report()
        r['experimental_demux']=dict(transfers=self.dma_transfers,outputs=self.demux_outputs,
            crc_dropped=self.crc_dropped,packets=self.section_assembler.packets,
            pointers={str(k):f'{v:08X}' for k,v in self.demux_banks[0x124].items()})
        r['self_test_returns']=self.test_returns;r['boot_flag_writes']=self.flag_writes
        r['board_output_latch']=dict(value=f'{self.board_latch:02X}',writes=self.board_latch_writes)
        r['inferred_nor_profile']=dict(name=getattr(self.nor[0],'profile','MBM29LV160B'),banks=[dict(identify=b.identify,commands=b.commands) for b in self.nor])
        return r
