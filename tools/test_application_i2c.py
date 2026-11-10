"""Exercise genuine I2C ISR/driver completion, including NACK error control."""
import gzip,pickle
from pace_probe_application_i2c import ApplicationI2CProbe
from pace_probe import StopProbe

class DriverReturnProbe(ApplicationI2CProbe):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.driver_returns=[]
    def step16(self):
        if self.pc==0x80006cda:self.driver_returns.append(self.r[2])
        return super().step16()

with gzip.open('re/application_entry_08.pkl.gz','rb') as f:old=pickle.load(f)
for ack,expected_data,expected_return in ((True,'3ffea670',0),(False,'',8)):
    p=DriverReturnProbe(old.flash);p.__dict__.update(pickle.loads(pickle.dumps(old.__dict__)))
    p.i2c_enabled=True;p.i2c_ack_ca=ack;p.transport_ack_unknown=True;p.fast_idle=True
    body=bytes.fromhex(p.peer_requests.pop());p.handle_request(body);p.attach_current_request()
    p.run(11860000)
    assert p.i2c_transactions==[dict(address='CA',data=expected_data,acknowledged=ack)],p.i2c_transactions
    assert p.driver_returns==[expected_return],p.driver_returns
    expected_irqs=5 if ack else 1
    assert sum(e['pc']=='80006DD4' for e in p.i2c_events)==expected_irqs
    assert not p.i2c_regs[0xb2006060]&1 and not p.i2c_regs[0xb2006050]&1
    assert p.i2c_due is None and p.i2c_address is None
print('PASS: genuine I2C ISR sends4 payload bytes after ACK and returns0; NACK sends none and returns8; IRQs acknowledged')
