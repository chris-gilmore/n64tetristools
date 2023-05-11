#!/usr/bin/env python3

"""
    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --image modified_finale_boiler.png -i 0x521998

    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --seed 0x600D5EED

    # All blues
    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --bag 5 6 9

    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --sprint 90

    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --ultra 1500

    # by name
    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --image modified_finale_boiler.png -n finale_boiler
"""

import argparse

from n64tetris.roms.tnt import TheNewTetrisRom

def auto_int(x):
    return int(x, 0)

def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true', help='increase verbosity')
    parser.add_argument('SRC', help='source rom file')
    parser.add_argument('DEST', help='output rom file')

    group_image = parser.add_argument_group('image', description='Insert image either by address or by name.')
    group_image.add_argument('--image', metavar='FILE', help='load image file')
    group_image_x = group_image.add_mutually_exclusive_group(required=False)
    group_image_x.add_argument('-i', metavar='ADDR', type=auto_int, help='address of image')
    group_image_x.add_argument('-n', metavar='NAME', help='name of image')

    group_seed = parser.add_argument_group('seed', 'Hardcode RNG seed to a given 32-bit value, for example, 0x600D5EED.')
    group_seed.add_argument('--seed', metavar='VALUE', type=auto_int, help='RNG seed')

    group_bag = parser.add_argument_group('bag', 'A bag is defined by the following three numbers: {START} {END} {N}. Each bag generated will contain {N} copies each of the pieces from {START} up to, but not including, {END}.  Bag size {N*(END-START)} must not be greater than 63.  The order of pieces is: 0:L, 1:J, 2:Z, 3:S, 4:T, 5:I, 6:O.  Example: "--bag 5 6 9" would produce only I pieces.')
    group_bag.add_argument('--bag', nargs=3, metavar='#', type=int, help='(default: 0 7 9)')

    group_sprint = parser.add_argument_group('sprint', 'Sprint goal time.')
    group_sprint.add_argument('--sprint', metavar='TIME', type=auto_int, help='seconds (default: 180)')

    group_ultra = parser.add_argument_group('ultra', 'Ultra goal lines.')
    group_ultra.add_argument('--ultra', metavar='LINES', type=auto_int, help='lines (default: 150)')

    args = parser.parse_args()

    rom = TheNewTetrisRom(verbose=args.verbose)
    rom.from_file(args.SRC)

    if args.image:
        if args.i:
            rom.insert_image(args.image, args.i)
        elif args.n:
            rom.insert_by_name(args.image, args.n)

    if args.seed:
        rom.modify_seed(args.seed)

    if args.bag:
        start, end, n = args.bag
        rom.modify_bag(start, end, n)

    if args.sprint:
        rom.modify_sprint(args.sprint)

    if args.ultra:
        rom.modify_ultra(args.ultra)

    rom.to_file(args.DEST)

if __name__ == "__main__":
    main()
