"""Encode against this firmware's own initialized Huffman tree, not a web dict.

Addresses are decoded from the literal pool of original function 800BECF0.
No extracted dictionary is bundled. Supply the operator's initialized RAM dump.
Only dictionary selector zero is currently initialized by this firmware.
"""
from pathlib import Path


class FirmwareHuffman:
    def __init__(self, ram):
        self.ram = ram
        if len(ram) != 16 * 1024 * 1024:
            raise ValueError('Expected this firmware\'s 16 MiB initialized RAM image')

        def word(address, size=4):
            address &= 0x1fffffff
            if address + size > len(ram):
                raise ValueError('Dictionary pointer outside RAM')
            return int.from_bytes(ram[address:address + size], 'big')

        zero = word(word(0x800bedf0))
        one = word(word(0x800bedf4))
        count = word(word(0x800bedf8))
        phrases = word(word(0x800bee00))
        if count != 511:
            raise ValueError('Unsupported native Huffman tree shape')
        self.edges = (zero, one)
        self.symbols = {}
        self.codes = {}

        def visit(node, bits, ancestors):
            if node >= count or node in ancestors or len(bits) > 32:
                raise ValueError('Invalid native Huffman tree')
            for bit, base in enumerate(self.edges):
                value = word(base + 2 * node, 2)
                path = bits + str(bit)
                if not value & 0x8000:
                    visit(value, path, ancestors | {node})
                    continue
                symbol = (~value) & 0xffff
                if symbol < 256:
                    text = bytes((symbol,))
                else:
                    address = word(phrases + 4 * (symbol - 256)) & 0x1fffffff
                    if address >= len(ram):
                        raise ValueError('Phrase outside RAM')
                    end = ram.find(b'\x00', address, address + 4096)
                    if end < 0:
                        raise ValueError('Unterminated Huffman phrase')
                    text = ram[address:end]
                self.symbols[path] = text
                if text and len(path) < len(self.codes.get(text, 'x' * 100)):
                    self.codes[text] = path

        visit(0, '', set())
        # Pad the final byte with an INTERNAL prefix, not a literal TAB/NUL or
        # an invented end-marker. The native decoder ends at the byte length.
        # A deepest leaf guarantees that any prefix up to seven bits emits no
        # extra character after the last complete encoded symbol.
        self.padding = max(self.symbols, key=len)
        if len(self.padding) <= 7:
            raise ValueError('No safe final-byte padding path')

    @classmethod
    def from_file(cls, path):
        return cls(Path(path).read_bytes())

    def encode(self, text):
        source = text.encode('ascii') if isinstance(text, str) else bytes(text)
        # Minimum-bit parse supports multi-character phrases without greedy
        # phrase choices making later characters more expensive.
        best = [None] * (len(source) + 1)
        best[-1] = ''
        for offset in range(len(source) - 1, -1, -1):
            candidates = [bits + best[offset + len(value)]
                          for value, bits in self.codes.items()
                          if source.startswith(value, offset) and best[offset + len(value)] is not None]
            if not candidates:
                raise ValueError(f'Unencodable text byte at {offset}')
            best[offset] = min(candidates, key=len)
        bits = '00' + best[0]  # dictionary selector 0; first byte has six data bits
        bits += self.padding[:(-len(bits)) % 8]
        return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))

    def decode(self, encoded):
        if not encoded or encoded[0] >> 6:
            raise ValueError('Unsupported dictionary selector')
        bits = ''.join(f'{byte:08b}' for byte in encoded)[2:]
        prefix = ''
        output = bytearray()
        for bit in bits:
            prefix += bit
            if prefix in self.symbols:
                output += self.symbols[prefix]
                prefix = ''
        return bytes(output)
