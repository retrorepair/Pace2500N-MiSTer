"""Strict LSI-family grouped interface, inferred from guest + L64724 manual.

Exact silicon variant is NOT established. Guest uploads1024 program bytes and
uses control APR0400; the available L64724 releaseB manual specifies512 and0208.
Stop at that mismatch rather than silently emulate the wrong microcontroller.
"""
from pace_probe import StopProbe
import hashlib

class LsiGroupedDevice:
    def __init__(self):
        self.group=None;self.apr=0;self.groups={g:{} for g in range(8)}
        self.events=[];self.general_calls=[];self.variant_mismatch=None
    def select(self,group):
        if group>7:raise StopProbe(f'Unmodelled LSI group selector {group:02X}')
        self.group=group
    def write(self,value):
        group=self.group;address=self.apr
        self.events.append(dict(kind='write',group=group,apr=f'{address:04X}',value=f'{value:02X}'))
        if group==0:self.apr=(self.apr&0x1f00)|value
        elif group==1:self.apr=(self.apr&255)|((value&31)<<8)
        elif group==7:
            # Group7 writes disable the microcontroller; it is not running
            # in this strict profile, which stops before the unknown control.
            pass
        elif group in (2,4,5):
            if group==5 and address>=0x400:
                self.variant_mismatch=dict(group=group,apr=f'{address:04X}',value=f'{value:02X}')
                raise StopProbe(f'LSI variant control at group5 APR{address:04X}={value:02X} needs identification')
            self.groups[group][address]=value;self.apr=(address+1)&0x1fff
        elif group==3:raise StopProbe('LSI status-group write semantics need silicon identification')
        else:raise StopProbe('Reserved/unselected LSI register group')
    def peek(self):
        if self.group==0:return self.apr&255
        if self.group==1:return self.apr>>8
        if self.group==7:return 0 # documented reset-state arbiter value
        if self.group==4 and self.apr in self.groups[4]:return self.groups[4][self.apr]
        raise StopProbe(f'LSI group{self.group} APR{self.apr:04X} read data is unmodelled')
    def read(self):
        value=self.peek();self.events.append(dict(kind='read',group=self.group,apr=f'{self.apr:04X}',value=f'{value:02X}'))
        if self.group in (2,3,4,5):self.apr=(self.apr+1)&0x1fff
        return value
    def report(self):
        program=self.groups[5]
        raw=bytes(program[n] for n in range(len(program))) if set(program)==set(range(len(program))) else b''
        return dict(interface='LSI-family, exact derivative unconfirmed',apr=f'{self.apr:04X}',group=self.group,
            program_bytes=len(program),program_sha256=hashlib.sha256(raw).hexdigest() if raw else None,
            configuration_bytes=len(self.groups[4]),variant_mismatch=self.variant_mismatch,
            general_calls=self.general_calls,
            microcontroller_executed=False,events=self.events)

class LsiObserved512Device(LsiGroupedDevice):
    """Firmware-derived512-word variant; shared documented register semantics.

Functional control only: records program/config, with no incoming RF and no
instruction-level acquisition microcontroller. Never asserts signal lock.
Unknown identification/configuration reads still stop.
"""
    def __init__(self):
        super().__init__();self.control=0;self.micro_enabled=False
        self.status={n:0 for n in range(24)};self.system_status=[0]*4
        self.extended_status_zero=False
    def write(self,value):
        g,a=self.group,self.apr
        if g==5 and a==0x400:
            self.control=value;self.micro_enabled=bool(value&1)
            self.events.append(dict(kind='control',group=g,apr=f'{a:04X}',value=f'{value:02X}'))
            self.apr=(a+1)&0x1fff;return
        if g==3 and a<6:
            self.status[a&~1]=0;self.status[a|1]=0
            self.events.append(dict(kind='counter_clear',group=g,apr=f'{a:04X}',value=f'{value:02X}'))
            self.apr=(a+1)&0x1fff;return
        if g==7:self.micro_enabled=False
        super().write(value)
        if g==4 and a==55 and value&3:
            self.status={n:0 for n in range(24)};self.system_status=[0]*4
            self.groups[4][a]=value&~3
    def peek(self):
        if self.group==2:return self.system_status[self.apr&3]
        if self.group==3 and self.apr in self.status:
            if self.apr==6:raise StopProbe('LSI silicon identification register not supplied')
            return self.status[self.apr]
        if self.group==3 and 24<=self.apr<=33 and getattr(self,'extended_status_zero',False):return 0
        return super().peek()
    def report(self):
        r=super().report();r.update(interface='Observed512-word LSI-family derivative; functional no-RF profile',
            control=f'{self.control:02X}',micro_enabled=self.micro_enabled,
            satellite_lock=False,microcontroller_executed=False)
        r['extended_status_zero_diagnostic']=getattr(self,'extended_status_zero',False)
        r['extended_status_reads']=[e for e in self.events if e['kind']=='read' and e['group']==3 and int(e['apr'],16)>=24]
        return r
