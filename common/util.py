def checksum(msg):
    cs_a = 0
    cs_b = 0

    for b in msg:
        cs_a = (cs_a + b)%256
        cs_b = (cs_b + cs_a)%256

    return ((cs_b << 8) | cs_a).to_bytes(2,'little')

def bytesToHexStr(b):
    str = b.hex()
    return ' '.join(str[i:i+2] for i in range(0, len(str), 2))