"""Read-only census of this firmware's SDK message lists in a RAM capture.

The table lookup (80023DBC), enqueue (8007FB08) and dequeue (8007FDC0)
layouts were independently decoded from the original firmware in Ghidra.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('ram', type=Path)
args = parser.parse_args()
ram = args.ram.read_bytes()


def word(address):
    offset = address & 0x1fffffff
    if offset + 4 > len(ram):
        raise ValueError(f'Address outside guest RAM: {address:08X}')
    return int.from_bytes(ram[offset:offset + 4], 'big')


def walk(address, next_offset):
    nodes = []
    seen = set()
    while address:
        if address in seen or len(nodes) >= 4096:
            raise ValueError('Message list cycle or implausible length')
        seen.add(address)
        nodes.append(dict(address=f'{address:08X}', callback=f'{word(address + 8):08X}',
                          payload=[f'{word(address + offset):08X}' for offset in range(12, 32, 4)]))
        address = word(address + next_offset)
    return nodes


table = word(0x80023e2c)
free = walk(word(0x80106f2c), 0)
queues = []
for index in range(64):
    task, metadata = word(table + index * 12), word(table + index * 12 + 4)
    if not task or not metadata:
        continue
    offset = task & 0x1fffffff
    if ram[offset + 12:offset + 16] != b'TASK':
        raise ValueError('Metadata table points outside validated task objects')
    name = ram[offset + 16:offset + 24].split(b'\0')[0].decode('ascii')
    nodes = walk(word(metadata + 4), 4)
    queues.append(dict(task=f'{task:08X}', name=name, metadata=f'{metadata:08X}',
                       message_size=int.from_bytes(ram[(metadata & 0x1fffffff) + 8:(metadata & 0x1fffffff) + 10], 'big'),
                       waiting=ram[(metadata & 0x1fffffff) + 10], queued=len(nodes),
                       callback_counts=dict(Counter(node['callback'] for node in nodes)),
                       payload_first_word_counts=dict(Counter(node['payload'][0] for node in nodes)),
                       messages=nodes))
if not any(queue['name'] == 'TASK30' for queue in queues):
    raise ValueError('Expected application task metadata was not found')
print(json.dumps(dict(source=str(args.ram), table=f'{table:08X}', free_messages=len(free),
                      queued_messages=sum(queue['queued'] for queue in queues),
                      queues=sorted(queues, key=lambda queue: -queue['queued'])), indent=2))
