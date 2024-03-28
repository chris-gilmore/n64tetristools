import sys
from enum import Enum, auto

from .. import utils

class AssetType(Enum):
    UNKNOWN = auto()

class AssetFormat(Enum):
    UNKNOWN = auto()

class BaseRom:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.decoders = ()
        self.data = bytearray()
        self.asm_addr = None

    def from_file(self, filename):
        self.data = bytearray(open(filename, 'rb').read())

    def to_file(self, filename):
        utils.sm64_update_checksums(self.data)
        open(filename, 'wb').write(self.data)

    def guess_asset(self, raw):
        info = {}
        return AssetType.UNKNOWN, AssetFormat.UNKNOWN, info

    def extract_asset(self, addr):
        found = False
        for decode in self.decoders:
            raw, info, err = decode(addr)
            if err is None:
                found = True
                break
        if not found:
            return None, None, None, None, None, f"No asset found at address: 0x{addr:06X}"

        asset_type, asset_format, asset_info = self.guess_asset(raw)
        if self.verbose:
            print(f"{asset_type.name}\t{asset_format.name}\t{asset_info}", file=sys.stderr)

        return raw, info, asset_type, asset_format, asset_info, None

    def scan(self):
        print(f"Start\tPrefix\tBuflen\tPayload\tEnd\tType\tFormat\tInfo")
        addr = 0
        while addr < len(self.data):
            _, info, asset_type, asset_format, asset_info, err = self.extract_asset(addr)
            if err is None:
                print(f"0x{addr:06X}\t{info['prefix'].decode()}\t{info['buflen']}\t{info['payload_size']}\t0x{info['end']:06X}\t{asset_type.name}\t{asset_format.name}\t{asset_info}")
                addr = info['end']
            else:
                addr += 1

    def word_align(self, addr):
        return (addr + 3) & ~3

    def insert_bytes(self, addr, raw):
        end = addr + len(raw)
        self.data[addr : end] = raw
        return end

    def asm(self, bytes_or_hexstring):
        if self.asm_addr is None:
            print("asm error: asm_addr is None", file=sys.stderr)
            sys.exit(1)

        if self.asm_addr & 3:
            print(f"asm error: asm_addr ({self.asm_addr:06X}) is not word-aligned", file=sys.stderr)
            sys.exit(1)

        type_ = type(bytes_or_hexstring)
        if type_ is bytes:
            raw = bytes_or_hexstring
        elif type_ is str:
            raw = bytes.fromhex(bytes_or_hexstring)
        else:
            print("asm error: argument type must be either bytes or str", file=sys.stderr)
            sys.exit(1)

        if len(raw) != 4:
            print("asm error: len(raw) != 4", file=sys.stderr)
            sys.exit(1)

        self.asm_addr = self.insert_bytes(self.asm_addr, raw)
