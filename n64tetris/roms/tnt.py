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
    def __init__(self, verbose=False, force=False):
        super().__init__(game_code=b'NRIE', verbose=verbose, force=force)
        self.decoders = (self.h2o_decode,)
        self.next_sub_addr = 0x0F5A50  # 8012F7D0 (original start of heap)

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
                im = Image.frombytes('LA', (asset_info['width'], asset_info['height']), utils.ia44_to_ia88(raw[8:]))

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
            im = im.convert(mode='LA')

            raw = bytearray()
            raw[:4] = struct.pack('>2H', asset_info['width'], asset_info['height'])
            raw[4:8] = b'\x00\x02\x00\x00'
            raw[8:] = utils.ia88_to_ia44(im.tobytes())
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
        """
        In FUN_80052114, replace:
            local_1c = extraout_v1;
        """
        addr1 = 0x018624
        addr2 = 0x018650
        addr3 = 0x018658

        value &= 0xFFFFFFFF
        seed = value.to_bytes(4, byteorder='big')

        self.insert_bytes(addr1, b'\x3C\x11' + seed[0 : 2])  # lui     $s1, ...
        self.insert_bytes(addr2, b'\x36\x31' + seed[2 : 4])  # ori     $s1, $s1, ...

        self.asm_addr = addr3
        self.asm('AFB10054')  # sw      $s1, 0x54($sp)

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

    def old_save_seed(self):
        addr1 = 0x0A4420
        addr2 = 0x099480
        addr3 = 0x0187BC
        menu = 0x0A69A4

        """
        000a15f0  30 31 32 33 34 35 36 37  38 39 61 62 63 64 65 66  |0123456789abcdef|
        000a1600  00 00 00 00 30 31 32 33  34 35 36 37 38 39 41 42  |....0123456789AB|
        000a1610  43 44 45 46 00 00 00 00  00 00 00 00 00 00 00 00  |CDEF............|
        """

        self.insert_bytes(menu, b'VALUES\x00')

        # allocate space for seed value (8 chars)
        addr1_ = self.insert_bytes(addr1, b'\x0ASEED\x0A        \x0A')
        after_val_addr = addr1_ - 1
        # font size: big, big, small
        addr2_ = self.insert_bytes(addr2, b'\x01\x01\x00')

        # end text
        addr1_ = self.insert_bytes(addr1_, b'\x0A\x00')
        # font size: big
        self.insert_bytes(addr2_, b'\x01')

        #addr4 = self.word_align(addr1_)
        addr4 = self.next_sub_addr
        jal_inst = self.jal(self.virt(addr4))

        # Jump out
        self.asm_addr = addr3
        self.asm('8FA40054')  # lw      $a0, 0x54($sp)
        self.asm(jal_inst)    # jal     ...
        self.asm('00000000')  # nop

        self.asm_addr = addr4

        # Store seed into 0x8013AD7C
        self.asm('3C0D8013')  # lui     $t5, 0x8013
        self.asm('35ADAD7C')  # ori     $t5, $t5, 0xAD7C
        self.asm('ADA40000')  # sw      $a0, ($t5)

        # Copy $a0 (seed) into $t6
        self.asm('00807025')  # or      $t6, $a0, $zero

        # $t1 is position after val in ram
        vaddr_bytes = self.virt(after_val_addr).to_bytes(4, byteorder='big')
        self.asm(b'\x3C\x09' + vaddr_bytes[0 : 2])  # lui     $t1, ...
        self.asm(b'\x35\x29' + vaddr_bytes[2 : 4])  # ori     $t1, $t1, ...

        # $t2 is "0123456789ABCDEF"
        self.asm('3C0A800D')  # lui     $t2, 0x800D
        self.asm('354AB384')  # ori     $t2, $t2, 0xB384

        self.asm('240C0008')  # addiu   $t4, $zero, 0x8
        # $t6 is seed
        self.asm('31C8000F')  # andi    $t0, $t6, 0xF
        self.asm('010A5821')  # addu    $t3, $t0, $t2
        self.asm('91680000')  # lbu     $t0, ($t3)
        self.asm('000E7102')  # srl     $t6, $t6, 4
        self.asm('2529FFFF')  # addiu   $t1, $t1, -1
        self.asm('258CFFFF')  # addiu   $t4, $t4, -1
        self.asm('1D80FFF9')  # bgtz    $t4, -0x1C
        self.asm('A1280000')  # sb      $t0, ($t1)

        # Jump back in
        self.asm('03E00008')  # jr      $ra
        self.asm('00000000')  # nop
        print(f"{self.asm_addr:08X}")
        self.next_sub_addr = self.asm_addr

        addr5 = 0x100FF7  # 8013AD77
        self.insert_bytes(addr5, b'%08X\x00')

    def move_heap(self):
        """
        Make room for new code.
        Note that 1 MB from 0x1000 of the rom is loaded into ram (ie, 0x1000 to 0x101000).
        Move start of heap to 0x8013AD80 (rom equivalent: 0x101000).
        Original start of heap is 0x8012F7D0.
        This gives us 0x8013AD80 - 0x8012F7D0 = 46512 bytes to add new code and static data.
        """
        self.asm_addr = 0x0106C4
        self.asm('3C088013')  # lui     $t0, 0x8013
        self.asm_addr = 0x0106D0
        self.asm('3508AD80')  # ori     $t0, $t0, 0xAD80

        # Unused code
        #self.asm_addr = 0x00FDA8
        #self.asm('3C0F8013')  # lui     $t7, 0x8013
        #self.asm('35EFAD80')  # ori     $t7, $t7, 0xAD80

    def func_display_text(self):
        addr = self.next_sub_addr
        self.jal_display_text = self.jal(self.virt(addr))

        self.asm_addr = addr
        self.asm('27bdffd8')  # addiu   $sp, $sp, -0x28
        self.asm('afbf0024')  # sw      $ra, 0x24($sp)

        self.asm('afa60010')  # sw      $a2, 0x10($sp)          ; str
        self.asm('00a03825')  # or      $a3, $a1, $zero         ; y
        self.asm('00803025')  # or      $a2, $a0, $zero         ; x
        self.asm('240900ff')  # addiu   $t1, $zero, 0xFF        ; red
        self.asm('240a00ff')  # addiu   $t2, $zero, 0xFF        ; green
        self.asm('240b00ff')  # addiu   $t3, $zero, 0xFF        ; blue
        self.asm('240c00ff')  # addiu   $t4, $zero, 0xFF        ; alpha
        self.asm('afac0020')  # sw      $t4, 0x20($sp)
        self.asm('afab001c')  # sw      $t3, 0x1C($sp)
        self.asm('afaa0018')  # sw      $t2, 0x18($sp)
        self.asm('afa90014')  # sw      $t1, 0x14($sp)
        self.asm('3c058011')  # lui     $a1, 0x8011
        self.asm('34a50a08')  # ori     $a1, $a1, 0xA08         ; font
        self.asm('3c04800e')  # lui     $a0, 0x800E
        self.asm('0c01de58')  # jal     func_80077960           ; display_text
        self.asm('348420c0')  # ori     $a0, $a0, 0x20C0        ; ?

        self.asm('8fbf0024')  # lw      $ra, 0x24($sp)
        self.asm('03e00008')  # jr      $ra
        self.asm('27bd0028')  # addiu   $sp, $sp, 0x28
        self.next_sub_addr = self.asm_addr

    def add_utility_functions(self):
        self.func_display_text()

    def init_static_data(self):
        # reserves space for seed
        addr = 0x100FFC  # 8013AD7C
        self.insert_bytes(addr, b'\x00' * 4)

        addr = 0x100FF7  # 8013AD77
        self.insert_bytes(addr, b'%08X\x00')

        addr = 0x100FF1  # 8013AD71
        self.insert_bytes(addr, b'%c %c\x00')

        addr = 0x100FDC  # 8013AD5C
        self.insert_bytes(addr, b'%d %d %d %d %d %d %d\x00')

        # x,y - piece_count, 2p, p2
        addr = 0x100FD8  # 8013AD58
        self.insert_bytes(addr, b'\x00\xA9\x00\xF7')

        # x,y - piece_count, 2p, p1
        addr = 0x100FD4  # 8013AD54
        self.insert_bytes(addr, b'\x00\xA9\x00\xA8')

        # x,y - piece_count, 1p, p1
        addr = 0x100FD0  # 8013AD50
        self.insert_bytes(addr, b'\x01\x27\x00\x9B')

        # x,y - remaining_pieces, 2p, p2
        #addr = 0x100FCC  # 8013AD4C
        #self.insert_bytes(addr, b'\x00\xF0\x00\xFC')

        # x,y - remaining_pieces, 2p, p1
        #addr = 0x100FC8  # 8013AD48
        #self.insert_bytes(addr, b'\x00\x2F\x00\xFC')

        # x,y - remaining_pieces, 1p, p1
        addr = 0x100FC4  # 8013AD44
        self.insert_bytes(addr, b'\x00\x35\x00\x66')

        # x,y - extra_lookahead, 2p, p2
        addr = 0x100FC0  # 8013AD40
        self.insert_bytes(addr, b'\x00\xD2\x00\x90')

        # x,y - extra_lookahead, 2p, p1
        addr = 0x100FBC  # 8013AD3C
        self.insert_bytes(addr, b'\x00\xAC\x00\x90')

        # x,y - extra_lookahead, 1p, p1
        addr = 0x100FB8  # 8013AD38
        self.insert_bytes(addr, b'\x00\xD0\x00\x90')

        # initializes linked list and reserves space for head item
        # register_piece_count() places its item here
        addr = 0x100FA4  # 8013AD24
        self.insert_bytes(addr, b'\x00' * 20)

        # register_remaining_pieces() places its item here
        addr = 0x100F90  # 8013AD10
        self.insert_bytes(addr, b'\x00' * 20)

        # register_extra_lookahead() places its item here
        addr = 0x100F7C  # 8013ACFC
        self.insert_bytes(addr, b'\x00' * 20)

    def save_seed(self):
        """
        In FUN_80052114, replace:
            FUN_80041260();
        """
        addr = self.next_sub_addr
        jal_inst = self.jal(self.virt(addr))
        self.asm_addr = 0x0187AC
        self.asm(jal_inst)    # jal     ...
        self.asm('8fa40054')  # lw      $a0, 0x54($sp)          ; seed

        self.asm_addr = addr
        self.asm('27bdffe8')  # addiu   $sp, $sp, -0x18
        self.asm('afa40018')  # sw      $a0, 0x18($sp)          ; seed
        self.asm('afbf0014')  # sw      $ra, 0x14($sp)

        self.asm('8fa80018')  # lw      $t0, 0x18($sp)          ; seed
        self.asm('3c098013')  # lui     $t1, 0x8013
        self.asm('3529ad7c')  # ori     $t1, $t1, 0xAD7C
        self.asm('ad280000')  # sw      $t0, ($t1)              ; store seed into 8013AD7C

        """
        # store 0x9 into 46 shorts beginning at 80110A0C
        self.asm('3c088011')  # lui     $t0, 0x8011
        self.asm('35080a0c')  # ori     $t0, $t0, 0x0A0C
        self.asm('2409002e')  # addiu   $t1, $zero, 0x2E        ; 46 chars in font_c
        self.asm('240a0009')  # addiu   $t2, $zero, 0x9
        self.asm('a50a0000')  # sh      $t2, ($t0)              ; sets char width to 9
        self.asm('2529ffff')  # addiu   $t1, $t1, -1
        self.asm('1d20fffd')  # bgtz    $t1, -0xC
        self.asm('25080002')  # addiu   $t0, $t0, 2
        """

        """
        FUN_80041260();
        /* 0187AC 8005252C 0C010498 */  jal   func_80041260
        /* 0187B0 80052530 00000000 */  nop
        """
        self.asm('0c010498')  # jal     func_80041260
        self.asm('00000000')  # nop

        self.asm('8fbf0014')  # lw      $ra, 0x14($sp)
        self.asm('03e00008')  # jr      $ra
        self.asm('27bd0018')  # addiu   $sp, $sp, 0x18
        self.next_sub_addr = self.asm_addr

    def display_seed(self):
        """
        In FUN_80051F30, replace:
            FUN_80072A84();
        """
        addr = self.next_sub_addr
        jal_inst = self.jal(self.virt(addr))
        self.asm_addr = 0x01821C
        self.asm(jal_inst)    # jal     ...

        self.asm_addr = addr
        self.asm('27bdffc8')  # addiu   $sp, $sp, -0x38
        self.asm('afb00034')  # sw      $s0, 0x34($sp)
        self.asm('afbf0030')  # sw      $ra, 0x30($sp)

        """
        FUN_80072A84();
        /* 01821C 80051F9C 0C01CAA1 */  jal   func_80072A84
        """
        self.asm('0c01caa1')  # jal     func_80072A84
        self.asm('00000000')  # nop

        self.asm('3c088013')  # lui     $t0, 0x8013
        self.asm('3508ad7c')  # ori     $t0, $t0, 0xAD7C
        self.asm('8d060000')  # lw      $a2, ($t0)              ; seed
        self.asm('3c058013')  # lui     $a1, 0x8013
        self.asm('34a5ad77')  # ori     $a1, $a1, 0xAD77        ; "%08X"
        self.asm('0c02d8b5')  # jal     func_800B62D4           ; sprintf()
        self.asm('27a40024')  # addiu   $a0, $sp, 0x24          ; s_seed

        self.asm('3c10800e')  # lui     $s0, 0x800E
        self.asm('361020c0')  # ori     $s0, $s0, 0x20C0        ; ?
        self.asm('0c016eff')  # jal     func_8005BBFC           ; open_display?
        self.asm('02002025')  # or      $a0, $s0, $zero         ; copy $s0 to $a0

        self.asm('2406000c')  # addiu   $a2, $zero, 0xC         ; x position for seed
        self.seed_xpos_addr = self.asm_addr - 2
        self.asm('2407011d')  # addiu   $a3, $zero, 0x11D       ; y position for seed
        self.seed_ypos_addr = self.asm_addr - 2
        self.asm('27a80024')  # addiu   $t0, $sp, 0x24          ; s_seed
        self.asm('240900ff')  # addiu   $t1, $zero, 0xFF        ; red
        self.seed_red_addr = self.asm_addr - 1
        self.asm('240a00ff')  # addiu   $t2, $zero, 0xFF        ; green
        self.seed_green_addr = self.asm_addr - 1
        self.asm('240b00ff')  # addiu   $t3, $zero, 0xFF        ; blue
        self.seed_blue_addr = self.asm_addr - 1
        self.asm('240c009f')  # addiu   $t4, $zero, 0x9F        ; alpha
        self.seed_alpha_addr = self.asm_addr - 1
        self.asm('afac0020')  # sw      $t4, 0x20($sp)
        self.asm('afab001c')  # sw      $t3, 0x1C($sp)
        self.asm('afaa0018')  # sw      $t2, 0x18($sp)
        self.asm('afa90014')  # sw      $t1, 0x14($sp)
        self.asm('afa80010')  # sw      $t0, 0x10($sp)
        self.asm('3c058011')  # lui     $a1, 0x8011
        self.asm('34a50a08')  # ori     $a1, $a1, 0xA08         ; font
        self.asm('0c01de58')  # jal     func_80077960           ; display_text
        self.asm('02002025')  # or      $a0, $s0, $zero         ; copy $s0 to $a0

        self.asm('0c016f90')  # jal     func_8005BE40           ; close_display?
        self.asm('02002025')  # or      $a0, $s0, $zero         ; copy $s0 to $a0

        self.asm('8fbf0030')  # lw      $ra, 0x30($sp)
        self.asm('8fb00034')  # lw      $s0, 0x34($sp)
        self.asm('03e00008')  # jr      $ra
        self.asm('27bd0038')  # addiu   $sp, $sp, 0x38
        self.next_sub_addr = self.asm_addr

    def heap_alloc_player_data(self):
        """
        Allocate extra heap space for per-player data.  Increase by 24 bytes.

        In FUN_80052114, change 0x6848 to 0x6860
            FUN_8007E03C(0x6848);

        /* 0186E8 80052468 0C01F80F */  jal   func_8007E03C
        /* 0186EC 8005246C 24046848 */  addiu $a0, $zero, 0x6848
        """
        self.insert_bytes(0x0186EE, b'\x68\x60')

    def init_player_stats(self):
        """
        In FUN_800547F0, replace:
            FUN_800713F0(param_1 + 0x6690, &local_4);
        """
        addr = self.next_sub_addr
        jal_inst = self.jal(self.virt(addr))
        self.asm_addr = 0x01AACC
        self.asm(jal_inst)    # jal     ...

        self.asm_addr = addr
        self.asm('27BDFFE0')  # addiu   $sp, $sp, -0x20
        self.asm('AFBF001C')  # sw      $ra, 0x1C($sp)
        self.asm('AFA40020')  # sw      $a0, 0x20($sp)          ; player_data + 0x6690
        self.asm('AFA50024')  # sw      $a1, 0x24($sp)
        self.asm('AFB00018')  # sw      $s0, 0x18($sp)

        self.asm('8FA80020')  # lw      $t0, 0x20($sp)
        self.asm('250801B8')  # addiu   $t0, $t0, 0x1B8
        self.asm('AFA80014')  # sw      $t0, 0x14($sp)          ; player_data + 0x6848

        self.asm('3C098011')  # lui     $t1, 0x8011
        self.asm('3529EF20')  # ori     $t1, $t1, 0xEF20
        self.asm('912A0000')  # lbu     $t2, ($t1)              ; num_players
        self.asm('2D4B0003')  # sltiu   $t3, $t2, 0x3
        self.asm('15600002')  # bne     $t3, $zero, 0x8         ; branch if num_players < 3
        self.asm('254AFFFF')  # addiu   $t2, $t2, -1
        self.asm('240A0003')  # addiu   $t2, $zero, 0x3

        # branch target for "num_players < 3"
        self.asm('3C098011')  # lui     $t1, 0x8011
        self.asm('3529EF21')  # ori     $t1, $t1, 0xEF21
        self.asm('912B0000')  # lbu     $t3, ($t1)              ; cur_player
        self.asm('016A5821')  # addu    $t3, $t3, $t2
        self.asm('000B5880')  # sll     $t3, $t3, 0x2
        self.asm('AFAB0010')  # sw      $t3, 0x10($sp)          ; np_cp

        # traverse linked list
        self.asm('3C088013')  # lui     $t0, 0x8013
        self.asm('3508AD24')  # ori     $t0, $t0, 0xAD24        ; head of linked list

        # branch target for "next_item != 0"
        self.asm('8d090008')  # lw      $t1, 0x8($t0)           ; item_init_func
        self.asm('11200007')  # beq     $t1, $zero, 0x1C        ; branch if item_init_func == 0
        self.asm('8d100000')  # lw      $s0, ($t0)              ; next_item
        self.asm('8d0a0004')  # lw      $t2, 0x4($t0)           ; item_flags
        self.asm('11400004')  # beq     $t2, $zero, 0x10        ; branch if item_flags == 0
        self.asm('00000000')  # nop
        self.asm('8fa50010')  # lw      $a1, 0x10($sp)          ; np_cp
        self.asm('0120f809')  # jalr    $t1                     ; call item_init_func
        self.asm('8fa40014')  # lw      $a0, 0x14($sp)          ; player_data + 0x6848

        # branch target for "item_init_func == 0" OR "item_flags == 0"
        self.asm('1600fff6')  # bne     $s0, $zero, -0x28       ; branch if next_item != 0
        self.asm('02004025')  # or      $t0, $s0, $zero         ; copy $s0 to $t0

        """
        FUN_800713F0(param_1 + 0x6690, &local_4);
        /* 01AACC 8005484C 0C01C4FC */  jal   func_800713F0
        """
        self.asm('8FA50024')  # lw      $a1, 0x24($sp)
        self.asm('0C01C4FC')  # jal     func_800713F0
        self.asm('8FA40020')  # lw      $a0, 0x20($sp)

        self.asm('8FBF001C')  # lw      $ra, 0x1C($sp)
        self.asm('8FB00018')  # lw      $s0, 0x18($sp)
        self.asm('03E00008')  # jr      $ra
        self.asm('27BD0020')  # addiu   $sp, $sp, 0x20
        self.next_sub_addr = self.asm_addr

    def update_player_stats(self):
        """
        In FUN_80071394, replace:
            FUN_80071238(param_1);
        """
        addr = self.next_sub_addr
        jal_inst = self.jal(self.virt(addr))
        self.asm_addr = 0x037624
        self.asm(jal_inst)    # jal     ...

        self.asm_addr = addr
        self.asm('27BDFFE0')  # addiu   $sp, $sp, -0x20
        self.asm('AFBF001C')  # sw      $ra, 0x1C($sp)
        self.asm('AFA40020')  # sw      $a0, 0x20($sp)          ; player_data + 0x6690
        self.asm('AFB00018')  # sw      $s0, 0x18($sp)

        self.asm('8FA80020')  # lw      $t0, 0x20($sp)
        self.asm('250801B8')  # addiu   $t0, $t0, 0x1B8
        self.asm('AFA80014')  # sw      $t0, 0x14($sp)          ; player_data + 0x6848

        # traverse linked list
        self.asm('3C088013')  # lui     $t0, 0x8013
        self.asm('3508AD24')  # ori     $t0, $t0, 0xAD24        ; head of linked list

        # branch target for "next_item != 0"
        self.asm('8d09000c')  # lw      $t1, 0xC($t0)           ; item_update_func
        self.asm('11200006')  # beq     $t1, $zero, 0x18        ; branch if item_update_func == 0
        self.asm('8d100000')  # lw      $s0, ($t0)              ; next_item
        self.asm('8d0a0004')  # lw      $t2, 0x4($t0)           ; item_flags
        self.asm('11400003')  # beq     $t2, $zero, 0xC         ; branch if item_flags == 0
        self.asm('00000000')  # nop
        self.asm('0120f809')  # jalr    $t1                     ; call item_update_func
        self.asm('8fa40014')  # lw      $a0, 0x14($sp)          ; player_data + 0x6848

        # branch target for "item_update_func == 0" OR "item_flags == 0"
        self.asm('1600fff7')  # bne     $s0, $zero, -0x24       ; branch if next_item != 0
        self.asm('02004025')  # or      $t0, $s0, $zero         ; copy $s0 to $t0

        """
        FUN_80071238(param_1);
        /* 037624 800713A4 0C01C48E */  jal   func_80071238
        """
        self.asm('0C01C48E')  # jal     func_80071238
        self.asm('8FA40020')  # lw      $a0, 0x20($sp)

        self.asm('8FBF001C')  # lw      $ra, 0x1C($sp)
        self.asm('8FB00018')  # lw      $s0, 0x18($sp)
        self.asm('03E00008')  # jr      $ra
        self.asm('27BD0020')  # addiu   $sp, $sp, 0x20
        self.next_sub_addr = self.asm_addr

    def display_player_stats(self):
        """
        In FUN_8005447C, replace:
            FUN_80052A00(param_1 + 0x6808);
        """
        addr = self.next_sub_addr
        jal_inst = self.jal(self.virt(addr))
        self.asm_addr = 0x01A79C
        self.asm(jal_inst)    # jal     ...

        self.asm_addr = addr
        self.asm('27BDFFE0')  # addiu   $sp, $sp, -0x20
        self.asm('AFBF001C')  # sw      $ra, 0x1C($sp)
        self.asm('AFA40020')  # sw      $a0, 0x20($sp)          ; player_data + 0x6808
        self.asm('AFB00018')  # sw      $s0, 0x18($sp)

        """
        FUN_80052A00(param_1 + 0x6808);
        /* 01A79C 8005451C 0C014A80 */  jal   func_80052A00
        """
        self.asm('0C014A80')  # jal     func_80052A00
        self.asm('8FA40020')  # lw      $a0, 0x20($sp)

        self.asm('3C04800E')  # lui     $a0, 0x800E
        self.asm('0C016EFF')  # jal     func_8005BBFC           ; open_display?
        self.asm('348420C0')  # ori     $a0, $a0, 0x20C0        ; ?

        self.asm('8FA80020')  # lw      $t0, 0x20($sp)
        self.asm('25080040')  # addiu   $t0, $t0, 0x40
        self.asm('AFA80014')  # sw      $t0, 0x14($sp)          ; player_data + 0x6848
        self.asm('3C098011')  # lui     $t1, 0x8011
        self.asm('3529EF20')  # ori     $t1, $t1, 0xEF20
        self.asm('912A0000')  # lbu     $t2, ($t1)
        self.asm('afaa0010')  # sw      $t2, 0x10($sp)          ; num_players

        # traverse linked list
        self.asm('3C088013')  # lui     $t0, 0x8013
        self.asm('3508AD24')  # ori     $t0, $t0, 0xAD24        ; head of linked list

        # branch target for "next_item != 0"
        self.asm('8d090010')  # lw      $t1, 0x10($t0)          ; item_display_func
        self.asm('11200007')  # beq     $t1, $zero, 0x1C        ; branch if item_display_func == 0
        self.asm('8d100000')  # lw      $s0, ($t0)              ; next_item
        self.asm('8d0a0004')  # lw      $t2, 0x4($t0)           ; item_flags
        self.asm('11400004')  # beq     $t2, $zero, 0x10        ; branch if item_flags == 0
        self.asm('00000000')  # nop
        self.asm('8fa50010')  # lw      $a1, 0x10($sp)          ; num_players
        self.asm('0120f809')  # jalr    $t1                     ; call item_display_func
        self.asm('8fa40014')  # lw      $a0, 0x14($sp)          ; player_data + 0x6848

        # branch target for "item_display_func == 0" OR "item_flags == 0"
        self.asm('1600fff6')  # bne     $s0, $zero, -0x28       ; branch if next_item != 0
        self.asm('02004025')  # or      $t0, $s0, $zero         ; copy $s0 to $t0

        self.asm('3C04800E')  # lui     $a0, 0x800E
        self.asm('0C016F90')  # jal     func_8005BE40           ; close_display?
        self.asm('348420C0')  # ori     $a0, $a0, 0x20C0        ; ?

        self.asm('8FBF001C')  # lw      $ra, 0x1C($sp)
        self.asm('8FB00018')  # lw      $s0, 0x18($sp)
        self.asm('03E00008')  # jr      $ra
        self.asm('27BD0020')  # addiu   $sp, $sp, 0x20
        self.next_sub_addr = self.asm_addr

    def ll_add_item(self, this_item_addr, next_item_addr, item_flags, item_init_func_addr, item_update_func_addr, item_display_func_addr):
        # next_item
        if next_item_addr is None:
            self.insert_bytes(this_item_addr, int(0).to_bytes(4, byteorder='big'))
        else:
            self.insert_bytes(this_item_addr, self.virt(next_item_addr).to_bytes(4, byteorder='big'))

        # item_flags
        self.insert_bytes(this_item_addr + 4, item_flags.to_bytes(4, byteorder='big'))

        # item_init_func
        if item_init_func_addr is None:
            self.insert_bytes(this_item_addr + 8, int(0).to_bytes(4, byteorder='big'))
        else:
            self.insert_bytes(this_item_addr + 8, self.virt(item_init_func_addr).to_bytes(4, byteorder='big'))

        # item_update_func
        if item_update_func_addr is None:
            self.insert_bytes(this_item_addr + 12, int(0).to_bytes(4, byteorder='big'))
        else:
            self.insert_bytes(this_item_addr + 12, self.virt(item_update_func_addr).to_bytes(4, byteorder='big'))

        # item_display_func
        if item_display_func_addr is None:
            self.insert_bytes(this_item_addr + 16, int(0).to_bytes(4, byteorder='big'))
        else:
            self.insert_bytes(this_item_addr + 16, self.virt(item_display_func_addr).to_bytes(4, byteorder='big'))

    def ll_update_item_flags(self, this_item_addr, item_flags):
        self.insert_bytes(this_item_addr + 4, item_flags.to_bytes(4, byteorder='big'))

    def enable_piece_count(self):
        this_item_addr = 0x100FA4  # 8013AD24
        self.ll_update_item_flags(this_item_addr, 1)

    def register_piece_count(self):
        this_item_addr = 0x100FA4  # 8013AD24
        next_item_addr = 0x100F90  # 8013AD10

        self.asm_addr = self.next_sub_addr


        item_init_func_addr = self.asm_addr
        self.asm('2408fffc')  # addiu   $t0, $zero, -4          ; initialize piece_count to -4
        self.asm('ac880008')  # sw      $t0, 0x8($a0)           ; store piece_count at player_data + 0x6850

        self.asm('3c098013')  # lui     $t1, 0x8013
        self.asm('3529ad50')  # ori     $t1, $t1, 0xAD50        ; x,y lut for piece_count
        self.asm('01254821')  # addu    $t1, $t1, $a1           ; apply np_cp offset
        self.asm('8d2a0000')  # lw      $t2, ($t1)              ; x,y for piece_count

        self.asm('03e00008')  # jr      $ra
        self.asm('ac8a000c')  # sw      $t2, 0xC($a0)           ; store x,y at player_data + 0x6854


        item_update_func_addr = self.asm_addr
        self.asm('8c880008')  # lw      $t0, 0x8($a0)           ; piece_count
        self.asm('25080001')  # addiu   $t0, $t0, 1             ; increment piece_count

        self.asm('03E00008')  # jr      $ra
        self.asm('ac880008')  # sw      $t0, 0x8($a0)           ; store piece_count at player_data + 0x6850


        item_display_func_addr = self.asm_addr
        self.asm('27bdffc0')  # addiu   $sp, $sp, -0x40
        self.asm('afbf0024')  # sw      $ra, 0x24($sp)
        self.asm('afa40040')  # sw      $a0, 0x40($sp)          ; player_data + 0x6848
        self.asm('afa50044')  # sw      $a1, 0x44($sp)          ; num_players
        self.asm('afb0003c')  # sw      $s0, 0x3C($sp)

        self.asm('8fa80044')  # lw      $t0, 0x44($sp)          ; num_players
        self.asm('2d090003')  # sltiu   $t1, $t0, 0x3
        self.asm('1120000f')  # beq     $t1, $zero, 0x3C        ; branch if num_players >= 3
        self.asm('8fb00040')  # lw      $s0, 0x40($sp)          ; player_data + 0x6848

        self.asm('8e060008')  # lw      $a2, 0x8($s0)           ; piece_count
        self.asm('2408003f')  # addiu   $t0, $zero, 0x3F
        self.asm('00c8001b')  # divu    $zero, $a2, $t0
        self.asm('00003812')  # mflo    $a3                     ; num_bags
        self.asm('00004810')  # mfhi    $t1
        self.asm('afa90010')  # sw      $t1, 0x10($sp)          ; bag_count

        self.asm('3c058013')  # lui     $a1, 0x8013
        self.asm('34a5ad68')  # ori     $a1, $a1, 0xAD68        ; "%d %d %d"
        self.asm('0c02d8b5')  # jal     func_800B62D4           ; sprintf()
        self.asm('27a40028')  # addiu   $a0, $sp, 0x28          ; s_piece_count

        self.asm('27a60028')  # addiu   $a2, $sp, 0x28          ; s_piece_count
        self.asm('9605000e')  # lhu     $a1, 0xE($s0)           ; y position for piece_count
        self.asm(self.jal_display_text)  # jal     func_display_text
        self.asm('9604000c')  # lhu     $a0, 0xC($s0)           ; x position for piece_count

        # branch target for "num_players >= 3"
        self.asm('8fbf0024')  # lw      $ra, 0x24($sp)
        self.asm('8fb0003c')  # lw      $s0, 0x3C($sp)
        self.asm('03e00008')  # jr      $ra
        self.asm('27bd0040')  # addiu   $sp, $sp, 0x40


        self.next_sub_addr = self.asm_addr

        self.ll_add_item(this_item_addr, next_item_addr, 0, item_init_func_addr, item_update_func_addr, item_display_func_addr)

    def enable_remaining_pieces(self):
        this_item_addr = 0x100F90  # 8013AD10
        self.ll_update_item_flags(this_item_addr, 1)

    def register_remaining_pieces(self):
        this_item_addr = 0x100F90  # 8013AD10
        next_item_addr = 0x100F7C  # 8013ACFC

        self.asm_addr = self.next_sub_addr


        item_init_func_addr = self.asm_addr
        self.asm('24080001')  # addiu   $t0, $zero, 1           ; initialize total_remaining_pieces to 1
        self.asm('A0880007')  # sb      $t0, 0x7($a0)           ; store total_remaining_pieces at player_data + 0x684F

        self.asm('3C098013')  # lui     $t1, 0x8013
        self.asm('3529AD44')  # ori     $t1, $t1, 0xAD44        ; x,y lut for remaining_pieces
        self.asm('01254821')  # addu    $t1, $t1, $a1           ; apply np_cp offset
        self.asm('8D2A0000')  # lw      $t2, ($t1)              ; x,y for remaining_pieces

        self.asm('03E00008')  # jr      $ra
        self.asm('AC8A0010')  # sw      $t2, 0x10($a0)          ; store x,y at player_data + 0x6858


        item_update_func_addr = self.asm_addr
        self.asm('24880000')  # addiu   $t0, $a0, 0x0           ; remaining_pieces_array
        self.asm('81090007')  # lb      $t1, 0x7($t0)           ; total_remaining_pieces
        self.asm('2529ffff')  # addiu   $t1, $t1, -1            ; decrement total_remaining_pieces
        self.asm('1d20000b')  # bgtz    $t1, 0x2C               ; branch if total_remaining_pieces > 0
        self.asm('00000000')  # nop
        self.asm('240a0009')  # addiu   $t2, $zero, 9           ; set each piece count to 9
        self.asm('a10a0000')  # sb      $t2, 0x0($t0)           ; store into remaining_pieces_array[0] at player_data + 0x6848
        self.asm('a10a0001')  # sb      $t2, 0x1($t0)           ; [1]
        self.asm('a10a0002')  # sb      $t2, 0x2($t0)           ; [2]
        self.asm('a10a0003')  # sb      $t2, 0x3($t0)           ; [3]
        self.asm('a10a0004')  # sb      $t2, 0x4($t0)           ; [4]
        self.asm('a10a0005')  # sb      $t2, 0x5($t0)           ; [5]
        self.asm('a10a0006')  # sb      $t2, 0x6($t0)           ; [6]
        self.asm('1000000a')  # beq     $zero, $zero, 0x28      ; unconditional branch
        self.asm('2409003f')  # addiu   $t1, $zero, 63          ; set total_remaining_pieces to 63

        # branch target for "total_remaining_pieces > 0"
        self.asm('248afe48')  # addiu   $t2, $a0, -0x1B8        ; player_data + 0x6690
        self.asm('8d4b0004')  # lw      $t3, 0x4($t2)           ; refill_idx
        self.asm('000b6080')  # sll     $t4, $t3, 2             ; buf25 entries are ints
        self.asm('014c6821')  # addu    $t5, $t2, $t4           ; add refill_idx offset
        self.asm('8dae0008')  # lw      $t6, 0x8($t5)           ; next_seen_piece = buf25[refill_idx]
        self.asm('010e7821')  # addu    $t7, $t0, $t6           ; remaining_pieces_array[next_seen_piece]
        self.asm('81f80000')  # lb      $t8, ($t7)              ; get piece count
        self.asm('2718ffff')  # addiu   $t8, $t8, -1            ; decrement
        self.asm('a1f80000')  # sb      $t8, ($t7)              ; write back

        # branch target for "unconditional"
        self.asm('03e00008')  # jr      $ra
        self.asm('a1090007')  # sb      $t1, 0x7($t0)           ; store total_remaining_pieces at player_data + 0x684F


        item_display_func_addr = self.asm_addr
        self.asm('27bdffc0')  # addiu   $sp, $sp, -0x40
        self.asm('afbf0024')  # sw      $ra, 0x24($sp)
        self.asm('afa40040')  # sw      $a0, 0x40($sp)          ; player_data + 0x6848
        self.asm('afa50044')  # sw      $a1, 0x44($sp)          ; num_players
        self.asm('afb0003c')  # sw      $s0, 0x3C($sp)
        self.asm('afb10038')  # sw      $s1, 0x38($sp)
        self.asm('afb20034')  # sw      $s2, 0x34($sp)
        self.asm('afb30030')  # sw      $s3, 0x30($sp)

        self.asm('8fa80044')  # lw      $t0, 0x44($sp)          ; num_players
        self.asm('2d090002')  # sltiu   $t1, $t0, 0x2
        self.asm('11200011')  # beq     $t1, $zero, 0x44        ; branch if num_players >= 2
        self.asm('8fb00040')  # lw      $s0, 0x40($sp)          ; player_data + 0x6848

        self.asm('96120010')  # lhu     $s2, 0x10($s0)          ; x position for remaining_pieces
        self.asm('96130012')  # lhu     $s3, 0x12($s0)          ; y position for remaining_pieces

        self.asm('24110007')  # addiu   $s1, $zero, 0x7

        self.asm('82060000')  # lb      $a2, ($s0)              ; remaining_pieces[i]
        self.asm('3c058013')  # lui     $a1, 0x8013
        self.asm('34a5ad6e')  # ori     $a1, $a1, 0xAD6e        ; "%d"
        self.asm('0c02d8b5')  # jal     func_800B62D4           ; sprintf()
        self.asm('27a40028')  # addiu   $a0, $sp, 0x28          ; s_remaining_pieces

        self.asm('27a60028')  # addiu   $a2, $sp, 0x28          ; s_remaining_pieces
        self.asm('02602825')  # or      $a1, $s3, $zero
        self.asm(self.jal_display_text)  # jal     func_display_text
        self.asm('02402025')  # or      $a0, $s2, $zero

        self.asm('26730013')  # addiu   $s3, $s3, 0x13          ; move y to next line
        self.asm('2631ffff')  # addiu   $s1, $s1, -1
        self.asm('1e20fff4')  # bgtz    $s1, -0x30
        self.asm('26100001')  # addiu   $s0, $s0, 1

        # branch target for "num_players >= 2"
        self.asm('8fbf0024')  # lw      $ra, 0x24($sp)
        self.asm('8fb0003c')  # lw      $s0, 0x3C($sp)
        self.asm('8fb10038')  # lw      $s1, 0x38($sp)
        self.asm('8fb20034')  # lw      $s2, 0x34($sp)
        self.asm('8fb30030')  # lw      $s3, 0x30($sp)
        self.asm('03e00008')  # jr      $ra
        self.asm('27bd0040')  # addiu   $sp, $sp, 0x40


        self.next_sub_addr = self.asm_addr

        self.ll_add_item(this_item_addr, next_item_addr, 0, item_init_func_addr, item_update_func_addr, item_display_func_addr)

    def enable_extra_lookahead(self):
        this_item_addr = 0x100F7C  # 8013ACFC
        self.ll_update_item_flags(this_item_addr, 1)

    def register_extra_lookahead(self):
        this_item_addr = 0x100F7C  # 8013ACFC
        next_item_addr = None

        self.asm_addr = self.next_sub_addr


        item_init_func_addr = self.asm_addr
        self.asm('3C098013')  # lui     $t1, 0x8013
        self.asm('3529AD38')  # ori     $t1, $t1, 0xAD38        ; x,y lut for extra_lookahead
        self.asm('01254821')  # addu    $t1, $t1, $a1           ; apply np_cp offset
        self.asm('8D2A0000')  # lw      $t2, ($t1)              ; x,y for extra_lookahead

        self.asm('03E00008')  # jr      $ra
        self.asm('AC8A0014')  # sw      $t2, 0x14($a0)          ; store x,y at player_data + 0x685C


        item_update_func_addr = None


        item_display_func_addr = self.asm_addr
        self.asm('27bdffd0')  # addiu   $sp, $sp, -0x30
        self.asm('afbf0024')  # sw      $ra, 0x24($sp)
        self.asm('afa40030')  # sw      $a0, 0x30($sp)          ; player_data + 0x6848
        self.asm('afa50034')  # sw      $a1, 0x34($sp)          ; num_players
        self.asm('afb0002c')  # sw      $s0, 0x2C($sp)

        self.asm('8fa80034')  # lw      $t0, 0x34($sp)          ; num_players
        self.asm('2d090003')  # sltiu   $t1, $t0, 0x3
        self.asm('11200018')  # beq     $t1, $zero, 0x60        ; branch if num_players >= 3
        self.asm('8fb00030')  # lw      $s0, 0x30($sp)          ; player_data + 0x6848

        """
        000963a0  80 0d 00 b0 80 0d 00 d0  80 0d 00 f0 4c 4a 5a 53  |............LJZS|  // ... 800d012c piece names: arr[7]
        000963b0  54 49 4f 00 00 00 00 00  00 00 00 00 00 00 00 00  |TIO.............|  // L, J, Z, S, T, I, O
        """
        self.asm('3c08800d')  # lui     $t0, 0x800D
        self.asm('3508012c')  # ori     $t0, $t0, 0x012C        ; "LJZSTIO"
        self.asm('2609fe48')  # addiu   $t1, $s0, -0x1B8        ; player_data + 0x6690
        self.asm('8d2a0004')  # lw      $t2, 0x4($t1)           ; refill_idx
        self.asm('000a5880')  # sll     $t3, $t2, 2             ; buf25 entries are ints
        self.asm('012b6021')  # addu    $t4, $t1, $t3           ; add refill_idx offset
        self.asm('8d8d0008')  # lw      $t5, 0x8($t4)           ; next_seen_piece = buf25[refill_idx]
        self.asm('010d7021')  # addu    $t6, $t0, $t5           ; "LJZSTIO"[next_seen_piece]
        self.asm('91c60000')  # lbu     $a2, ($t6)              ; 4th lookahead

        self.asm('8d2a0000')  # lw      $t2, ($t1)              ; next_idx
        self.asm('000a5880')  # sll     $t3, $t2, 2             ; buf25 entries are ints
        self.asm('012b6021')  # addu    $t4, $t1, $t3           ; add next_idx offset
        self.asm('8d8d0008')  # lw      $t5, 0x8($t4)           ; next_next_seen_piece = buf25[next_idx]
        self.asm('010d7021')  # addu    $t6, $t0, $t5           ; "LJZSTIO"[next_next_seen_piece]
        self.asm('91c70000')  # lbu     $a3, ($t6)              ; 5th lookahead

        self.asm('3c058013')  # lui     $a1, 0x8013
        self.asm('34a5ad71')  # ori     $a1, $a1, 0xAD71        ; "%c %c"
        self.asm('0c02d8b5')  # jal     func_800B62D4           ; sprintf()
        self.asm('27a40028')  # addiu   $a0, $sp, 0x28          ; s_extra_lookahead

        self.asm('27a60028')  # addiu   $a2, $sp, 0x28          ; s_extra_lookahead
        self.asm('96050016')  # lhu     $a1, 0x16($s0)           ; y position for extra_lookahead
        self.asm(self.jal_display_text)  # jal     func_display_text
        self.asm('96040014')  # lhu     $a0, 0x14($s0)           ; x position for extra_lookahead

        # branch target for "num_players >= 3"
        self.asm('8fbf0024')  # lw      $ra, 0x24($sp)
        self.asm('8fb0002c')  # lw      $s0, 0x2C($sp)
        self.asm('03e00008')  # jr      $ra
        self.asm('27bd0030')  # addiu   $sp, $sp, 0x30


        self.next_sub_addr = self.asm_addr

        self.ll_add_item(this_item_addr, next_item_addr, 0, item_init_func_addr, item_update_func_addr, item_display_func_addr)

    """
    def shift_piece(self, position, value):
        addr1 = 0x0962b0
        value &= 0xFF
        self.data[addr1 + position: addr1 + position + 1] = bytes([value])
    """

    def modify_handicap(self, value):
        addr1 = 0x096180
        value &= 0xFF
        self.data[addr1 : addr1 + 1] = bytes([value])
