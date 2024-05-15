#!/usr/bin/env python3

import sys

def detect_endianness(data):
    magic_bytes = data[0x18F8 : 0x18FC]

    if magic_bytes == bytes.fromhex("302e3062"):
        return 'big'
    elif magic_bytes == bytes.fromhex("62302e30"):
        return 'little'
    else:
        return None

def calc_checksum(data, offset, length, endianness):
    """
    glabel func_8007BCC4
    /* 041F44 8007BCC4 27BDFFF8 */  addiu      $sp, $sp, -0x8
    /* 041F48 8007BCC8 AFA00004 */  sw         $zero, 0x4($sp)  ; sum = 0
    /* 041F4C 8007BCCC 10A0001B */  beqz       $a1, .L8007BD3C  ; branch if length == 0
    /* 041F50 8007BCD0 AFA00000 */   sw        $zero, 0x0($sp)  ; i = 0
    .L8007BCD4:
    /* 041F54 8007BCD4 8FAF0000 */  lw         $t7, 0x0($sp)
    /* 041F58 8007BCD8 8FAE0004 */  lw         $t6, 0x4($sp)
    /* 041F5C 8007BCDC 008FC021 */  addu       $t8, $a0, $t7
    /* 041F60 8007BCE0 93190000 */  lbu        $t9, 0x0($t8)    ; a = data[i]
    /* 041F64 8007BCE4 008F5021 */  addu       $t2, $a0, $t7
    /* 041F68 8007BCE8 3B280010 */  xori       $t0, $t9, 0x10
    /* 041F6C 8007BCEC 01C84821 */  addu       $t1, $t6, $t0
    /* 041F70 8007BCF0 AFA90004 */  sw         $t1, 0x4($sp)    ; sum += a ^ 0x10
    /* 041F74 8007BCF4 914B0002 */  lbu        $t3, 0x2($t2)    ; c = data[i+2]
    /* 041F78 8007BCF8 008F6821 */  addu       $t5, $a0, $t7
    /* 041F7C 8007BCFC 012B6023 */  subu       $t4, $t1, $t3
    /* 041F80 8007BD00 AFAC0004 */  sw         $t4, 0x4($sp)    ; sum -= c
    /* 041F84 8007BD04 91B80001 */  lbu        $t8, 0x1($t5)    ; b = data[i+1]
    /* 041F88 8007BD08 008F4021 */  addu       $t0, $a0, $t7
    /* 041F8C 8007BD0C 3B190020 */  xori       $t9, $t8, 0x20
    /* 041F90 8007BD10 01997021 */  addu       $t6, $t4, $t9
    /* 041F94 8007BD14 AFAE0004 */  sw         $t6, 0x4($sp)    ; sum += b ^ 0x20
    /* 041F98 8007BD18 8FAD0000 */  lw         $t5, 0x0($sp)
    /* 041F9C 8007BD1C 910A0003 */  lbu        $t2, 0x3($t0)    ; d = data[i+3]
    /* 041FA0 8007BD20 25B80004 */  addiu      $t8, $t5, 0x4
    /* 041FA4 8007BD24 000A4840 */  sll        $t1, $t2, 1
    /* 041FA8 8007BD28 0305082B */  sltu       $at, $t8, $a1
    /* 041FAC 8007BD2C 01C95823 */  subu       $t3, $t6, $t1
    /* 041FB0 8007BD30 AFB80000 */  sw         $t8, 0x0($sp)    ; i += 4
    /* 041FB4 8007BD34 1420FFE7 */  bnez       $at, .L8007BCD4  ; branch if i < length
    /* 041FB8 8007BD38 AFAB0004 */   sw        $t3, 0x4($sp)    ; sum -= d << 1
    .L8007BD3C:
    /* 041FBC 8007BD3C 8FA20004 */  lw         $v0, 0x4($sp)    ; return sum
    /* 041FC0 8007BD40 03E00008 */  jr         $ra
    /* 041FC4 8007BD44 27BD0008 */   addiu     $sp, $sp, 0x8
    """

    sum = 0
    i = 0
    while i < length:
        if endianness == 'big':
            a, b, c, d = data[offset + i : offset + i + 4]
        else:
            d, c, b, a = data[offset + i : offset + i + 4]

        sum += a ^ 0x10
        sum += b ^ 0x20
        sum -= c
        sum -= d << 1

        i += 4

    return sum & 0xFFFFFFFF

def update_checksum(data, offset, sum, endianness):
    data[offset + 0x18FC : offset + 0x1900] = sum.to_bytes(4, byteorder=endianness)

def main():
    if len(sys.argv) < 3:
        print("Must specify input sram file and output sram file")
        sys.exit(1)
    input_sram_filename = sys.argv[1]
    output_sram_filename = sys.argv[2]

    data = bytearray(open(input_sram_filename, 'rb').read())

    endianness = detect_endianness(data)
    if endianness is None:
        print("error: Unknown endianness", file=sys.stderr)
        sys.exit(1)

    sum = calc_checksum(data, 0, 0x18FC, endianness)
    print(f"0x{sum:08X}")
    update_checksum(data, 0, sum, endianness)

    sum = calc_checksum(data, 0x1900, 0x18FC, endianness)
    print(f"0x{sum:08X}")
    update_checksum(data, 0x1900, sum, endianness)

    sum = calc_checksum(data, 0x3200, 0x18FC, endianness)
    print(f"0x{sum:08X}")
    update_checksum(data, 0x3200, sum, endianness)

    open(output_sram_filename, 'wb').write(data)

if __name__ == "__main__":
    main()
