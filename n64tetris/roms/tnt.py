import sys
import struct
from enum import Enum, auto

#from PIL import Image
#import lzo

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
        import lzo

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
        from PIL import Image

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
        import lzo

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
        from PIL import Image

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
        if stat < 1 or stat > 4:
            print("stat error: Stat type must be between 1 and 4", file=sys.stderr)
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

        elif stat == 4:
            """
            Seed
            """
            addr1 = self.seed_xpos_addr
            addr2 = self.seed_ypos_addr

        x &= 0xFFFF
        x_bytes = x.to_bytes(2, byteorder='big')

        y &= 0xFFFF
        y_bytes = y.to_bytes(2, byteorder='big')

        self.data[addr1 : addr1 + 2] = x_bytes[0:2]
        self.data[addr2 : addr2 + 2] = y_bytes[0:2]

    def modify_stat_color(self, stat, r, g, b, a):
        if stat < 1 or stat > 4:
            print("stat error: Stat type must be between 1 and 4", file=sys.stderr)
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

        elif stat == 4:
            """
            Seed
            """
            addr1 = self.seed_red_addr
            addr2 = self.seed_green_addr
            addr3 = self.seed_blue_addr
            addr4 = self.seed_alpha_addr

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

    # value must be in the set {2, 4, 6, 8}
    def modify_square_size(self, value):
        """
                                                                // For square size of 6
        function: FUN_8006a9f4
        /* 030D18 00030D18 2A210007 */ 	slti  $at, $s1,	7       // change to 5
        /* 030D28 00030D28 2A410011 */ 	slti  $at, $s2,	0x11    // change to 0xf
        /* 030DC4 00030DC4 2A210007 */ 	slti  $at, $s1,	7       // change to 5
        /* 030DD4 00030DD4 2A410011 */ 	slti  $at, $s2,	0x11    // change to 0xf

        function: FUN_8006a4ec
        /* 0307AC 000307AC 29C10007 */ 	 slti  $at, $t6, 7      // change to 5
        /* 0307B4 000307B4 29E10011 */ 	 slti  $at, $t7, 0x11   // change to 0xf
        /* 0307D4 000307D4 24100004 */ 	addiu $s0, $zero, 4     // change to 9
        /* 030814 00030814 240C0004 */ 	addiu $t4, $zero, 4     // change to 6
        /* 030828 00030828 240D0004 */ 	addiu $t5, $zero, 4     // change to 6
        /* 0308C8 000308C8 24010004 */ 	addiu $at, $zero, 4     // change to 9
        /* 0308F4 000308F4 26310018 */ 	addiu $s1, $s1,	0x18    // change to 0x10

        function: FUN_8006a740
        /* 0309E4 000309E4 25CFFFFD */  addiu $t7, $t6, -3      // change to -5
        /* 0309F8 000309F8 2719FFFD */  addiu $t9, $t8, -3      // change to -5
        /* 030A1C 00030A1C 29810007 */  slti  $at, $t4, 7       // change to 5
        /* 030A28 00030A28 240D0006 */  addiu $t5, $zero, 6     // change to 4
        /* 030A4C 00030A4C 2B010011 */  slti  $at, $t8, 0x11    // change to 0xf
        /* 030A58 00030A58 24190010 */  addiu $t9, $zero, 0x10  // change to 0xe

        function: FUN_8006b050
        /* 0313A0 000313A0 272CFFD4 */  addiu $t4, $t9, -0x2c   // change to -0x42
        /* 0313C0 000313C0 250BFFD4 */  addiu $t3, $t0, -0x2c   // change to -0x42

        function: FUN_8006a050
        /* 0304DC 000304DC 25680004 */  addiu $t0, $t3, 4       // change to 6
        /* 0304F4 000304F4 25CC0004 */  addiu $t4, $t6, 4       // change to 6
        /* 030530 00030530 240B0004 */  addiu $t3, $zero, 4     // change to 6
        /* 03053C 0003053C 24080004 */  addiu $t0, $zero, 4     // change to 6
        /* 030598 00030598 26F70018 */  addiu $s7, $s7, 0x18    // change to 0x10
        /* 0305A8 000305A8 240B0010 */  addiu $t3, $zero, 0x10  // change to 0x24
        """
        addr1 = 0x030D1B
        addr2 = 0x030D2B
        addr3 = 0x030DC7
        addr4 = 0x030DD7

        addr5 = 0x0307AF
        addr6 = 0x0307B7
        addr7 = 0x0307D7
        addr8 = 0x030817
        addr9 = 0x03082B
        addr10 = 0x0308CB
        addr11 = 0x0308F7

        addr12 = 0x0309E7
        addr13 = 0x0309FB
        addr14 = 0x030A1F
        addr15 = 0x030A2B
        addr16 = 0x030A4F
        addr17 = 0x030A5B

        addr18 = 0x0313A3
        addr19 = 0x0313C3

        addr20 = 0x0304DF
        addr21 = 0x0304F7
        addr22 = 0x030533
        addr23 = 0x03053F
        addr24 = 0x03059B
        addr25 = 0x0305AB

        self.data[addr1 : addr1 + 1] = bytes([11 - value])
        self.data[addr2 : addr2 + 1] = bytes([21 - value])
        self.data[addr3 : addr3 + 1] = bytes([11 - value])
        self.data[addr4 : addr4 + 1] = bytes([21 - value])

        self.data[addr5 : addr5 + 1] = bytes([11 - value])
        self.data[addr6 : addr6 + 1] = bytes([21 - value])
        self.data[addr7 : addr7 + 1] = bytes([value * value // 4])
        self.data[addr8 : addr8 + 1] = bytes([value])
        self.data[addr9 : addr9 + 1] = bytes([value])
        self.data[addr10 : addr10 + 1] = bytes([value * value // 4])
        self.data[addr11 : addr11 + 1] = bytes([(10 - value) * 4])

        self.data[addr12 : addr12 + 1] = bytes([257 - value])
        self.data[addr13 : addr13 + 1] = bytes([257 - value])
        self.data[addr14 : addr14 + 1] = bytes([11 - value])
        self.data[addr15 : addr15 + 1] = bytes([10 - value])
        self.data[addr16 : addr16 + 1] = bytes([21 - value])
        self.data[addr17 : addr17 + 1] = bytes([20 - value])

        self.data[addr18 : addr18 + 1] = bytes([256 - (value * 11)])
        self.data[addr19 : addr19 + 1] = bytes([256 - (value * 11)])

        self.data[addr20 : addr20 + 1] = bytes([value])
        self.data[addr21 : addr21 + 1] = bytes([value])
        self.data[addr22 : addr22 + 1] = bytes([value])
        self.data[addr23 : addr23 + 1] = bytes([value])
        self.data[addr24 : addr24 + 1] = bytes([(10 - value) * 4])
        self.data[addr25 : addr25 + 1] = bytes([value * value])

    def save_seed(self):
        addr1 = 0x0A4420
        addr2 = 0x099480
        addr3 = 0x0376AC
        menu = 0x0A69A4

        """
        Jump back in:
          0376AC + 8
          0376B4
          0376B4 + 039D80
          071434
          071434 / 4
          01C50D

        000a15f0  30 31 32 33 34 35 36 37  38 39 61 62 63 64 65 66  |0123456789abcdef|
        000a1600  00 00 00 00 30 31 32 33  34 35 36 37 38 39 41 42  |....0123456789AB|
        000a1610  43 44 45 46 00 00 00 00  00 00 00 00 00 00 00 00  |CDEF............|

        Convert from rom address to game address:
          A1604 + 80039D80
          800DB384
        """

        self.data[menu : menu + 7] = b'VALUES\x00'

        self.data[addr1 : addr1 + 15] = b'\x0ASEED\x0A        \x0A'  # allocate space for seed value (8 chars)
        val_addr = addr1 + 15
        val_addr = (val_addr - 1) - 8  # start position of value
        self.data[addr2 : addr2 + 3] = b'\x01\x01\x00'  # font size: big, big, small

        self.data[addr1 + 15 : addr1 + 17] = b'\x0A\x00'
        self.data[addr2 + 3 : addr2 + 4] = b'\x01'  # font size: big

        addr4 = self.word_align(addr1 + 17)
        jmp_addr = addr4 + 0x039D80
        jmp_addr = jmp_addr >> 2
        jmp_opc = 0b000010
        jmp_inst = (jmp_opc << 26) | jmp_addr
        jmp_inst = jmp_inst.to_bytes(4, byteorder='big')

        # Jump out
        self.data[addr3 : addr3 + 4] = jmp_inst                   # j ...

        # Copy $t7 (seed) into $t6
        self.data[addr4 : addr4 + 4] = b'\x01\xE0\x70\x25'        # move $t6, $t7

        # $t1 is position after val_addr in ram
        after_val_addr = val_addr + 8
        after_val_addr = after_val_addr + 0x80039D80
        after_val_addr_hi = after_val_addr >> 16
        after_val_addr_lo = after_val_addr & 0xFFFF
        after_val_addr_hi = after_val_addr_hi.to_bytes(2, byteorder='big')
        after_val_addr_lo = after_val_addr_lo.to_bytes(2, byteorder='big')
        self.data[addr4 + 4 : addr4 + 6] = b'\x3C\x09'            # lui $t1, ...
        self.data[addr4 + 6 : addr4 + 8] = after_val_addr_hi
        self.data[addr4 + 8 : addr4 + 10] = b'\x35\x29'           # ori $t1, $t1, ...
        self.data[addr4 + 10 : addr4 + 12] = after_val_addr_lo

        # $t2 is "0123456789ABCDEF"
        self.data[addr4 + 12 : addr4 + 16] = b'\x3C\x0A\x80\x0D'  # lui $t2, 0x800D
        self.data[addr4 + 16 : addr4 + 20] = b'\x35\x4A\xB3\x84'  # ori $t2, $t2, 0xB384

        self.data[addr4 + 20 : addr4 + 24] = b'\x24\x0C\x00\x08'  # addiu $t4, $zero, 0x8
        # $t6 is seed
        self.data[addr4 + 24 : addr4 + 28] = b'\x31\xC8\x00\x0F'  # andi $t0, $t6, 0xF
        self.data[addr4 + 28 : addr4 + 32] = b'\x01\x0A\x58\x21'  # addu $t3, $t0, $t2
        self.data[addr4 + 32 : addr4 + 36] = b'\x91\x68\x00\x00'  # lbu $t0, ($t3)
        self.data[addr4 + 36 : addr4 + 40] = b'\x00\x0E\x71\x02'  # srl $t6, $t6, 4
        self.data[addr4 + 40 : addr4 + 44] = b'\x25\x29\xFF\xFF'  # addiu $t1, $t1, -1
        self.data[addr4 + 44 : addr4 + 48] = b'\x25\x8C\xFF\xFF'  # addiu $t4, $t4, -1
        self.data[addr4 + 48 : addr4 + 52] = b'\x1D\x80\xFF\xF9'  # bgtz $t4, 0xFFF9
        self.data[addr4 + 52 : addr4 + 56] = b'\xA1\x28\x00\x00'  # sb $t0, ($t1)

        # Store seed into 0x800DE90C
        self.data[addr4 + 56 : addr4 + 60] = b'\x3C\x0D\x80\x0D'  # lui $t5, 0x800D
        self.data[addr4 + 60 : addr4 + 64] = b'\x35\xAD\xE9\x0C'  # ori $t5, $t5, 0xE90C
        self.data[addr4 + 64 : addr4 + 68] = b'\xAD\xAF\x00\x00'  # sw $t7, ($t5)

        # Jump back in
        self.data[addr4 + 68 : addr4 + 72] = b'\x08\x01\xC5\x0D'  # j 0x071434
        self.data[addr4 + 72 : addr4 + 76] = b'\x00\x00\x00\x00'  # nop

        # "%08X" is stored at 0x800DE907
        addr5 = 0x0A4B87
        self.insert_bytes(addr5, b'%08X\x00')

    def display_seed(self):
        addr1 = 0x0182D8
        addr2 = 0x0A4480

        jal_addr = addr2 + 0x039D80
        jal_addr = jal_addr >> 2
        jal_opc = 0b000011
        jal_inst = (jal_opc << 26) | jal_addr
        jal_inst = jal_inst.to_bytes(4, byteorder='big')

        self.asm_addr = addr1
        self.asm(jal_inst)    # jal     func_800DE200
        self.asm('00000000')  # nop
        self.asm('00000000')  # nop
        self.asm('00000000')  # nop
        self.asm('00000000')  # nop
        self.asm('00000000')  # nop
        self.asm('00000000')  # nop
        self.asm('00000000')  # nop
        self.asm('00000000')  # nop
        self.asm('00000000')  # nop

        self.asm_addr = addr2
        self.asm('27BDFFC8')  # addiu   $sp, $sp, -0x38
        self.asm('AFBF0024')  # sw      $ra, 0x24($sp)
        self.asm('3C08800D')  # lui     $t0, 0x800D
        self.asm('3508E90C')  # ori     $t0, $t0, 0xE90C
        self.asm('8D060000')  # lw      $a2, ($t0)              ; seed
        self.asm('3C05800D')  # lui     $a1, 0x800D
        self.asm('34A5E907')  # ori     $a1, $a1, 0xE907        ; "%08X"
        self.asm('0C02D8B5')  # jal     func_800B62D4           ; sprintf()
        self.asm('27A40028')  # addiu   $a0, $sp, 0x28          ; stringSeed
        self.asm('3C04800E')  # lui     $a0, 0x800E
        self.asm('0C016EFF')  # jal     func_8005BBFC
        self.asm('348420C0')  # ori     $a0, $a0, 0x20C0
        self.asm('3C058011')  # lui     $a1, 0x8011
        self.asm('27AB0028')  # addiu   $t3, $sp, 0x28          ; stringSeed
        self.asm('3C04800E')  # lui     $a0, 0x800E
        self.asm('241800FF')  # addiu   $t8, $zero, 0xFF        ; red
        self.seed_red_addr = self.asm_addr - 1
        self.asm('240F00FF')  # addiu   $t7, $zero, 0xFF        ; green
        self.seed_green_addr = self.asm_addr - 1
        self.asm('241900FF')  # addiu   $t9, $zero, 0xFF        ; blue
        self.seed_blue_addr = self.asm_addr - 1
        self.asm('240E00FF')  # addiu   $t6, $zero, 0xFF        ; alpha
        self.seed_alpha_addr = self.asm_addr - 1
        self.asm('AFAE0020')  # sw      $t6, 0x20($sp)
        self.asm('AFB9001C')  # sw      $t9, 0x1C($sp)
        self.asm('AFAF0018')  # sw      $t7, 0x18($sp)
        self.asm('AFB80014')  # sw      $t8, 0x14($sp)
        self.asm('348420C0')  # ori     $a0, $a0, 0x20C0
        self.asm('AFAB0010')  # sw      $t3, 0x10($sp)
        self.asm('24060006')  # addiu   $a2, $zero, 0x6         ; x position
        self.seed_xpos_addr = self.asm_addr - 2
        self.asm('2407011A')  # addiu   $a3, $zero, 0x11A       ; y position
        self.seed_ypos_addr = self.asm_addr - 2
        self.asm('0C01DE58')  # jal     func_80077960
        self.asm('34A50A08')  # ori     $a1, $a1, 0xA08
        self.asm('3C04800E')  # lui     $a0, 0x800E
        self.asm('0C016F90')  # jal     func_8005BE40
        self.asm('348420C0')  # ori     $a0, $a0, 0x20C0
        self.asm('8FBF0024')  # lw      $ra, 0x24($sp)
        self.asm('27BD0038')  # addiu   $sp, $sp, 0x38
        self.asm('03E00008')  # jr      $ra
        self.asm('00000000')  # nop
