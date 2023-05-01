"""
Scales from m bits to n bits.
Assumes v is an unsigned m-bit value.
"""
def scalebits(m, n, v):
    vv = v
    mm = m
    while mm < n:
        vv <<= m
        vv |= v
        mm += m
    return vv >> (mm - n)

def rgba5551_to_rgba8888(raw):
    l = []
    for i in range(0, len(raw), 2):
        r = scalebits(5, 8, raw[i] >> 3)
        g = scalebits(5, 8, ((raw[i] & 0b111) << 2) | (raw[i+1] >> 6))
        b = scalebits(5, 8, (raw[i+1] >> 1) & 0b11111)
        a = scalebits(1, 8, raw[i+1] & 0b1)
        l.extend((r, g, b, a))
    return bytes(l)

def rgba8888_to_rgba5551(raw):
    l = []
    for i in range(0, len(raw), 4):
        r = scalebits(8, 5, raw[i])
        g = scalebits(8, 5, raw[i+1])
        b = scalebits(8, 5, raw[i+2])
        a = scalebits(8, 1, raw[i+3])
        hibyte = (r << 3) | (g >> 2)
        lobyte = ((g & 0b11) << 6) | (b << 1) | a
        l.extend((hibyte, lobyte))
    return bytes(l)
