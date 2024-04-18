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
    parser.add_argument('-i', nargs='+', metavar='ADDR', type=auto_int, help='address of image (multiple for anim)')

    args = parser.parse_args()

    rom = TetrisphereRom(verbose=args.verbose, force=args.force)
    rom.from_file(args.SRC)

    if args.i:
        rom.extract_image(args.i)

if __name__ == "__main__":
    main()
