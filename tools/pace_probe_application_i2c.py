"""Inferred channel0 I2C byte completion, from application driver068xx..06Fxx.

Default profile supplies no external read data. Optional generic seeded register
experiments are provisional; strict LSI-family mode uses grouped addressing and
stops on the documented-versus-observed microcontroller variant mismatch.
"""
from pace_probe_application import ApplicationProbe
from pace_probe import StopProbe
from pace_lsi_grouped import LsiGroupedDevice

class ApplicationI2CProbe(ApplicationProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.i2c_enabled=False;self.i2c_ack_ca=False;self.i2c_nack_unknown=False;self.i2c_ack_18=False
        self.i2c_regs={a:0 for a in range(0xb2006000,0xb2006070,16)}
        self.i2c_due=None;self.i2c_address=None;self.i2c_start=False
        self.i2c_transactions=[];self.i2c_bytes=bytearray();self.i2c_events=[]
        self.device18_registers={};self.device18_seeds={};self.device18_pointer=None
        self.i2c_payload_index=0;self.i2c_receive=False;self.i2c_rx_valid=False;self.i2c_reads=[]
        self.lsi_grouped=None;self.eeprom=None
    def skip_idle(self,limit):
        if self.pc!=0x800d35dc:return super().skip_idle(limit)
        # Exact application counterpart of the protected loader's idle loop.
        expected=bytes.fromhex('3c0180108c2472d83c0180108c2872b014800003000000001100fff935040000')
        if not self.fast_idle or self.mode16 or self.branch is not None or self.delay_origin is not None:return False
        if not self.timer_armed or self.cp0.get(13,0)&0xfc00 or self.clock_due is not None or self.i2c_due is not None:return False
        if self.ram[0xd35dc:0xd35fc]!=expected:return False
        if any(self.ram[0x1072d8:0x1072dc]) or any(self.ram[0x1072b0:0x1072b4]):return False
        if self.r[1]!=0x80100000 or self.r[4]!=0 or self.r[8]!=0:return False
        if self.timer_regs[0xb000d030]&1:
            limit=min(limit,self.steps+max(0,(self.timer_remaining-1)//self.peripheral_ticks-8))
        distance=(self.cp0.get(11,0)-self.cp0.get(9,0))&0xffffffff
        loops=min((limit-self.steps)//8,max(0,distance//(8*self.counter_ticks)-1))
        if loops<=0:return False
        retired=loops*8;self.steps+=retired;self.idle_skipped+=retired
        self.advance_counter(retired)
        self.recent.append(f'{self.steps:8d} verified application idle fast-forward {retired} instructions')
        return True
    def sync_irq(self):
        super().sync_irq()
        if not getattr(self,'i2c_enabled',False):return
        pending=self.i2c_regs[0xb2006050]&1 and self.i2c_regs[0xb2006060]&1
        if pending:
            self.read_overrides[0xb0000030]|=0x200000
            if self.timer_regs[0xb0000040]&0x200000:self.cp0[13]|=0x400
    def write(self,address,value,size=4):
        super().write(address,value,size)
        if not self.i2c_enabled or address not in self.i2c_regs or size!=4:return
        self.i2c_regs[address]=value&0xffffffff
        self.i2c_events.append(dict(step=self.steps,pc=f'{self.pc:08X}',address=f'{address:08X}',value=f'{value:08X}'))
        if address==0xb2006000:
            if value==0x9a:
                if self.i2c_address is not None:
                    self.i2c_transactions.append(dict(address=f'{self.i2c_address:02X}',data=self.i2c_bytes.hex(),acknowledged=self.i2c_acknowledged(),repeated_start=True))
                self.i2c_start=True
            elif value==0x99 and self.i2c_address is not None:
                self.i2c_transactions.append(dict(address=f'{self.i2c_address:02X}',data=self.i2c_bytes.hex(),acknowledged=self.i2c_acknowledged()))
                if self.eeprom is not None and self.i2c_address in (0xa0,0xa1):self.eeprom.stop()
                self.i2c_address=None;self.i2c_bytes.clear();self.i2c_due=None
            elif value in (0xa8,0xac):
                if self.i2c_address==0xa1 and self.eeprom is not None:pass
                elif self.i2c_address==0x19 and self.lsi_grouped is not None:self.lsi_grouped.peek()
                elif self.i2c_address!=0x19 or self.device18_pointer not in self.device18_registers:
                    pointer='unset' if self.device18_pointer is None else f'{self.device18_pointer:02X}'
                    raise StopProbe(f'I2C receive requested; device18 register {pointer} is unmodelled')
                self.i2c_receive=True;self.i2c_rx_valid=False;self.i2c_due=self.steps+64
        if address==0xb2006040:
            if self.i2c_start:
                if value&255!=0xca and not (self.i2c_ack_18 and value&254==0x18) and not (self.eeprom is not None and value&254==0xa0) and not self.i2c_nack_unknown:raise StopProbe(f'Unmodelled I2C address byte {value&255:02X}')
                self.i2c_start=False
                self.i2c_address=value&255;self.i2c_bytes.clear()
                self.i2c_payload_index=0;self.i2c_rx_valid=False
                if self.eeprom is not None and self.i2c_address in (0xa0,0xa1):self.eeprom.begin(self.i2c_address)
            else:
                self.i2c_bytes.append(value&255)
                if self.eeprom is not None and self.i2c_address in (0xa0,0xa1):self.eeprom.write(value&255)
                if self.i2c_address==0 and self.lsi_grouped is not None:
                    if value&255!=6:raise StopProbe('Unknown LSI general-call argument')
                    self.lsi_grouped.general_calls.append(value&255)
                if self.i2c_address==0x18 and self.i2c_ack_18:
                    if self.lsi_grouped is not None:
                        if self.i2c_payload_index==0:self.lsi_grouped.select(value&255)
                        else:self.lsi_grouped.write(value&255)
                    elif self.i2c_payload_index==0:self.device18_pointer=value&255
                    else:
                        self.device18_registers[self.device18_pointer]=value&255
                        self.device18_pointer=(self.device18_pointer+1)&255
                    self.i2c_payload_index+=1
            self.i2c_due=self.steps+64
        self.sync_irq()
    def read(self,address,size=4):
        if getattr(self,'i2c_enabled',False) and address in self.i2c_regs:
            if address==0xb2006040 and not self.i2c_rx_valid:raise StopProbe('I2C RX byte not available')
            self.read_overrides[address]=self.i2c_regs[address]
        return super().read(address,size)
    def i2c_acknowledged(self):
        return bool(self.i2c_ack_ca and self.i2c_address==0xca or self.i2c_ack_18 and self.i2c_address is not None and self.i2c_address&254==0x18 or self.lsi_grouped is not None and self.i2c_address==0 or self.eeprom is not None and self.i2c_address in (0xa0,0xa1))
    def advance_counter(self,retired):
        super().advance_counter(retired)
        if self.i2c_enabled and self.i2c_due is not None and self.steps>=self.i2c_due:
            self.i2c_due=None
            if self.i2c_receive:
                if self.i2c_address==0xa1 and self.eeprom is not None:
                    value=self.eeprom.read();register=f'{(self.eeprom.pointer-1)&65535:04X}'
                else:
                    value=self.lsi_grouped.read() if self.lsi_grouped is not None else self.device18_registers[self.device18_pointer]
                    register=f'group{self.lsi_grouped.group}' if self.lsi_grouped is not None else f'{self.device18_pointer:02X}'
                self.i2c_regs[0xb2006040]=value;self.i2c_rx_valid=True;self.i2c_receive=False
                self.i2c_reads.append(dict(step=self.steps,address=f'{self.i2c_address:02X}',register=register,value=f'{value:02X}',seeded=self.i2c_address==0x19 and self.device18_pointer in self.device18_seeds))
                if self.i2c_address==0x19 and self.lsi_grouped is None:self.device18_pointer=(self.device18_pointer+1)&255
            self.i2c_regs[0xb2006010]=4 if self.i2c_acknowledged() else 0
            self.i2c_regs[0xb2006050]=1
            self.sync_irq()
    def report(self):
        r=super().report();r['inferred_i2c_channel0']=dict(enabled=self.i2c_enabled,
            ack_write_address_ca=self.i2c_ack_ca,completion_delay_instructions=64,
            unknown_address_nack_control=self.i2c_nack_unknown,
            address18_19_transport_ack_control=self.i2c_ack_18,
            transactions=self.i2c_transactions,events=self.i2c_events,
            external_read_data_supplied=bool(self.i2c_reads),reads=self.i2c_reads,
            experimental_device18_seeds={f'{k:02X}':f'{v:02X}' for k,v in self.device18_seeds.items()},
            device18_registers={f'{k:02X}':f'{v:02X}' for k,v in self.device18_registers.items()})
        r['strict_lsi_grouped_profile']=None if self.lsi_grouped is None else self.lsi_grouped.report()
        r['diagnostic_eeprom']=None if self.eeprom is None else self.eeprom.report()
        return r
