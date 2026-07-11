#!/usr/bin/env python3

"""
    # mode='RGBA'
    $ ./sphere-extract.py -v ~/tetrisphere.z64 -i 0x74271C
    $ mv image.png title_screen.png
"""

import argparse

from n64tetris.roms.sphere import TetrisphereRom

def auto_int(x):
    return int(x, 0)

def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true', help='increase verbosity')
    parser.add_argument('-f', '--force', action='store_true', help='bypass safety checks')
    parser.add_argument('SRC', help='source rom file')
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('-i', nargs='+', metavar='ADDR', type=auto_int, help='address of image (multiple for anim)')
    group.add_argument('-s', metavar='ADDR', type=auto_int, help='address of sample')
    group.add_argument('--all-samples', action='store_true', help='all samples')
    parser.add_argument('-w', '--wave', action='store_true', help='as wav file(s)')
    group.add_argument('--dcm', metavar='ADDR', type=auto_int, help='address of dcm')
    group.add_argument('--all-dcms', action='store_true', help='all dcms')

    args = parser.parse_args()

    rom = TetrisphereRom(verbose=args.verbose, force=args.force)
    rom.from_file(args.SRC)

    if args.i:
        rom.extract_image(args.i)

    if args.s:
        rom.extract_sample(args.s, args.wave)

    if args.all_samples:
        rom.extract_all_samples(args.wave)

    if args.dcm:
        rom.extract_dcm(args.dcm)

    if args.all_dcms:
        rom.extract_all_dcms()

if __name__ == "__main__":
    main()
