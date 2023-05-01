import sys
from enum import Enum, auto

class AssetType(Enum):
    UNKNOWN = auto()

class AssetFormat(Enum):
    UNKNOWN = auto()

class BaseRom:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.decoders = ()
        self.data = bytearray()

    def from_file(self, filename):
        self.data = bytearray(open(filename, 'rb').read())

    def to_file(self, filename):
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
