#!/usr/bin/env python3

import argparse

from n64tetris.srams.tnt import TheNewTetrisSram

def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true', help='increase verbosity')
    parser.add_argument('SRC', help='source sram file')
    parser.add_argument('DEST', help='output sram file')

    parser.add_argument('--twl', metavar='VALUE', type=int, help='set total wonder lines')

    group_music = parser.add_argument_group('music', description='Set music options.')
    group_music.add_argument('--mlvl', metavar='[1-14]', choices=range(1, 15), type=int, help='music level')
    group_music.add_argument('--slvl', metavar='[1-14]', choices=range(1, 15), type=int, help='sfx level')
    group_music.add_argument('--mode', metavar='[0-2]', choices=range(0, 3), type=int, help='music mode: 0=AUTO, 1=CHOOSE, 2=RANDOM')
    group_music.add_argument('--song', metavar='[0-15]', choices=range(0, 16), type=int, help='song: 0=TITLE, 1=MOROCCO, 2=DVIE, 3=POLYASIA, 4=FLOPPY, 5=PYRAMID, 6=GIALI, 7=THREAD6, 8=HALUCI, 9=MAYAN, 10=GREEK, 11=EGYPT, 12=CELTIC, 13=AFRICA, 14=JAPAN, 15=KALINKA')

    args = parser.parse_args()

    sram = TheNewTetrisSram(verbose=args.verbose)
    sram.from_file(args.SRC)

    if args.twl is not None:
        sram.set_total_wonder_lines(args.twl)

    if args.mlvl is not None:
        sram.set_music_level(args.mlvl)

    if args.slvl is not None:
        sram.set_sfx_level(args.slvl)

    if args.mode is not None:
        sram.set_music_mode(args.mode)

    if args.song is not None:
        sram.set_song(args.song)

    sram.to_file(args.DEST)

if __name__ == "__main__":
    main()
