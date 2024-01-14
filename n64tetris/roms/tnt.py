import sys
import struct
from enum import Enum, auto

from PIL import Image
import lzo

from .base import BaseRom
from .. import utils
from ..mappings import tnt as tntmap

class AssetType(Enum):
    UNKNOWN = auto()
    IMAGE = auto()
    PALETTE = auto()

class AssetFormat(Enum):
    UNKNOWN = auto()
    RGBA5551 = auto()
    INTENSITY = auto()
    COLOR_INDEX = auto()

class TheNewTetrisRom(BaseRom):
    def __init__(self, verbose=False):
        super().__init__(verbose=verbose)
        self.decoders = (self.h2o_decode,)

    def h2os_decompress(self, addr, buflen):
        success = False

        for end in range(addr+3, len(self.data) + 1):
            if self.data[end-3 : end] == b'\x11\x00\x00':
                try:
                    raw = lzo.decompress(bytes(self.data[addr : end]), False, buflen)
                    success = True
                    break
                except lzo.error:
                    continue

        if not success:
            raise lzo.error(f"Failed to decompress at address: 0x{addr:06X}")

        assert len(raw) == buflen
        return raw, end

    def h2o_decode(self, addr):
        prefix = self.data[addr : addr + 4]
        if prefix not in (b'H2OS', b'H2ON'):
            return None, None, f"No H2O asset found at address: 0x{addr:06X}"

        buflen = int.from_bytes(self.data[addr+4 : addr+4 + 4], byteorder='big')

        if prefix == b'H2OS':
            raw, end = self.h2os_decompress(addr+8, buflen)
        else:  # prefix == b'H2ON'
            end = addr+8 + buflen
            raw = bytes(self.data[addr+8 : end])

        payload_size = end - (addr+8)

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
                return AssetType.IMAGE, AssetFormat.INTENSITY, info

            elif raw[4:8] == b'\x00\x03\x00\x00':
                info['width'], info['height'] = width, height
                return AssetType.IMAGE, AssetFormat.COLOR_INDEX, info

        elif buflen == 512:
            return AssetType.PALETTE, AssetFormat.RGBA5551, info

        return AssetType.UNKNOWN, AssetFormat.UNKNOWN, info

    def extract_image_or_anim(self, i_addrs):
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

            elif asset_format == AssetFormat.INTENSITY:
                im = Image.frombytes('L', (asset_info['width'], asset_info['height']), raw[8:])
                im.info['transparency'] = 0x00

            elif asset_format == AssetFormat.COLOR_INDEX:
                im = Image.frombytes('P', (asset_info['width'], asset_info['height']), raw[8:])

                p_addr = tntmap.PALETTE[i_addr]

                raw, _, asset_type, asset_format, _, err = self.extract_asset(p_addr)
                if err is not None:
                    print(err, file=sys.stderr)
                    sys.exit(1)

                if asset_type != AssetType.PALETTE:
                    print(f"No palette found at address: 0x{p_addr:06X}", file=sys.stderr)
                    sys.exit(1)

                if asset_format == AssetFormat.RGBA5551:
                    im.putpalette(utils.rgba5551_to_rgba8888(raw), rawmode='RGBA')

                elif asset_format == AssetFormat.UNKNOWN:
                    print(f"Unknown palette format at address: 0x{p_addr:06X}", file=sys.stderr)
                    sys.exit(1)
                else:
                    print(f"Unimplemented palette format at address: 0x{p_addr:06X}", file=sys.stderr)
                    sys.exit(1)

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

    def extract_image(self, i_addr):
        i_addrs = []
        i_addrs.append(i_addr)
        self.extract_image_or_anim(i_addrs)

    def extract_anim(self, i_addr):
        if i_addr not in tntmap.ANIM:
            print(f"No anim found at address: 0x{i_addr:06X}", file=sys.stderr)
            sys.exit(1)

        i_addrs = []
        i_addrs.append(i_addr)
        i_addrs.extend(tntmap.ANIM[i_addr])
        self.extract_image_or_anim(i_addrs)

    def extract_by_name(self, name):
        if name in tntmap.ANIM_BY_NAME:
            self.extract_anim(tntmap.ANIM_BY_NAME[name])
        elif name in tntmap.IMAGE_BY_NAME:
            self.extract_image(tntmap.IMAGE_BY_NAME[name])
        else:
            print(f"No image or anim found by name: {name}", file=sys.stderr)
            sys.exit(1)

    def h2os_compress(self, raw):
        return lzo.optimize(lzo.compress(raw, 9, False), False, len(raw))

    def insert_asset(self, addr, raw, info):
        buflen = len(raw)

        if info['prefix'] == b'H2OS':
            raw = self.h2os_compress(bytes(raw))
            end = addr+8 + len(raw)
        else:  # info['prefix'] == b'H2ON'
            end = addr+8 + buflen

        #if end > info['end']:
        if end > tntmap.END[addr]:
            payload_size = end - (addr+8)
            print(f"Payload size ({payload_size}) is too large", file=sys.stderr)
        else:
            self.data[addr+8 : end] = raw

        self.data[addr : addr + 4] = info['prefix']
        self.data[addr+4 : addr+4 + 4] = buflen.to_bytes(4, byteorder='big')

    def insert_image(self, filename, i_addr):
        with Image.open(filename) as im:
            # TODO:
            # If we need to convert to mode='L', then we ought to do something different than what is done below, so that we may properly deal with transparency.

            # Otherwise, convert to intermediary mode='RGBA'.
            # If our final destination mode is to be 'P', then this intermediary image will ensure that we get a palette with mode='RGBA' after converting to mode='P'.

            rgba_im = im.convert(mode='RGBA')

        _, info, asset_type, asset_format, asset_info, err = self.extract_asset(i_addr)
        if err is not None:
            print(err, file=sys.stderr)
            sys.exit(1)

        if asset_type != AssetType.IMAGE:
            print(f"No image found at address: 0x{i_addr:06X}", file=sys.stderr)
            sys.exit(1)

        im = rgba_im.resize((asset_info['width'], asset_info['height']))

        if asset_format == AssetFormat.RGBA5551:
            raw = bytearray()
            raw[:4] = struct.pack('>2H', asset_info['width'], asset_info['height'])
            raw[4:8] = b'\x00\x00\x00\x00'
            raw[8:] = utils.rgba8888_to_rgba5551(im.tobytes())
            self.insert_asset(i_addr, raw, info)

        elif asset_format == AssetFormat.INTENSITY:
            im = im.convert(mode='L')

            raw = bytearray()
            raw[:4] = struct.pack('>2H', asset_info['width'], asset_info['height'])
            raw[4:8] = b'\x00\x02\x00\x00'
            raw[8:] = im.tobytes()
            self.insert_asset(i_addr, raw, info)

        elif asset_format == AssetFormat.COLOR_INDEX:
            im = im.convert(mode='P', palette=Image.Palette.ADAPTIVE)

            raw = bytearray()
            raw[:4] = struct.pack('>2H', asset_info['width'], asset_info['height'])
            raw[4:8] = b'\x00\x03\x00\x00'
            raw[8:] = im.tobytes()
            self.insert_asset(i_addr, raw, info)

            p_addr = tntmap.PALETTE[i_addr]

            _, info, asset_type, asset_format, _, err = self.extract_asset(p_addr)
            if err is not None:
                print(err, file=sys.stderr)
                sys.exit(1)

            if asset_type != AssetType.PALETTE:
                print(f"No palette found at address: 0x{p_addr:06X}", file=sys.stderr)
                sys.exit(1)

            if asset_format == AssetFormat.RGBA5551:
                raw = bytearray()
                raw = utils.rgba8888_to_rgba5551(im.palette.tobytes())
                self.insert_asset(p_addr, raw, info)

            elif asset_format == AssetFormat.UNKNOWN:
                print(f"Unknown palette format at address: 0x{p_addr:06X}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"Unimplemented palette format at address: 0x{p_addr:06X}", file=sys.stderr)
                sys.exit(1)

        elif asset_format == AssetFormat.UNKNOWN:
            print(f"Unknown image format at address: 0x{i_addr:06X}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Unimplemented image format at address: 0x{i_addr:06X}", file=sys.stderr)
            sys.exit(1)

    def insert_by_name(self, filename, name):
        if name in tntmap.ANIM_BY_NAME:
            print(f"Instead of providing anim name, please supply the name of the anim's images one at a time.", file=sys.stderr)
            sys.exit(1)
        elif name in tntmap.IMAGE_BY_NAME:
            self.insert_image(filename, tntmap.IMAGE_BY_NAME[name])
        else:
            print(f"No image found by name: {name}", file=sys.stderr)
            sys.exit(1)

    def modify_seed(self, value):
        addr1 = 0x037688
        addr2 = 0x037690

        value &= 0xFFFFFFFF
        seed = value.to_bytes(4, byteorder='big')

        self.data[addr1 : addr1 + 2] = b'\x3C\x0F'   # lui $t7, ...
        self.data[addr1 + 2 : addr1 + 4] = seed[0:2]
        self.data[addr2 : addr2 + 2] = b'\x35\xEF'   # ori $t7, $t7, ...
        self.data[addr2 + 2 : addr2 + 4] = seed[2:4]

    def modify_bag(self, start, end, n):
        if start < 0:
            print("bag error: {START} must not be less than 0", file=sys.stderr)
            sys.exit(1)
        if end > 7:
            print("bag error: {END} must not be greater than 7", file=sys.stderr)
            sys.exit(1)
        if end - start < 1:
            print("bag error: {END} must be greater than {START}", file=sys.stderr)
            sys.exit(1)
        if n < 1:
            print("bag error: {N} must not be less than 1", file=sys.stderr)
            sys.exit(1)
        if n * (end - start) > 63:
            print("bag error: Bag size {N*(END-START)} must not be greater than 63", file=sys.stderr)
            sys.exit(1)

        addr1 = 0x037474
        addr2 = 0x03748F
        addr3 = 0x03749F
        addr4 = 0x0374AB

        bag_size = n * (end - start)

        self.data[addr1 : addr1 + 3] = b'\x20\x06\x00'   # addi $a2, $zero, ...
        self.data[addr1 + 3 : addr1 + 4] = bytes([start])
        self.data[addr2 : addr2 + 1] = bytes([end])
        self.data[addr3 : addr3 + 1] = bytes([n])
        self.data[addr4 : addr4 + 1] = bytes([bag_size])

    # Sprint goal (time)
    def modify_sprint(self, value):
        addr1 = 0x01851A

        value *= 60
        value &= 0xFFFF
        time = value.to_bytes(2, byteorder='big')

        self.data[addr1 : addr1 + 2] = time[0:2]

    # Ultra goal (lines)
    def modify_ultra(self, value):
        # for display
        addr1 = 0x01852A
        # for goal
        addr2 = 0x01A9BA

        value &= 0xFFFF
        lines = value.to_bytes(2, byteorder='big')

        self.data[addr1 : addr1 + 2] = lines[0:2]
        self.data[addr2 : addr2 + 2] = lines[0:2]

    def modify_piece_color(self, base_address, piece, r, g, b):
        if piece < 0 or piece > 6:
            print("piece error: Piece type must be between 0 and 6", file=sys.stderr)
            sys.exit(1)

        addr1 = base_address + piece * 12

        r &= 0xFF
        g &= 0xFF
        b &= 0xFF

        self.data[addr1 + 1 : addr1 + 2] = bytes([r])
        self.data[addr1 + 3 : addr1 + 4] = bytes([g])
        self.data[addr1 + 5 : addr1 + 6] = bytes([b])

    def modify_piece_diffuse_color(self, piece, r, g, b):
        base_address = 0x096210
        self.modify_piece_color(base_address, piece, r, g, b)

    def modify_piece_specular_color(self, piece, r, g, b):
        base_address = 0x096210 + 6
        self.modify_piece_color(base_address, piece, r, g, b)

    # Piece spawn delay
    def modify_spawn_delay(self, value):
        addr1 = 0x02EB73
        value &= 0xFF
        self.data[addr1 : addr1 + 1] = bytes([value])

    # Piece hold delay
    def modify_hold_delay(self, value):
        addr1 = 0x02C7D3
        value &= 0xFF
        if value == 0:
            print("Piece hold delay of 0 will freeze the game/console.", file=sys.stderr)
            sys.exit(1)
        self.data[addr1 : addr1 + 1] = bytes([value])

    # Piece lock delay
    def modify_lock_delay(self, value):
        addr1 = 0x02D2E7
        addr2 = 0x02E0F3
        value &= 0xFF
        self.data[addr1 : addr1 + 1] = bytes([value])
        self.data[addr2 : addr2 + 1] = bytes([value])

    # Line clearing delay
    def modify_line_delay(self, value):
        addr1 = 0x02F59B
        value &= 0xFF
        self.data[addr1 : addr1 + 1] = bytes([value])

    # Square forming delay
    def modify_square_delay(self, value):
        addr1 = 0x030973
        value &= 0xFF
        self.data[addr1 : addr1 + 1] = bytes([value])

    def modify_screens(self, start, end):
        if start < 0:
            print("screens error: {START} must not be less than 0", file=sys.stderr)
            sys.exit(1)
        if end > 7:
            print("screens error: {END} must not be greater than 7", file=sys.stderr)
            sys.exit(1)
        if end - start < 0:
            print("screens error: {END} must not be less than {START}", file=sys.stderr)
            sys.exit(1)

        for addr1, addr2, addr3 in [(0x0570E0, 0x0570E8, 0x0570D7),    # Game mode
                                    (0x0571D8, 0x0571E0, 0x0571CF)]:   # Attract mode
            # Enables all screens without needing to unlock all wonders
            self.data[addr3 : addr3 + 1] = bytes([0])
            # Now limit the set of allowable screens
            self.data[addr1 : addr1 + 3] = b'\x24\x04\x00'   # addiu $a0, $zero, ...
            self.data[addr1 + 3 : addr1 + 4] = bytes([start])
            self.data[addr2 : addr2 + 3] = b'\x24\x05\x00'   # addiu $a1, $zero, ...
            self.data[addr2 + 3 : addr2 + 4] = bytes([end])

    def modify_stat_position(self, stat, x, y):
        if stat < 1 or stat > 3:
            print("stat error: Stat type must be between 1 and 3", file=sys.stderr)
            sys.exit(1)

        if stat == 1:
            """
            1p, Finale screen, player 1 name
            /* 02A3E4 0002A3E4 24060125 */  addiu $a2, $zero, 0x125
            /* 02A3E8 0002A3E8 240700CA */  addiu $a3, $zero, 0xca
            """
            addr1 = 0x02A3E6
            addr2 = 0x02A3EA

        elif stat == 2:
            """
            1p, All screens, player 1 line count
            /* 0262B4 000262B4 24080127 */  addiu $t0, $zero, 0x127
            /* 0262C4 000262C4 240F00B7 */  addiu $t7, $zero, 0xb7
            """
            addr1 = 0x0262B6
            addr2 = 0x0262C6

        elif stat == 3:
            """
            1p, All screens, player 1 time remaining
            /* 02A50C 0002A50C 24060157 */  addiu $a2, $zero, 0x157
            /* 02A510 0002A510 240700E6 */  addiu $a3, $zero, 0xe6
            """
            addr1 = 0x02A50E
            addr2 = 0x02A512

        x &= 0xFFFF
        x_bytes = x.to_bytes(2, byteorder='big')

        y &= 0xFFFF
        y_bytes = y.to_bytes(2, byteorder='big')

        self.data[addr1 : addr1 + 2] = x_bytes[0:2]
        self.data[addr2 : addr2 + 2] = y_bytes[0:2]

    def modify_stat_color(self, stat, r, g, b, a):
        if stat < 1 or stat > 3:
            print("stat error: Stat type must be between 1 and 3", file=sys.stderr)
            sys.exit(1)

        if stat == 1:
            """
            1p, Finale screen, player 1 name
            /* 02A3B8 0002A3B8 241800FF */  addiu $t8, $zero, 0xff
            /* 02A3BC 0002A3BC 241900FF */  addiu $t9, $zero, 0xff
            /* 02A3C0 0002A3C0 240800FF */  addiu $t0, $zero, 0xff
            /* 02A3C4 0002A3C4 240E00FF */  addiu $t6, $zero, 0xff
            """
            addr1 = 0x02A3BB
            addr2 = 0x02A3BF
            addr3 = 0x02A3C3
            addr4 = 0x02A3C7

        elif stat == 2:
            """
            1p,2p,3p,4p, All screens, player 1,2,3,4 line count
            /* 018B38 00018B38 241800FF */  addiu $t8, $zero, 0xff
            /* 018B3C 00018B3C 241900FF */  addiu $t9, $zero, 0xff
            /* 018B40 00018B40 240800FF */  addiu $t0, $zero, 0xff
            /* 018B44 00018B44 240900FF */  addiu $t1, $zero, 0xff
            """
            addr1 = 0x018B3B
            addr2 = 0x018B3F
            addr3 = 0x018B43
            addr4 = 0x018B47

        elif stat == 3:
            """
            1p, All screens, player 1 time remaining
            /* 02A4E8 0002A4E8 240D00FF */  addiu $t5, $zero, 0xff
            /* 02A4EC 0002A4EC 240F00FF */  addiu $t7, $zero, 0xff
            /* 02A4F0 0002A4F0 241800FF */  addiu $t8, $zero, 0xff
            /* 02A4F4 0002A4F4 241900FF */  addiu $t9, $zero, 0xff
            """
            addr1 = 0x02A4EB
            addr2 = 0x02A4EF
            addr3 = 0x02A4F3
            addr4 = 0x02A4F7

        r &= 0xFF
        g &= 0xFF
        b &= 0xFF
        a &= 0xFF

        self.data[addr1 : addr1 + 1] = bytes([r])
        self.data[addr2 : addr2 + 1] = bytes([g])
        self.data[addr3 : addr3 + 1] = bytes([b])
        self.data[addr4 : addr4 + 1] = bytes([a])

    def modify_initial_hold_piece(self, piece):
        if piece < 0 or piece > 6:
            print("ihp error: Piece type must be between 0 and 6", file=sys.stderr)
            sys.exit(1)

        addr1 = 0x02C868

        self.data[addr1 : addr1 + 3] = b'\x24\x0A\x00'   # addiu $t2, $zero, ...
        self.data[addr1 + 3 : addr1 + 4] = bytes([piece])
