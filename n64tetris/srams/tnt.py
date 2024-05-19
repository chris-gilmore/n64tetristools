import sys

class TheNewTetrisSram:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.data = bytearray()  # big endian
        self.orig_endianness = None

    def reverse_endianness(self, data):
        reversed_data = bytearray()
        i = 0
        while i < len(data):
            x = data[i : i + 4]
            x.reverse()
            reversed_data.extend(x)
            i += 4
        return reversed_data

    def from_file(self, filename):
        data = bytearray(open(filename, 'rb').read())
        magic_bytes = data[0x18F8 : 0x18FC]

        if magic_bytes == bytes.fromhex("302e3062"):
            self.orig_endianness = 'big'
            self.data = data
        elif magic_bytes == bytes.fromhex("62302e30"):
            self.orig_endianness = 'little'
            # convert to big endian for internal use
            self.data = self.reverse_endianness(data)
        else:
            print("error: Unknown file type", file=sys.stderr)
            sys.exit(1)

    def to_file(self, filename):
        self.update_checksum(0x0)
        self.update_checksum(0x1900)
        self.update_checksum(0x3200)

        if self.orig_endianness == 'big':
            data = self.data
        elif self.orig_endianness == 'little':
            # convert back to little endian
            data = self.reverse_endianness(self.data)
        else:
            print("error: Unknown file type", file=sys.stderr)
            sys.exit(1)

        open(filename, 'wb').write(data)

    def update_checksum(self, start):
        checksum = self.calc_checksum(start, 0x18FC)
        self.write(checksum, start, 0x18FC, 4)
        if self.verbose:
            print(f"Writing checksum at 0x{start+0x18FC:04X} to 0x{checksum:08X}")

    def calc_checksum(self, start, length):
        checksum = 0
        i = 0
        while i < length:
            a, b, c, d = self.data[start + i : start + i + 4]
            checksum += a ^ 0x10
            checksum += b ^ 0x20
            checksum -= c
            checksum -= d << 1
            i += 4
        return checksum & 0xFFFFFFFF

    def write(self, value, start, offset, nbytes):
        self.data[start + offset : start + offset + nbytes] = value.to_bytes(nbytes, byteorder='big')

    def write_thrice(self, value, offset, nbytes):
        self.write(value, 0x0, offset, nbytes)
        self.write(value, 0x1900, offset, nbytes)
        self.write(value, 0x3200, offset, nbytes)

    def set_total_wonder_lines(self, twl):
        odd_bits = twl & 0xAAAAAAAA
        even_bits = twl & 0x55555555
        self.write_thrice(odd_bits, 0xF04, 4)
        self.write_thrice(even_bits, 0xF08, 4)

    def set_music_level(self, mlvl):
        """
        [0x0639]  MUSIC LEVEL
                  1            0x00000000
                  2            0x00000924
                  3            0x00001248
                  4            0x00001B6C
                  5            0x00002490
                  6            0x00002DB4
                  7            0x000036D8
                  8            0x00003FFC
                  9            0x00004920
                  10           0x00005244
                  11           0x00005B68
                  12           0x0000648C
                  13           0x00006DB0
                  14           0x000076D4
        """
        self.write_thrice((mlvl - 1) * 0x924, 0x639 * 4, 4)

    def set_sfx_level(self, slvl):
        """
        [0x063A]  SFX LEVEL
                  1            0x00000000
                  2            0x00000924
                  3            0x00001248
                  4            0x00001B6C
                  5            0x00002490
                  6            0x00002DB4
                  7            0x000036D8
                  8            0x00003FFC
                  9            0x00004920
                  10           0x00005244
                  11           0x00005B68
                  12           0x0000648C
                  13           0x00006DB0
                  14           0x000076D4
        """
        self.write_thrice((slvl - 1) * 0x924, 0x63A * 4, 4)

    def set_song(self, song):
        """
        [0x063B]  SONG
                  TITLE        0x00000000
                  MOROCCO      0x00000001
                  DVIE         0x00000002
                  POLYASIA     0x00000003
                  FLOPPY       0x00000004
                  PYRAMID      0x00000005
                  GIALI        0x00000006
                  THREAD6      0x00000007
                  HALUCI       0x00000008
                  MAYAN        0x00000009
                  GREEK        0x0000000A
                  EGYPT        0x0000000B
                  CELTIC       0x0000000C
                  AFRICA       0x0000000D
                  JAPAN        0x0000000E
                  KALINKA      0x0000000F
        """
        self.write_thrice(song, 0x63B * 4, 4)

    def set_music_mode(self, mode):
        """
        [0x063C]  MUSIC MODE
                  AUTO         0x00000000
                  CHOOSE       0x00000001
                  RANDOM       0x00000002
        """
        self.write_thrice(mode, 0x63C * 4, 4)
