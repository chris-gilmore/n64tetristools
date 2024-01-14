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

    # Play only Finale
    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --screens 7 7

    # Move time_remaining (sprint) and change its color
    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --stat 3 --xy 235 150 --rgba 0xc0 0xc0 0xc0 0xff

    # Initial hold piece is always blue stick (5:I piece).
    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --ihp 5

    # Totally uncapped and unlocked
    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --spawn 1 --hold 1 --lock 10 --square 0 --line 1 --screens 0 7
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

    group_delay = parser.add_argument_group('delay', 'Delay timers for piece spawning, holding, locking, square forming, and line clearing containing gold or silver.  One jiffy is a sixtieth of a second.')
    group_delay.add_argument('--spawn', metavar='JIFFIES', type=int, help='(default: 20, minimum: 1)')
    group_delay.add_argument('--hold', metavar='JIFFIES', type=int, help='(default: 16, minimum: 1)')
    group_delay.add_argument('--lock', metavar='JIFFIES', type=int, help='(default: 20, minimum: 0)')
    group_delay.add_argument('--square', metavar='JIFFIES', type=int, help='(default: 45, minimum: 0)')
    group_delay.add_argument('--line', metavar='JIFFIES', type=int, help='(default: 24, minimum: 1)')

    group_screens = parser.add_argument_group('screens', 'Subrange of screens to play.  For example, --screens 2 5 would allow only screens Egypt, Celtic, Africa, and Japan.  Play only Finale: --screens 7 7')
    group_screens.add_argument('--screens', nargs=2, metavar='#', type=int, help='(default: 0 7)')

    group_stat = parser.add_argument_group('stat', 'Modify stat properties.')
    group_stat.add_argument('--stat', metavar='TYPE', type=int, help='1:PlayerName, 2:LineCount, 3:TimeRemaining')
    group_stat.add_argument('--xy', nargs=2, metavar='#', type=auto_int, help='position: X Y')
    group_stat.add_argument('--rgba', nargs=4, metavar='#', type=auto_int, help='color: R G B A')

    group_ihp = parser.add_argument_group('ihp', 'Set initial hold piece.')
    group_ihp.add_argument('--ihp', metavar='TYPE', type=int, help='0:L, 1:J, 2:Z, 3:S, 4:T, 5:I, 6:O')

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

    if args.spawn is not None:
        rom.modify_spawn_delay(args.spawn)

    if args.hold is not None:
        rom.modify_hold_delay(args.hold)

    if args.lock is not None:
        rom.modify_lock_delay(args.lock)

    if args.square is not None:
        rom.modify_square_delay(args.square)

    if args.line is not None:
        rom.modify_line_delay(args.line)

    if args.screens is not None:
        start, end = args.screens
        rom.modify_screens(start, end)

    if args.stat is not None:
        if args.xy is not None:
            x, y = args.xy
            rom.modify_stat_position(args.stat, x, y)
        if args.rgba is not None:
            r, g, b, a = args.rgba
            rom.modify_stat_color(args.stat, r, g, b, a)

    if args.ihp is not None:
        rom.modify_initial_hold_piece(args.ihp)

    rom.to_file(args.DEST)

if __name__ == "__main__":
    main()
