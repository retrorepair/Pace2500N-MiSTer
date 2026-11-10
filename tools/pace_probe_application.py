"""Application-entry RE profile. Not evidence of protected-loader handoff."""
from pace_probe_boot_peripheral import BootPeripheralProbe
from pace_probe import StopProbe
from pace_probe_serial_ack import encode_frame
from pace_external_uart import ExternalUart
from pace_crc_accel import crc,TABLE

class ApplicationProbe(BootPeripheralProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.external_output_writes=[]
        self.peer_selector_outputs={}
        self.ack_only54=False
        self.transport_ack_unknown=False;self.transport_only_requests=[]
        self.external_uart=ExternalUart()
        self.application_crc_calls=[]
        self.external_input_events=[]
        self.application_event_trace=[]
    def queue_remote_key(self,key):
        # Real RX dispatcher297B0 ->02 handler2AA80 extracts this byte
        # and maps it through original key tableFCEC0. No guest RAM edits.
        body=bytes([5,0,2,0,key>>4,(key&15)<<4])
        self.rx_wire.extend(encode_frame(body))
        self.external_input_events.append(dict(step=self.steps,kind='remote_key_press',
            key=f'{key:02X}',body=body.hex(),transport='experimental serial peer clock'))
        if self.gpio_regs.get(0xb200a000,0)&1 and not self.serial_regs[0xb2009020]&1:
            self.clock_due=self.steps+8192
    def step16(self):
        if not hasattr(self,'application_crc_calls'):self.application_crc_calls=[]
        if not hasattr(self,'application_event_trace'):self.application_event_trace=[]
        if self.pc in (0x8002a810,0x8006ea04,0x8006ea1a,0x8006ea58,0x8006eaf6,0x80036b54,0x800369e0,0x80054ddc,0x80054df2,0x80085128) and len(self.application_event_trace)<1024:
            event=dict(step=self.steps,pc=f'{self.pc:08X}',v0=f'{self.r[2]:08X}',
                args=[f'{n:08X}' for n in self.r[4:8]],ra=f'{self.r[31]:08X}')
            address=self.r[4]&0x1fffffff
            if 0x100000<=address<len(self.ram)-32:event['argument_ram']=bytes(self.ram[address:address+32]).hex()
            self.application_event_trace.append(event)
        if self.pc==0x800b1af4 and len(self.application_crc_calls)<128:
            self.application_crc_calls.append(dict(step=self.steps,source=f'{self.r[4]:08X}',
                length=self.r[5],caller=f'{self.r[31]:08X}'))
        return super().step16()
    def skip_pure_loop(self,limit):
        if not self.fast_crc or not self.mode16 or self.pc!=0x800b1b0e:return super().skip_pure_loop(limit)
        code=bytes.fromhex('a4e04c01f6003262eaee3248b70ee7499a403360eb4e651d4dff61f2')
        if self.ram[0xb1af8:0xb1b14]!=code or self.ram[0x101a34:0x101e34]!=TABLE:return False
        if self.branch is not None or self.delay_origin is not None:return False
        status=self.cp0.get(12,0)
        interrupts_possible=bool(status&1 and not status&6 and status&0xff00)
        if interrupts_possible and self.cp0.get(13,0)&status&0xff00:return False
        count=min(self.r[5],(limit-self.steps)//13)
        if interrupts_possible and self.timer_armed:
            distance=(self.cp0.get(11,0)-self.cp0.get(9,0))&0xffffffff
            count=min(count,max(0,(distance-1)//(13*self.counter_ticks)))
        if (interrupts_possible or not self.timer_regs[0xb000d020]&1) and self.timer_regs[0xb000d030]&1:
            count=min(count,max(0,(self.timer_remaining-1)//(13*self.peripheral_ticks)))
        for name in ('clock_due','i2c_due','serial0_due'):
            due=getattr(self,name,None)
            if due is not None:count=min(count,max(0,(due-self.steps-1)//13))
        if count<1:return False
        address=self.r[4];kind=self.memory_kind(address,count)
        if kind=='ram':data=bytes(self.ram[address&0xffffff:(address&0xffffff)+count])
        elif kind=='flash' and 0x1fc00000<=address&0x1fffffff and (address&0x1fffffff)+count<=0x1fe00000:
            start=(address&0x1fffffff)-0x1fc00000;data=self.flash[start:start+count]
        elif kind=='flash' and 0x1f800000<=(address&0x1fffffff)<0x1fc00000:
            bank=self.nor[((address&0x1fffffff)-0x1f800000)>>21]
            offset=address&0x1fffff
            if bank.identify or offset+count>len(bank.data):return False
            data=bank.data[offset:offset+count]
        else:return False
        if len(data)!=count:return False
        remaining=self.r[5];initial=self.r[3];previous=crc(data[:-1],initial)
        index=(previous>>24)^data[-1]
        self.r[2]=int.from_bytes(TABLE[index*4:index*4+4],'big');self.r[3]=crc(data,initial)
        self.r[4]=(address+count)&0xffffffff;self.r[5]=remaining-count
        self.r[7]=0x80101a34;self.r[24]=remaining-count+1
        retired=count*13;self.steps+=retired;self.mips16_count+=retired;self.extended_count+=count
        self.crc_skipped_instructions+=retired
        for offset in (0xb1b0e,0xb1b10,0xb1b12,0xb1af8,0xb1afa,0xb1afc,0xb1b00,0xb1b02,0xb1b04,0xb1b06,0xb1b08,0xb1b0a,0xb1b0c):
            pc=offset+0x80000000;self.unique16.add(pc);self.visits[pc]+=count
        self.recent.append(f'{self.steps:8d} exact application CRC {count} bytes / {retired} instructions')
        self.advance_counter(retired);return True
    def handle_request(self,body):
        if len(body)>=3 and (body[2]==0x53 or body[2]==0x54 and self.ack_only54):
            if body[2]==0x53 and (len(body)!=6 or body[0]!=5):raise StopProbe('Unmodelled command53 size')
            if body[2]==0x54 and (len(body)!=4 or body[0]!=3):raise StopProbe('Unmodelled command54 size')
            # Original builder296F0 sends three separate byte arguments.
            # Their physical meaning is unknown; retain the last two raw.
            self.peer_requests.append(body.hex())
            if body[2]==0x53:self.peer_selector_outputs[f'{body[3]:02X}']=body[4:6].hex()
            reply=bytes([2,body[1],0x10])
            self.replies.append(dict(request=body.hex(),reply=reply.hex(),step=self.steps))
            self.rx_wire.extend(encode_frame(reply));return
        if self.transport_ack_unknown and len(body)>=3 and body[2] not in (0x10,0x11,0x12,0x41,0x44,0x51,0x52):
            if len(body)!=body[0]+1:raise StopProbe('Invalid guest request length')
            # Explicit diagnostic control: only acknowledge packet receipt.
            # No identity, EEPROM, tuner or other device-data reply is supplied.
            self.peer_requests.append(body.hex());self.transport_only_requests.append(body.hex())
            reply=bytes([2,body[1],0x10])
            self.replies.append(dict(request=body.hex(),reply=reply.hex(),step=self.steps,transport_only=True))
            self.rx_wire.extend(encode_frame(reply));return
        return super().handle_request(body)
    @staticmethod
    def memory_kind(address,size):
        if (0xb4080000<=address<0xb4080008 or 0xb4080100<=address<0xb4080108) and size==1:return 'mmio'
        return BootPeripheralProbe.memory_kind(address,size)
    def write(self,address,value,size=4):
        if address==0xb4080002:
            self.external_output_writes.append(dict(step=self.steps,pc=f'{self.pc:08X}',value=f'{value:02X}'))
        result=super().write(address,value,size)
        if 0xb4080000<=address<0xb4080008 and size==1:self.external_uart.write(address-0xb4080000,value)
        return result
    def read(self,address,size=4):
        if 0xb4080000<=address<0xb4080008 and size==1:
            self.read_overrides[address]=self.external_uart.read(address-0xb4080000)
        return super().read(address,size)
    def report(self):
        r=super().report();r['application_external_output_writes']=self.external_output_writes
        r['application_peer_selector_outputs']=self.peer_selector_outputs
        r['command54_ack_only_control']=self.ack_only54
        r['unknown_command_transport_ack_control']=dict(enabled=self.transport_ack_unknown,requests=self.transport_only_requests)
        r['external_uart']=self.external_uart.report()
        r['application_crc_calls']=getattr(self,'application_crc_calls',[])
        r['external_input_events']=getattr(self,'external_input_events',[])
        r['application_event_trace']=getattr(self,'application_event_trace',[])
        r['mode_switches_omitted_from_history']=getattr(self,'mode_switches_omitted',0)
        return r
