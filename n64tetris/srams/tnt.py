import sys

class TheNewTetrisSram:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.data = bytearray()
        self.endianness = None

    def detect_endianness(self):
        magic_bytes = self.data[0x18F8 : 0x18FC]
        if magic_bytes == bytes.fromhex("302e3062"):
            self.endianness = 'big'
        elif magic_bytes == bytes.fromhex("62302e30"):
            self.endianness = 'little'
        else:
            self.endianness = None

    def from_file(self, filename):
        self.data = bytearray(open(filename, 'rb').read())
        self.detect_endianness()
        if self.endianness is None:
            print("error: Unknown endianness", file=sys.stderr)
            sys.exit(1)

    def to_file(self, filename):
        self.update_checksum(0x0)
        self.update_checksum(0x1900)
        self.update_checksum(0x3200)
        open(filename, 'wb').write(self.data)

    def update_checksum(self, start):
        sum = self.calc_checksum(start)
        self.data[start + 0x18FC : start + 0x1900] = sum.to_bytes(4, byteorder=self.endianness)
        if self.verbose:
            print(f"checksum at 0x{start+0x18FC:04X}: 0x{sum:08X}")

    def calc_checksum(self, start):
        sum = 0
        i = 0
        while i < 0x18FC:
            if self.endianness == 'big':
                a, b, c, d = self.data[start + i : start + i + 4]
            else:
                d, c, b, a = self.data[start + i : start + i + 4]
            sum += a ^ 0x10
            sum += b ^ 0x20
            sum -= c
            sum -= d << 1
            i += 4
        return sum & 0xFFFFFFFF
