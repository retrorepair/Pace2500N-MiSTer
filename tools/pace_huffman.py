"""Encode guide text with the operator's original U202 firmware dictionary.

The legacy initialized RAM image is also accepted. Dictionary selector zero
is the dictionary initialized by this firmware.
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
        edges = tuple([word(base + 2 * node, 2) for node in range(count)]
                      for base in (zero, one))
        phrase_count = max((~value) & 0xffff for edge in edges for value in edge if value & 0x8000) - 255
        texts = []
        for index in range(phrase_count):
            address = word(phrases + 4 * index) & 0x1fffffff
            if address >= len(ram):
                raise ValueError('Phrase outside RAM')
            end = ram.find(b'\x00', address, address + 4096)
            if end < 0:
                raise ValueError('Unterminated Huffman phrase')
            texts.append(ram[address:end])
        self._load_tree(edges, texts)

    def _load_tree(self, edges, phrases):
        count = len(edges[0])
        if count != 511:
            raise ValueError('Unsupported native Huffman tree shape')
        self.edges = edges
        self.symbols = {}
        self.codes = {}

        def visit(node, bits, ancestors):
            if node >= count or node in ancestors or len(bits) > 32:
                raise ValueError('Invalid native Huffman tree')
            for bit, edge in enumerate(self.edges):
                value = edge[node]
                path = bits + str(bit)
                if not value & 0x8000:
                    visit(value, path, ancestors | {node})
                    continue
                symbol = (~value) & 0xffff
                if symbol < 256:
                    text = bytes((symbol,))
                else:
                    if symbol - 256 >= len(phrases):
                        raise ValueError('Huffman phrase index outside dictionary')
                    text = phrases[symbol - 256]
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
        # Phrases by first byte, in the dictionary's order (the parse's tie-break), and the
        # encodings already made: a week of listings repeats most titles many times.
        self._by_first = {}
        for value, bits in self.codes.items():
            self._by_first.setdefault(value[0], []).append((value, bits))
        self._cache = {}

    @classmethod
    def from_file(cls, path):
        data = Path(path).read_bytes()
        return cls.from_flash(data) if len(data) == 2 * 1024 * 1024 else cls(data)

    @classmethod
    def from_flash(cls, flash):
        """Read the resident dictionary through U202's original copy table.

        This extracts initialized application data for the PC encoder. The
        core receives the original flash image and executes its own loader.
        """
        from extract_application_ram import extract

        if len(flash) != 2 * 1024 * 1024:
            raise ValueError('Expected the 2 MiB FLASH_U202.bin firmware image')
        try:
            image, _ = extract(flash)
        except (AssertionError, IndexError) as error:
            raise ValueError('Unsupported U202 application copy table') from error

        # The resident resource at 800FD798 is read by the firmware's
        # dictionary initializer. It holds a header, two 511-node edge
        # tables and the length-delimited block of 256 NUL-ended phrases.
        start = 0xfd798
        if image[start:start + 6] != bytes.fromhex('0400000001ff'):
            raise ValueError('Unsupported U202 resident Huffman dictionary')
        count = 511
        edges = tuple([int.from_bytes(image[offset:offset + 2], 'big')
                       for offset in range(base, base + 2 * count, 2)]
                      for base in (start + 6, start + 6 + 2 * count))
        header = start + 6 + 4 * count
        if image[header:header + 4] != bytes.fromhex('00000100'):
            raise ValueError('Unsupported U202 Huffman phrase table')
        length = int.from_bytes(image[header + 4:header + 6], 'big')
        blob = image[header + 6:header + 6 + length]
        phrases = blob.split(b'\x00')
        if len(blob) != length or len(phrases) != 257 or phrases[-1] != b'':
            raise ValueError('Invalid U202 Huffman phrase block')
        codec = cls.__new__(cls)
        codec.ram = None
        codec._load_tree(edges, phrases[:-1])
        return codec

    def encode(self, text):
        source = text.encode('ascii') if isinstance(text, str) else bytes(text)
        hit = self._cache.get(source)
        if hit is not None:
            return hit
        # Minimum-bit parse supports multi-character phrases without greedy
        # phrase choices making later characters more expensive. Costs in bits from each
        # offset to the end; ties go to the earlier phrase in the dictionary.
        n = len(source)
        cost = [None] * (n + 1)
        cost[n] = 0
        choice = [None] * n
        for offset in range(n - 1, -1, -1):
            best = None
            for value, bits in self._by_first.get(source[offset], ()):
                rest = cost[offset + len(value)] if offset + len(value) <= n else None
                if rest is None or not source.startswith(value, offset):
                    continue
                total = len(bits) + rest
                if best is None or total < best:
                    best, choice[offset] = total, (value, bits)
            if best is None:
                raise ValueError(f'Unencodable text byte at {offset}')
            cost[offset] = best
        pieces, offset = [], 0
        while offset < n:
            value, bits = choice[offset]
            pieces.append(bits)
            offset += len(value)
        bits = '00' + ''.join(pieces)  # dictionary selector 0; first byte has six data bits
        bits += self.padding[:(-len(bits)) % 8]
        out = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
        if len(self._cache) >= 50000:
            self._cache.clear()
        self._cache[source] = out
        return out

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
