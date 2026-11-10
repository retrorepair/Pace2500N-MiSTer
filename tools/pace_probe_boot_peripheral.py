"""Peripheral completion + released front-panel inputs derived from U202.

FF FF matches the default input bytes at ROM1B05C and active-low button reader.
No identity/smartcard/tuner data is supplied by this profile.
"""
from pace_probe_console import ConsoleProbe
from pace_probe_serial_ack import encode_frame
from pace_probe import StopProbe
from pace_crc_accel import CrcLoopMixin

class BootPeripheralProbe(CrcLoopMixin,ConsoleProbe):
    def __init__(self,*args,button_state=0xffff,**kwargs):
        super().__init__(*args,**kwargs)
        self.button_state=button_state;self.application_entries=[]
    def handle_request(self,body):
        if len(body)>=3 and body[2]==0x44:
            self.peer_requests.append(body.hex())
            if len(body)!=4 or body[0]!=3 or body[3]!=0:
                raise StopProbe('Unmodelled front-panel query argument')
            reply=bytes([4,body[1],0x44])+self.button_state.to_bytes(2,'big')
            self.replies.append(dict(request=body.hex(),reply=reply.hex(),step=self.steps))
            self.rx_wire.extend(encode_frame(reply));return
        return super().handle_request(body)
    def step32(self):
        if self.pc in (0xbfc2048c,0x9fc2048c,0xbf82048c,0x9f82048c):
            self.application_entries.append(dict(pc=f'{self.pc:08X}',step=self.steps))
        return super().step32()
    def step16(self):
        if self.pc in (0xbfc2048c,0x9fc2048c,0xbf82048c,0x9f82048c):
            self.application_entries.append(dict(pc=f'{self.pc:08X}',step=self.steps))
        return super().step16()
    def report(self):
        r=super().report();r['front_panel_profile']=dict(raw=f'{self.button_state:04X}',state='all released' if self.button_state==0xffff else 'custom')
        r['application_entries']=self.application_entries
        return r
