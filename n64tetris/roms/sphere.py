import sys
import struct
from enum import Enum, auto
import wave
import numpy as np

#from PIL import Image

from .base import BaseRom
from .. import utils
from ..mappings import sphere as spheremap

class AssetType(Enum):
    UNKNOWN = auto()
    IMAGE = auto()
    SAMPLE = auto()
    DCM = auto()

class AssetFormat(Enum):
    UNKNOWN = auto()
    RGBA5551 = auto()       # b'\x00\x00\x00\x00'
    CODE02 = auto()         # b'\x00\x02\x00\x00'
    CODE03 = auto()         # b'\x00\x03\x00\x00'
    SIZE_ASSUMED = auto()
    PCM_S8 = auto()
    PCM_S16 = auto()
    DCM1 = auto()

class TetrisphereRom(BaseRom):
    def __init__(self, verbose=False, force=False):
        super().__init__(game_code=b'NTPE', verbose=verbose, force=force)
        self.decoders = (self.sqsh_decode, self.dcm1_decode, self.sample_decode)

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
        end = addr+12 + payload_size

        if payload_size == buflen:
            raw = self.data[addr+12 : end]
        else:
            raw = self.sqsh_decompress(addr+12, payload_size, buflen)

        if self.verbose:
            print(f"0x{addr:06X}\t{prefix.decode()}\t{buflen}\t{payload_size}\t0x{end:06X}", file=sys.stderr)

        info = {'prefix': prefix, 'buflen': buflen, 'payload_size': payload_size, 'end': end}
        return raw, info, None

    def dcm1_decode(self, addr):
        prefix = self.data[addr : addr + 4]
        if prefix != b'DCM1':
            return None, None, f"No DCM1 asset found at address: 0x{addr:06X}"

        end = spheremap.END[addr]
        payload_size = end - addr
        raw = self.data[addr : end]
        buflen = len(raw)

        if self.verbose:
            print(f"0x{addr:06X}\t{prefix.decode()}\t{buflen}\t{payload_size}\t0x{end:06X}", file=sys.stderr)

        info = {'prefix': prefix, 'buflen': buflen, 'payload_size': payload_size, 'end': end}
        return raw, info, None

    def decompressLZ(self, addr, compressed_size):
        ring = [0] * 0x1000
        for i in range(0, 0x100):
            ring[i] = i
        for i in range(0x100, 0x200):
            ring[i] = 0x1FF - i
        for i in range(0, 0x100):
            for j in range(0, 4):
                ring[0x200 + (4 * i) + j] = i
        for i in range(0x600, 0x1000):
            ring[i] = i & 0xFF

        raw = b''
        r = 0
        p = 0
        while p < compressed_size:
            c = self.data[addr+p]
            p += 1
            l = c >> 4
            if l:
                b = (c & 0xF) << 8
                b |= self.data[addr+p]
                p += 1
                for i in range(0, l+2):
                    ring[r] = ring[(b+i) & 0xFFF]
                    raw += bytes([ring[r]])
                    r = (r+1) & 0xFFF
            else:
                c += 1;
                raw += self.data[addr+p : addr+p + c]
                for i in range(0, c):
                    ring[r] = self.data[addr+p]
                    p += 1
                    r = (r+1) & 0xFFF

        return raw

    def sample_decode(self, addr):
        if addr not in spheremap.SAMPLE:
            return None, None, f"No Sample asset found at address: 0x{addr:06X}"

        c = self.data[addr]
        if c == 0:
            prefix = b''
            payload_size = struct.unpack('>I', self.data[addr+1 + c : addr+1 + c + 4])[0]
            end = addr+1 + c + 4 + payload_size
            raw = self.data[addr+1 + c + 4 : end]
            buflen = len(raw)
        else:
            assert c == 2
            prefix = self.data[addr+1 : addr+1 + c]
            assert prefix == b'SD'
            payload_size = struct.unpack('>I', self.data[addr+1 + c : addr+1 + c + 4])[0]
            end = addr+1 + c + 4 + payload_size

            _raw = self.decompressLZ(addr+1 + c + 4, payload_size)

            raw = b''
            old = _raw[0]
            raw += bytes([old])
            for i in range(1, len(_raw)):
                old -= _raw[i]
                raw += bytes([old & 0xFF])

            buflen = len(raw)

        if self.verbose:
            print(f"0x{addr:06X}\t{prefix.decode()}\t{buflen}\t{payload_size}\t0x{end:06X}", file=sys.stderr)

        info = {'prefix': prefix, 'buflen': buflen, 'payload_size': payload_size, 'end': end}
        return raw, info, None

    def guess_asset(self, addr, raw):
        info = {}

        if addr in spheremap.SAMPLE:
            info['format'] = spheremap.SAMPLE[addr][0]
            info['sample_rate'] = spheremap.SAMPLE[addr][1]
            if info['format'] == 0:
                return AssetType.SAMPLE, AssetFormat.PCM_S8, info
            else:
                return AssetType.SAMPLE, AssetFormat.PCM_S16, info

        elif raw[:4] == b'DCM1':
            return AssetType.DCM, AssetFormat.DCM1, info

        else:
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

    def extract_sample(self, s_addr, as_wave):
        raw, _, asset_type, asset_format, asset_info, err = self.extract_asset(s_addr)
        if err is not None:
            print(err, file=sys.stderr)
            sys.exit(1)

        if asset_type != AssetType.SAMPLE:
            print(f"No sample found at address: 0x{s_addr:06X}", file=sys.stderr)
            sys.exit(1)

        if asset_format == AssetFormat.PCM_S16:
            if as_wave:
                with wave.open(f"{s_addr:06X}.wav", 'wb') as wavfile:
                    wavfile.setparams((1, 2, asset_info['sample_rate'], 0, 'NONE', 'not compressed'))
                    wavfile.writeframes(raw)
            else:
                open(f"{s_addr:06X}.bin", 'wb').write(raw)

        elif asset_format == AssetFormat.PCM_S8:
            if as_wave:
                arr_u8 = np.frombuffer(raw, dtype=np.uint8) + 128
                with wave.open(f"{s_addr:06X}.wav", 'wb') as wavfile:
                    wavfile.setparams((1, 1, asset_info['sample_rate'], 0, 'NONE', 'not compressed'))
                    wavfile.writeframes(arr_u8)
            else:
                open(f"{s_addr:06X}.bin", 'wb').write(raw)

        elif asset_format == AssetFormat.UNKNOWN:
            print(f"Unknown sample format at address: 0x{s_addr:06X}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Unimplemented sample format at address: 0x{s_addr:06X}", file=sys.stderr)
            sys.exit(1)

    def extract_all_samples(self, as_wave):
        for s_addr, params in spheremap.SAMPLE.items():
            self.extract_sample(s_addr, as_wave)

    def extract_dcm(self, dcm_addr):
        raw, _, asset_type, asset_format, asset_info, err = self.extract_asset(dcm_addr)
        if err is not None:
            print(err, file=sys.stderr)
            sys.exit(1)

        if asset_type != AssetType.DCM:
            print(f"No dcm found at address: 0x{dcm_addr:06X}", file=sys.stderr)
            sys.exit(1)

        if asset_format == AssetFormat.DCM1:
            open(f"{dcm_addr:06X}.bin", 'wb').write(raw)
            if self.verbose:
                print("dcm_name, dcm_addr, num_channels, num_samples, smp_id, flags, smplen, loopBegin, loopEnd")
                num_channels, num_samples = struct.unpack('2B', raw[4:6])
                for i in range(num_samples):
                    smplen, loopBegin, loopEnd, flags, smp_id = struct.unpack('<3I2H', raw[14 + i * 16 : 30 + i * 16])
                    print(f"{spheremap.DCM_NAME[dcm_addr]}, 0x{dcm_addr:06X}, {num_channels}, {num_samples}, {smp_id}, {flags:04b}, {smplen}, {loopBegin}, {loopEnd}")

        elif asset_format == AssetFormat.UNKNOWN:
            print(f"Unknown dcm format at address: 0x{dcm_addr:06X}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Unimplemented dcm format at address: 0x{dcm_addr:06X}", file=sys.stderr)
            sys.exit(1)

    def extract_all_dcms(self):
        for dcm_name, dcm_addr in spheremap.DCM_BY_NAME.items():
            self.extract_dcm(dcm_addr)
