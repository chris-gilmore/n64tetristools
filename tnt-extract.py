#!/usr/bin/env python3

"""
    # mode='RGBA'
    $ ./tnt-extract.py -v ~/tnt.z64 -i 0x2A56BA
    $ mv image.png nintendo_logo.png

    # mode='L'
    $ ./tnt-extract.py -v ~/tnt.z64 -i 0x2A87FA
    $ mv image.png font_a.png

    # mode='P'
    $ ./tnt-extract.py -v ~/tnt.z64 -i 0x521998
    $ mv image.png finale_boiler.png

    # anim, 4 frames
    $ ./tnt-extract.py -v ~/tnt.z64 --anim 0x527EDC
    $ mv anim.webp celtic_lamp.webp

    # by name
    $ ./tnt-extract.py -v ~/tnt.z64 -n nintendo_logo
    $ mv image.png nintendo_logo.png
"""

import argparse

from n64tetris.roms.tnt import TheNewTetrisRom

def auto_int(x):
    return int(x, 0)

def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true', help='increase verbosity')
    parser.add_argument('-f', '--force', action='store_true', help='bypass safety checks')
    parser.add_argument('SRC', help='source rom file')
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('-i', metavar='ADDR', type=auto_int, help='address of image')
    group.add_argument('--anim', metavar='ADDR', type=auto_int, help='address of first image')
    group.add_argument('-n', metavar='NAME', help='name of image or anim')

    args = parser.parse_args()

    rom = TheNewTetrisRom(verbose=args.verbose, force=args.force)
    rom.from_file(args.SRC)

    if args.i:
        rom.extract_image(args.i)

    if args.anim:
        rom.extract_anim(args.anim)

    if args.n:
        rom.extract_by_name(args.n)

if __name__ == "__main__":
    main()
