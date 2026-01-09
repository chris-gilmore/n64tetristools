#!/usr/bin/env python3

"""
    # RGBA, 16b
    $ ./tnt-extract.py -v ~/tnt.z64 -i 0x2A56BA
    # nintendo_logo.png

    # IA, 8b
    $ ./tnt-extract.py -v ~/tnt.z64 -i 0x2A87FA
    # font_a.png

    # CI, 8b
    $ ./tnt-extract.py -v ~/tnt.z64 -i 0x521998
    # finale_boiler.png

    # anim, 4 frames
    $ ./tnt-extract.py -v ~/tnt.z64 --anim 0x527EDC
    $ mv anim.webp celtic_lamp.webp

    # by name
    $ ./tnt-extract.py -v ~/tnt.z64 -n nintendo_logo
    # nintendo_logo.png

    # extract all non-anim images
    $ mkdir images && cd images
    $ ../tnt-extract.py -v ~/tnt.z64 --all-images
    $ cd ..

    # extract all anim images
    $ mkdir anims && cd anims
    $ ../tnt-extract.py -v ~/tnt.z64 --all-anims
    $ cd ..
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
    group.add_argument('--all-images', action='store_true', help='all non-anim images')
    group.add_argument('--all-anims', action='store_true', help='all anim images')

    args = parser.parse_args()

    rom = TheNewTetrisRom(verbose=args.verbose, force=args.force)
    rom.from_file(args.SRC)

    if args.i:
        rom.extract_image(args.i)

    if args.anim:
        rom.extract_anim(args.anim)

    if args.n:
        rom.extract_by_name(args.n)

    if args.all_images:
        rom.extract_all_images()

    if args.all_anims:
        rom.extract_all_anims()

if __name__ == "__main__":
    main()
