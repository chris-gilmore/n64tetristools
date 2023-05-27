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

    group_piece = parser.add_argument_group('piece', 'Modify piece properties.')
    group_piece.add_argument('--piece', metavar='TYPE', type=int, help='0:L, 1:J, 2:Z, 3:S, 4:T, 5:I, 6:O')
    group_piece.add_argument('--dc', nargs=3, metavar='#', type=auto_int, help='diffuse color: R G B')
    group_piece.add_argument('--sc', nargs=3, metavar='#', type=auto_int, help='specular color: R G B (default: 0xFF 0xFF 0xFF)')

    group_delay = parser.add_argument_group('delay', 'Delay timers for piece locking and square forming.  One jiffy is a sixtieth of a second.')
    group_delay.add_argument('--lock', metavar='JIFFIES', type=int, help='(default: 20)')
    group_delay.add_argument('--square', metavar='JIFFIES', type=int, help='(default: 45)')

    args = parser.parse_args()

    rom = TheNewTetrisRom(verbose=args.verbose)
    rom.from_file(args.SRC)

    if args.image is not None:
        if args.i is not None:
            rom.insert_image(args.image, args.i)
        elif args.n is not None:
            rom.insert_by_name(args.image, args.n)

    if args.seed is not None:
        rom.modify_seed(args.seed)

    if args.bag is not None:
        start, end, n = args.bag
        rom.modify_bag(start, end, n)

    if args.sprint is not None:
        rom.modify_sprint(args.sprint)

    if args.ultra is not None:
        rom.modify_ultra(args.ultra)

    if args.piece is not None:
        if args.dc is not None:
            r, g, b = args.dc
            rom.modify_piece_diffuse_color(args.piece, r, g, b)
        if args.sc is not None:
            r, g, b = args.sc
            rom.modify_piece_specular_color(args.piece, r, g, b)

    if args.lock is not None:
        rom.modify_lock_delay(args.lock)

    if args.square is not None:
        rom.modify_square_delay(args.square)

    rom.to_file(args.DEST)

if __name__ == "__main__":
    main()
