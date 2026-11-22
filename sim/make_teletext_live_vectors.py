from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from pace_teletext import page_packets, subtitle_packets, transport_packet

root = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp')
raw = []
for repeat in range(2):
    raw += page_packets(100, {2: 'LIVE TRANSPORT PAGE', 4: 'FPGA PES TO VBI TEST'})
    raw += subtitle_packets('SUBTITLE 888 END TO END', repeat)
raw += page_packets(100, {})[:1] + subtitle_packets('SUBTITLE 888 END TO END')[:1]
packets = [transport_packet(raw[i:i + 3], n & 15) for n, i in enumerate(range(0, len(raw), 3))]
data = b''.join(packets)
(root / 'pace-live-text-input.hex').write_bytes(''.join(f'{b:02x}\n' for b in data).encode())
(root / 'pace-live-text-expected.hex').write_bytes(''.join(p.hex() + '\n' for p in raw).encode())
print(len(data))
