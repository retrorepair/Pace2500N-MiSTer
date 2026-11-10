"""Read-only census of live Nucleus control blocks in this firmware's RAM.

Accept objects only with a printable name and valid same-type created-list
neighbours. Wait evidence requires an object to link to a suspension node that
contains both a known task pointer and that object's pointer. No guest writes.
"""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('ram', type=Path)
args = parser.parse_args()
ram = args.ram.read_bytes()


def word(at):
    at &= 0x1fffffff
    return int.from_bytes(ram[at:at + 4], 'big') if at + 4 <= len(ram) else 0


def pointer(value):
    return value & 0xe0000000 in (0x80000000, 0xa0000000) and value & 0x1fffffff < len(ram)


objects = {}
for magic in (b'TASK', b'SEMA', b'EVNT', b'PIPE', b'QUEU', b'HISR', b'TIME'):
    at = -1
    while True:
        at = ram.find(magic, at + 1)
        if at < 0:
            break
        base = at - 12
        if base < 0 or base % 4:
            continue
        name = ram[base + 16:base + 24].split(b'\x00')[0]
        if not name or any(c < 32 or c > 126 for c in name):
            continue
        neighbours = [word(base), word(base + 4)]
        if not all(pointer(v) and ram[(v & 0x1fffffff) + 12:(v & 0x1fffffff) + 16] == magic for v in neighbours):
            continue
        address = base | 0x80000000
        objects[address] = dict(address=f'{address:08X}', type=magic.decode(), name=name.decode())

seed = next((address for address, obj in objects.items() if obj['type'] == 'TASK' and obj['name'] == 'SMTTask'), None)
tasks = {}
address = seed
while address and address not in tasks:
    obj = objects.get(address)
    if not obj or obj['type'] != 'TASK':
        raise ValueError('Created-task list leaves validated task objects')
    tasks[address] = dict(obj, status=ram[(address & 0x1fffffff) + 24], runs=word(address + 28), waits=[])
    address = word(address + 4) | 0x80000000
    address &= 0x9fffffff

for object_address, obj in objects.items():
    if obj['type'] in ('TASK', 'HISR', 'TIME'):
        continue
    for offset in range(24, 256, 4):
        node = word(object_address + offset)
        visited = set()
        for _ in range(64):
            if not pointer(node) or node in visited:
                break
            visited.add(node)
            fields = [word(node + i) for i in range(0, 40, 4)]
            if object_address in fields:
                for task_address in tasks.keys() & set(fields):
                    evidence = dict(object=obj['address'], name=obj['name'], type=obj['type'], suspension=f'{node:08X}')
                    if evidence not in tasks[task_address]['waits']:
                        tasks[task_address]['waits'].append(evidence)
            # Suspension nodes use the same forward list link as created nodes.
            node = word(node + 4)

print(json.dumps(dict(source=str(args.ram), object_count=len(objects), task_count=len(tasks),
                     tasks=list(tasks.values())), indent=2))
