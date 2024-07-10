
```
usage: tnt-modify.py [-h] [-v] [-f] [-s] [-p] [-r] [-l] [--image FILE]
                     [-i ADDR | -n NAME] [--seed VALUE] [--bag # # #]
                     [--sprint TIME] [--ultra LINES] [--piece TYPE]
                     [--dc # # #] [--sc # # #] [--spawn JIFFIES]
                     [--hold JIFFIES] [--lock JIFFIES] [--square JIFFIES]
                     [--line JIFFIES] [--screens # #] [--stat TYPE] [--xy # #]
                     [--rgba # # # #] [--ihp TYPE] [--sqsz {2,4,6,8}]
                     [--handicap [0-19]]
                     SRC DEST

positional arguments:
  SRC                source rom file
  DEST               output rom file

options:
  -h, --help         show this help message and exit
  -v, --verbose      increase verbosity
  -f, --force        bypass safety checks
  -s                 displays seed
  -p                 displays piece count
  -r                 displays remaining pieces
  -l                 displays extra lookahead

image:
  Insert image either by address or by name.

  --image FILE       load image file
  -i ADDR            address of image
  -n NAME            name of image

seed:
  Hardcode RNG seed to a given 32-bit value, for example, 0x600D5EED.

  --seed VALUE       RNG seed

bag:
  A bag is defined by the following three numbers: {START} {END} {N}. Each
  bag generated will contain {N} copies each of the pieces from {START} up
  to, but not including, {END}. Bag size {N*(END-START)} must not be greater
  than 63. The order of pieces is: 0:L, 1:J, 2:Z, 3:S, 4:T, 5:I, 6:O.
  Example: "--bag 5 6 9" would produce only I pieces.

  --bag # # #        (default: 0 7 9)

sprint:
  Sprint goal time.

  --sprint TIME      seconds (default: 180)

ultra:
  Ultra goal lines.

  --ultra LINES      lines (default: 150)

piece:
  Modify piece properties.

  --piece TYPE       0:L, 1:J, 2:Z, 3:S, 4:T, 5:I, 6:O
  --dc # # #         diffuse color: R G B
  --sc # # #         specular color: R G B (default: 0xFF 0xFF 0xFF)

delay:
  Delay timers for piece spawning, holding, locking, square forming, and
  line clearing containing gold or silver. One jiffy is a sixtieth of a
  second.

  --spawn JIFFIES    (default: 20, minimum: 1)
  --hold JIFFIES     (default: 16, minimum: 1)
  --lock JIFFIES     (default: 20, minimum: 0)
  --square JIFFIES   (default: 45, minimum: 0)
  --line JIFFIES     (default: 24, minimum: 1)

screens:
  Subrange of screens to play. For example, --screens 2 5 would allow only
  screens Egypt, Celtic, Africa, and Japan. Play only Finale: --screens 7 7

  --screens # #      (default: 0 7)

stat:
  Modify stat properties.

  --stat TYPE        1:PlayerName, 2:LineCount, 3:TimeRemaining, 4:Seed
  --xy # #           position: X Y
  --rgba # # # #     color: R G B A

ihp:
  Set initial hold piece.

  --ihp TYPE         0:L, 1:J, 2:Z, 3:S, 4:T, 5:I, 6:O

sqsz:
  Square size.

  --sqsz {2,4,6,8}   (default: 4)

handiciap:
  Raise the bottom of the playfield for marathon and sprint.

  --handicap [0-19]  rows (default: 0)
```

```
    $ sudo dnf install lzo-devel python3-devel

--

    $ pip3 install python-lzo
    $ pip3 install pillow

--

    $ ./tnt-scan.py -v ~/tnt.z64 > tnt.assets

    $ ./sphere-scan.py -v ~/tetrisphere.z64 > tetrisphere.assets

--

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

    # mode='RGBA'
    $ ./sphere-extract.py -v ~/tetrisphere.z64 -i 0x74271C
    $ mv image.png title_screen.png

--

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
```
