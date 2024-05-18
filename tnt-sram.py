#!/usr/bin/env python3

import argparse

from n64tetris.srams.tnt import TheNewTetrisSram

def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true', help='increase verbosity')
    parser.add_argument('SRC', help='source sram file')
    parser.add_argument('DEST', help='output sram file')
    parser.add_argument('--twl', metavar='VALUE', type=int, help='set total wonder lines')

    args = parser.parse_args()

    sram = TheNewTetrisSram(verbose=args.verbose)
    sram.from_file(args.SRC)

    if args.twl is not None:
        sram.set_total_wonder_lines(args.twl)

    sram.to_file(args.DEST)

if __name__ == "__main__":
    main()
