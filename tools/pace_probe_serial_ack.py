"""Candidate transport ACK profile; no peripheral-data replies are invented.

LEN and the sequence field are identified in U202; sequence enforcement is not
established (the wrong-sequence control also advances). Opcode10 is recognised with
no data callback, so it is tested as an inferred ACK, not a confirmed MCU spec.
"""
from collections import deque
from pace_probe_serial_peer import SerialPeerProbe
from pace_probe import StopProbe

def encode_frame(body):
    wire=bytearray()
    for byte in body:
        if byte in (0,0x1b):wire.append(0x1b)
        wire.append(byte)
    wire.append(0)
    return wire

class AckSerialProbe(SerialPeerProbe):
    def __init__(self,*args,wrong_sequence=False,sync_ack_only=False,**kwargs):
        super().__init__(*args,**kwargs)
        self.rx_wire=deque();self.replies=[];self.wrong_sequence=wrong_sequence
        self.sync_ack_only=sync_ack_only;self.reply_milestones={}
        self.output_controls={}

    def step16(self):
        if self.pc in (0x9fc06312,0x9fc05ca2,0x9fc036c6,0x9fc126e4,0x9fc2048c):
            self.reply_milestones.setdefault(f'{self.pc:08X}',dict(step=self.steps,v0=f'{self.r[2]:08X}',sp=f'{self.r[29]:08X}'))
        return super().step16()
    def peer_rx_byte(self):return self.rx_wire.popleft() if self.rx_wire else 0

    def write(self,address,value,size=4):
        super().write(address,value,size)
        # The peer is the clock source. When the host advertises readiness,
        # a pending reply can initiate an exchange even with no host TX data.
        # Waiting for this GPIO write also prevents overwriting the one-byte
        # firmware RX mailbox before its task consumes the previous byte.
        if address==0xb200a000 and size==4 and value&1 and self.rx_wire and not self.serial_regs[0xb2009020]&1:
            self.clock_due=self.steps+8192
    def handle_request(self,body):
        self.peer_requests.append(body.hex())
        if len(body)<3 or len(body)!=body[0]+1:raise StopProbe('Invalid guest request length')
        opcode=body[2]
        if opcode not in (0x10,0x11,0x12,0x41,0x51,0x52):raise StopProbe(f'Peripheral-data semantics unknown for request {body.hex()}')
        if len(body)!=4:raise StopProbe('Unmodelled peripheral command size')
        if opcode==0x52 and body[3:]!=bytes([0]):raise StopProbe('Unmodelled sync request argument')
        if opcode!=0x52:self.output_controls[f'{opcode:02X}']=f'{body[3]:02X}'
        sequence=body[1]
        if self.wrong_sequence:sequence=(sequence%127)+1
        # U202 handler06408 consumes no data and releases the completion
        # semaphore. Send its opcode through the real RX path, not a RAM poke.
        response_opcode=0x52 if opcode==0x52 and not self.sync_ack_only else 0x10
        reply=bytes([2,sequence,response_opcode])
        self.replies.append(dict(request=body.hex(),reply=reply.hex(),step=self.steps))
        self.rx_wire.extend(encode_frame(reply))
    def report(self):
        r=super().report();r['candidate_transport_ack']=dict(wrong_sequence=self.wrong_sequence,sync_ack_only=self.sync_ack_only,replies=self.replies,milestones=self.reply_milestones,output_controls=self.output_controls)
        return r

