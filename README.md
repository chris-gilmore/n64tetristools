
```
usage: tnt-modify.py [-h] [-v] [--image FILE] [-i ADDR | -n NAME]
                     [--seed VALUE] [--bag # # #] [--sprint TIME]
                     [--ultra LINES]
                     SRC DEST

positional arguments:
  SRC            source rom file
  DEST           output rom file

optional arguments:
  -h, --help     show this help message and exit
  -v, --verbose  increase verbosity

image:
  Insert image either by address or by name.

  --image FILE   load image file
  -i ADDR        address of image
  -n NAME        name of image

seed:
  Hardcode RNG seed to a given 32-bit value, for example, 0xBAD05EED.

  --seed VALUE   RNG seed

bag:
  A bag is defined by the following three numbers: {START} {END} {N}. Each
  bag generated will contain {N} copies each of the pieces from {START} up
  to, but not including, {END}. Bag size {N*(END-START)} must not be greater
  than 63. The order of pieces is: 0:L, 1:J, 2:Z, 3:S, 4:T, 5:I, 6:O.
  Example: "--bag 5 6 9" would produce only I pieces.

  --bag # # #    (default: 0 7 9)

sprint:
  Sprint goal time.

  --sprint TIME  seconds (default: 180)

ultra:
  Ultra goal lines.

  --ultra LINES  lines (default: 150)

```

```
    $ sudo dnf install lzo-devel python3-devel

--

    $ pip3 install python-lzo
    $ pip3 install pillow

--

    $ ./tnt-scan.py -v ~/tnt.z64 > tnt.assets

    $ ./tetrisphere-scan.py -v ~/tetrisphere.z64 > tetrisphere.assets

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
    $ ./tetrisphere-extract.py -v ~/tetrisphere.z64 -i 0x74271C
    $ mv image.png title_screen.png

--

    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --image modified_finale_boiler.png -i 0x521998

    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --seed 0xBAD05EED

    # All blues
    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --bag 5 6 9

    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --sprint 90

    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --ultra 1500

    # by name
    $ ./tnt-modify.py -v ~/tnt.z64 mod.z64 --image modified_finale_boiler.png -n finale_boiler
```
