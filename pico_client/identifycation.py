def checksum(msg):
    cs_a = 0
    cs_b = 0

    for b in msg:
        cs_a = (cs_a + b)%256
        cs_b = (cs_b + cs_a)%256


    #cs_a = cs_a.to_bytes(1, 'big')
    #cs_b = cs_b.to_bytes(1, 'big')

    return ((cs_b << 8) | cs_a).to_bytes(2,'little')

def identifycation(ID):
    msg = b"\xb5\x62\xCA\x01\x04\x00" + ID.encode("ascii")
    
    return msg + checksum(msg[2:])
