#!/usr/bin/env python3

"""
    $ ./tnt-scan.py -v ~/tnt.z64 > tnt.assets
"""

import argparse

from n64tetris.roms.tnt import TheNewTetrisRom

def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true', help='increase verbosity')
    parser.add_argument('SRC', help='source rom file')
    args = parser.parse_args()

    rom = TheNewTetrisRom(verbose=args.verbose)
    rom.from_file(args.SRC)

    rom.scan()

if __name__ == "__main__":
    main()
