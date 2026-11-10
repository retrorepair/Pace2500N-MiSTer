"""Observed EMMA graphics command subset, supplied by real DMA channel12.

Accepts the observed solid16 fill and indexed interlaced fill/packed copy.
Coordinates/size/stride/color come from guest commands, never a target fixture.
"""
from pace_probe_application_i2c import ApplicationI2CProbe
from pace_probe import StopProbe
class GraphicsProbe(ApplicationI2CProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.graphics_events=[];self.graphics_dma_completions=0
        self.graphics_dma_pending=0;self.graphics_dma_acks=0
        self.graphics_capture_unknown=False;self.graphics_unexecuted=0
    def sync_irq(self):
        super().sync_irq()
        if getattr(self,'graphics_dma_pending',0):
            # Native interrupt table: logical DMA IRQ2 maps to mask00000002,
            # callback80005E29. Logical interrupt numbers are not bit indices.
            self.read_overrides[0xb0000030]|=2
            if self.timer_regs[0xb0000040]&2:self.cp0[13]|=0x400
    def graphics_command(self,data):
        if len(data)!=60:raise StopProbe(f'Unmodelled graphics packet size {len(data)}')
        w=[int.from_bytes(data[n:n+4],'big') for n in range(0,60,4)]
        if w[0]==0x00ac0000:
            # Observed menu command: word1 points at a CPU-rasterized packed
            # scratch image, while words2..6 contain unused stack values.
            # GoRetroTv fa3a471 independently measured width as source pitch.
            # Accept only this observed incomplete-source-descriptor profile.
            if (w[5]&0xffff)+1<=2048 and w[6]>>26==0:
                raise StopProbe('Unmodelled indexed copy with full source descriptor')
            source=w[1]&0x1fffffff;bases=[w[7]&0x1fffffff,w[8]&0x1fffffff]
            stride=(w[11]&0x7ff)+1;x=w[12]&0x7ff;y=(w[12]>>16)&0x3ff
            width=(w[13]&0x7ff)+1;height=((w[13]>>16)&0x3ff)+1
            if x+width>stride or source+width*height>len(self.ram):
                raise StopProbe('Indexed packed copy exceeds source/row bounds')
            rows=[]
            for row in range(height):
                line=y+row;dest=bases[line&1]+(line>>1)*stride+x
                if dest+width>len(self.ram):raise StopProbe('Indexed packed copy exceeds destination RAM')
                rows.append(dest)
            pixels=bytes(self.ram[source:source+width*height])
            for row,dest in enumerate(rows):self.ram[dest:dest+width]=pixels[row*width:(row+1)*width]
            self.graphics_events.append(dict(step=self.steps,opcode=f'{w[0]:08X}',
                kind='inferred_interlaced_index8_packed_copy',source=f'{source:08X}',
                source_stride=width,bases=[f'{a:08X}' for a in bases],stride=stride,
                x=x,y=y,width=width,height=height,distinct_source_indices=len(set(pixels)),
                words=[f'{n:08X}' for n in w],layout_verified_on_hardware=False))
            return
        if w[0]==0x01ac0000:
            # Original rect API1FCA0 ->086FC:8-bit color duplicated into
            # the two16-bit color halves. Bit00200000 selects two fields;
            # driver supplies two separately allocated720x288 index buffers
            # for a720x576 surface. Rect coordinates are full-frame units.
            if w[1]!=w[7] or w[2]!=w[8]:raise StopProbe('Unmodelled indexed-fill source/destination relation')
            bases=[w[7]&0xffffff,w[8]&0xffffff];stride=(w[11]&0x7ff)+1
            x=w[12]&0x7ff;y=(w[12]>>16)&0x3ff
            width=(w[13]&0x7ff)+1;height=((w[13]>>16)&0x3ff)+1
            colors=[w[14]>>16&255,w[14]&255]
            if x+width>stride:raise StopProbe('Indexed fill exceeds row stride')
            rows=[]
            for line in range(y,y+height):
                field=line&1;start=bases[field]+(line>>1)*stride+x
                if start+width>len(self.ram):raise StopProbe('Indexed fill exceeds guest RAM')
                rows.append((start,field))
            for start,field in rows:self.ram[start:start+width]=bytes([colors[field]])*width
            self.graphics_events.append(dict(step=self.steps,opcode=f'{w[0]:08X}',
                kind='inferred_interlaced_index8_fill',bases=[f'{a:08X}' for a in bases],
                stride=stride,x=x,y=y,width=width,height=height,colors=[f'{c:02X}' for c in colors],
                words=[f'{n:08X}' for n in w],layout_verified_on_hardware=False))
            return
        if w[0]!=0x418f0000:
            if not self.graphics_capture_unknown:raise StopProbe(f'Unmodelled graphics opcode {w[0]:08X}')
            if self.graphics_unexecuted>=512:raise StopProbe('Graphics capture-only limit reached')
            self.graphics_unexecuted+=1
            self.graphics_events.append(dict(step=self.steps,opcode=f'{w[0]:08X}',kind='CAPTURE_ONLY_NOT_EXECUTED',
                words=[f'{n:08X}' for n in w]))
            return
        base=w[7]&0x0fffffff;stride=((w[11]&0x7ff)+1)*2
        x=w[12]&0x7ff;y=(w[12]>>16)&0x3ff
        width=(w[13]&0x7ff)+1;height=((w[13]>>16)&0x3ff)+1
        color=(w[14]>>16).to_bytes(2,'big')
        if (x+width)*2>stride:raise StopProbe('Graphics fill exceeds row stride')
        start=base+y*stride+x*2;end=start+(height-1)*stride+width*2
        if end>len(self.ram):raise StopProbe('Graphics fill exceeds guest RAM')
        row=color*width
        for n in range(height):self.ram[start+n*stride:start+n*stride+len(row)]=row
        self.graphics_events.append(dict(step=self.steps,opcode=f'{w[0]:08X}',kind='solid16_fill',
            base=f'{base:08X}',start=f'{start:08X}',end=f'{end:08X}',stride=stride,
            x=x,y=y,width=width,height=height,color=color.hex(),words=[f'{n:08X}' for n in w]))
    def start_graphics_dma(self):
        if not self.mmio_streams.get((0xb000603c,4)) or not self.mmio_streams[(0xb000603c,4)][-1]&0x10:
            raise StopProbe('Graphics DMA while engine disabled')
        descriptor=self.demux_regs.get(0xb0009100,0)
        if not descriptor:raise StopProbe('Graphics DMA descriptor missing')
        raw=self.physical_read(descriptor,40);w=[int.from_bytes(raw[n:n+4],'big') for n in range(0,40,4)]
        start,end=w[3],w[8]
        if w[5]!=0x0014003c or end-start+1!=60:raise StopProbe(f'Unmodelled graphics DMA descriptor {w[5]:08X}')
        self.graphics_command(self.physical_read(start,60));self.graphics_dma_completions+=1
        self.demux_regs[0xb0009010]&=~0x1000
        self.graphics_dma_pending|=0x1000;self.sync_irq()
    def write(self,address,value,size=4):
        result=super().write(address,value,size)
        if address==0xb0009010 and size==4 and value&0x1000:self.start_graphics_dma()
        if address==0xb0009130 and size==4:
            if self.graphics_dma_pending&value:self.graphics_dma_acks+=1
            self.graphics_dma_pending&=~value;self.sync_irq()
        return result
    def read(self,address,size=4):
        if address in (0xb0009120,0xb0009122):self.read_overrides[address]=self.graphics_dma_pending
        if address in (0xb0009140,0xb0009142):self.read_overrides[address]=0
        if address==0xb0009010:self.read_overrides[address]=self.demux_regs.get(address,0)
        return super().read(address,size)
    def report(self):
        r=super().report();r['experimental_graphics']=dict(completions=self.graphics_dma_completions,
            pending=f'{self.graphics_dma_pending:04X}',acks=self.graphics_dma_acks,
            events=self.graphics_events,completion_timing='immediate; not cycle accurate',
            capture_only_unexecuted=getattr(self,'graphics_unexecuted',0),
            pixels_complete=not getattr(self,'graphics_unexecuted',0))
        return r
