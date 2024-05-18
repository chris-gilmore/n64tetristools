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
        checksum = self.calc_checksum(start, 0x18FC)
        self.write(checksum, start, 0x18FC, 4)
        if self.verbose:
            print(f"Writing checksum at 0x{start+0x18FC:04X} to 0x{checksum:08X}")

    def calc_checksum(self, start, length):
        checksum = 0
        i = 0
        while i < length:
            if self.endianness == 'big':
                a, b, c, d = self.data[start + i : start + i + 4]
            else:
                d, c, b, a = self.data[start + i : start + i + 4]
            checksum += a ^ 0x10
            checksum += b ^ 0x20
            checksum -= c
            checksum -= d << 1
            i += 4
        return checksum & 0xFFFFFFFF

    def write(self, value, start, offset, nbytes):
        self.data[start + offset : start + offset + nbytes] = value.to_bytes(nbytes, byteorder=self.endianness)

    def write_thrice(self, value, offset, nbytes):
        self.write(value, 0x0, offset, nbytes)
        self.write(value, 0x1900, offset, nbytes)
        self.write(value, 0x3200, offset, nbytes)

    def set_total_wonder_lines(self, twl):
        odd_bits = twl & 0xAAAAAAAA
        even_bits = twl & 0x55555555
        self.write_thrice(odd_bits, 0xF04, 4)
        self.write_thrice(even_bits, 0xF08, 4)
