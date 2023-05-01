#!/usr/bin/env python3

"""
    $ ./sphere-scan.py -v ~/tetrisphere.z64 > tetrisphere.assets
"""

import argparse

from n64tetris.roms.sphere import TetrisphereRom

def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true', help='increase verbosity')
    parser.add_argument('SRC', help='source rom file')
    args = parser.parse_args()

    rom = TetrisphereRom(verbose=args.verbose)
    rom.from_file(args.SRC)

    rom.scan()

if __name__ == "__main__":
    main()
