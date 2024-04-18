import sys
import struct
from enum import Enum, auto

from PIL import Image

from .base import BaseRom
from .. import utils

class AssetType(Enum):
    UNKNOWN = auto()
    IMAGE = auto()

class AssetFormat(Enum):
    UNKNOWN = auto()
    RGBA5551 = auto()       # b'\x00\x00\x00\x00'
    CODE02 = auto()         # b'\x00\x02\x00\x00'
    CODE03 = auto()         # b'\x00\x03\x00\x00'
    SIZE_ASSUMED = auto()

class TetrisphereRom(BaseRom):
    def __init__(self, verbose=False, force=False):
        super().__init__(game_code=b'NTPE', verbose=verbose, force=force)
        self.decoders = (self.sqsh_decode,)

    def sqsh_decompress(self, addr, compressed_size, expected_size):
        raw = b''
        p = 0
        while p < compressed_size:
            c = self.data[addr+p]
            p += 1
            if c & 0x80:
                c &= 0x7f
                c += 1
                c <<= 1
                b = int.from_bytes(self.data[addr+p : addr+p + 2], byteorder='big')
                b <<= 1
                for i in range(0, c, 2):
                    raw += raw[b+i : b+i + 2]
                p += 2
            else:
                c += 1
                c <<= 1
                raw += self.data[addr+p : addr+p + c]
                p += c

        raw_size = len(raw)
        assert (raw_size == expected_size or
                raw_size == expected_size + 1)
        if raw_size == expected_size + 1:
            return raw[:-1]
        else:
            return raw

    def sqsh_decode(self, addr):
        prefix = self.data[addr : addr + 4]
        if prefix != b'SQSH':
            return None, None, f"No SQSH asset found at address: 0x{addr:06X}"

        buflen = int.from_bytes(self.data[addr+4 : addr+4 + 4], byteorder='big')
        payload_size = int.from_bytes(self.data[addr+8 : addr+8 + 4], byteorder='big')

        if payload_size == buflen:
            raw = self.data[addr+12 : addr+12 + buflen]
        else:
            raw = self.sqsh_decompress(addr+12, payload_size, buflen)

        end = addr+12 + payload_size

        if self.verbose:
            print(f"0x{addr:06X}\t{prefix.decode()}\t{buflen}\t{payload_size}\t0x{end:06X}", file=sys.stderr)

        info = {'prefix': prefix, 'buflen': buflen, 'payload_size': payload_size, 'end': end}
        return raw, info, None

    def guess_asset(self, raw):
        info = {}
        buflen = len(raw)

        width, height = struct.unpack('>2H', raw[:4])

        if buflen == 2 * width * height + 8:
            if raw[4:8] == b'\x00\x00\x00\x00':
                info['width'], info['height'] = width, height
                return AssetType.IMAGE, AssetFormat.RGBA5551, info

        elif buflen == width * height + 8:
            if raw[4:8] == b'\x00\x02\x00\x00':
                info['width'], info['height'] = width, height
                return AssetType.IMAGE, AssetFormat.CODE02, info

            elif raw[4:8] == b'\x00\x03\x00\x00':
                info['width'], info['height'] = width, height
                return AssetType.IMAGE, AssetFormat.CODE03, info

        elif buflen == 1024:
            info['width'], info['height'] = 32, 32
            return AssetType.IMAGE, AssetFormat.SIZE_ASSUMED, info

        return AssetType.UNKNOWN, AssetFormat.UNKNOWN, info

    def extract_image(self, i_addrs):
        image_stack = []
        for i_addr in i_addrs:
            raw, _, asset_type, asset_format, asset_info, err = self.extract_asset(i_addr)
            if err is not None:
                print(err, file=sys.stderr)
                sys.exit(1)

            if asset_type != AssetType.IMAGE:
                print(f"No image found at address: 0x{i_addr:06X}", file=sys.stderr)
                sys.exit(1)

            if asset_format == AssetFormat.RGBA5551:
                im = Image.frombytes('RGBA', (asset_info['width'], asset_info['height']), utils.rgba5551_to_rgba8888(raw[8:]))

            elif asset_format == AssetFormat.UNKNOWN:
                print(f"Unknown image format at address: 0x{i_addr:06X}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"Unimplemented image format at address: 0x{i_addr:06X}", file=sys.stderr)
                sys.exit(1)

            image_stack.append(im)

        if image_stack:
            im = image_stack.pop(0)
            if not image_stack:
                im.save('image.png', format='png')
            else:
                im.save('anim.webp', format='webp', save_all=True, lossless=True, exact=True, minimize_size=True, loop=0, duration=1000, append_images=image_stack)
