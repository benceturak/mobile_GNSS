import uasyncio as asyncio
import machine
import network
from common import config
from pico_client import http
from pico_client import queue
import socket
import time
import sys
#uart = UART(4, 9600, timeout=0)  # timeout=0 prevents blocking at low baudrates
uart = machine.UART(1, baudrate=4800, bits=8, parity=None, tx=machine.Pin(8), rx=machine.Pin(9))
#q = queue.Queue()
#parser = ubxparser.UBXParser(q)
ID = "TES1"
status_ntrip=0
status_wifi=0
status_tcp=0
pream = b'\xb5\x62'

q = queue.Queue()

WDT_tcp = machine.WDT(timeout=8000)
#WDT_ntrip = machine.WDT(timeout=8000)

sreader = asyncio.StreamReader(uart)
swriter = asyncio.StreamWriter(uart, {})

maxRetryCnt = 3
run = True

def checksum(msg):
    cs_a = 0
    cs_b = 0

    for b in msg:
        cs_a = (cs_a + b)%256
        cs_b = (cs_b + cs_a)%256

    return ((cs_b << 8) | cs_a).to_bytes(2,'little')

def identifycation(ID):
    msg = b"\xb5\x62\xCA\x01\x04\x00" + ID.encode("ascii")
    return msg + checksum(msg[2:])

def bytesToHexStr(b):
    str = b.hex()
    return ' '.join(str[i:i+2] for i in range(0, len(str), 2))

async def rtcm2ublox(tcpReader):
    #print("AAAAAAAAAAA")
    data = await tcpReader.read(5000)
    #print(data)
    swriter.write(data)
    await swriter.drain()  # Transmission starts now.
    
async def ublox2queue():
    print("Listening on UART...")
    while True:
        res = await sreader.read(10000)
        WDT_tcp.feed()
        #print("Read {} bytes from UART".format(len(res)))
        await q.put(res)

async def ublox2queue_sim():
    global run
    print("SIM gen default MSG")

    msgPream = b'\xb5\x62'
    msgClass = b'\x01'
    msgId = b'\x02'
    msgLength = (28).to_bytes(2, 'little')
    msgHeader = msgClass + msgId + msgLength
    #
    iTOW = (0).to_bytes(4, 'little')
    lon = (190000000).to_bytes(4, 'little')
    lat = (470000000).to_bytes(4, 'little')
    height = (0).to_bytes(4, 'little')
    hMSL = (0).to_bytes(4, 'little')
    hAcc = (0).to_bytes(4, 'little')
    vAcc = (0).to_bytes(4, 'little')
    msgPayload = iTOW + lon + lat + height + hMSL + hAcc + vAcc

    msgChecksum = checksum(msgHeader + msgPayload)

    msg = msgPream + msgHeader + msgPayload + msgChecksum
    msgId = 0

    print("SIM starting")

    while run:
        print("SIM gen msg #{}".format(msgId))
        await q.put(msg)
        msgId += 1
        await asyncio.sleep(0.2)
        
async def queue2tcp(wifi):
    global run
    WDT_tcp.feed()
    bin = b''
    retryCnt = 0
    while run and retryCnt < maxRetryCnt:
        try:
            while run and not wifi.isconnected():
                await asyncio.sleep(1)

            print("Trying to connect to server...")
            tcpReader, tcpWriter = await asyncio.open_connection(config.server["IP"], config.server["port"])
            print("Awaiting TCP handshake...")

            # useless return msg as aysncio socket doesn't know if TCP handshake was actually done, always returns OK
            ack = await tcpReader.read(2)
            if ack == b'OK':
                print("TCP connection is up, streaming...")
            else:
                print("TCP connection is up, but server handshake with invalid!")

            id_msg = identifycation(ID)
            tcpWriter.write(id_msg)
            
            while True:
                try:
                    #bin += q.get_nowait()
                    bin += await q.get()
                except queue.QueueEmpty:
                    print("Queue empty")
                    await asyncio.sleep(0)
                    pass
                except Exception as err:
                    print("Error while reading queue: " + str(err))
                    await asyncio.sleep(1)
                    continue

                binLen = len(bin)
                lastMsgEnd = 0 
            
                if binLen < 6:
                    continue

                # DEBUG
                #print("Buffer length = " + str(binLen))
                #print(bytesToHexStr(bin))

                for i in range(0, binLen):

                    if bin[i:i+2] != pream:
                        #print("Did not find start bits in stream - maybe started in situ?")
                        continue

                    msgLen = int.from_bytes(bin[i+4:i+6], 'little')
                    startIndex = i
                    endIndex = i + msgLen + 8

                    if binLen < endIndex:
                        print("Awaiting message of length {}B, but so far only {}B received, waiting...".format(endIndex - startIndex, binLen - startIndex))
                        continue

                    #print("Found complete message in queue")
                    msg = bin[startIndex:endIndex]
                    cs = msg[6+msgLen:6+msgLen+2]

                    if cs != checksum(msg[2:6+msgLen]):
                        print("Invalid checksum: {} instead of {}".format(msg[msgLen-2:msgLen], checksum(msg[2:6+msgLen])))
                        #continue

                    #print("Sending message via TCP...")
                
                    try:
                        tcpWriter.write(msg)
                        await tcpWriter.drain()
                        #print("Send successful")
                        
                        WDT_tcp.feed()

                        lastMsgEnd = endIndex
                    except Exception as err:
                        print("Sending TCP packet unsuccessful: " + str(err))
            
                # trim buffer
                bin = bin[lastMsgEnd:]

        except Exception as err:
            retryCnt += 1
            print("TCP error on try #{}, retrying in 1s...".format(retryCnt))
            print(err)
            await asyncio.sleep(1)

    print("End of tries, go kill myself")

async def startNtrip(wifi):
    global run
    while run:
        try:
            print(0)
            while not wifi.isconnected():
                await asyncio.sleep(1)
            print(1)
            
            client = http.HTTP(config.ntrip["IP"], config.ntrip["port"])
            client.addParam("User-Agent", "NTRIP-agent")
            client.addParam("Authorization", "Authorization")

            
            await client.ntrip("BUTE0", rtcm2ublox)
            
            await asyncio.sleep(1)
        except Exception as err:
            print("Ntrip error")
            print(err)

    await asyncio.sleep(5) # asyncio is not preemtive, so yield()

async def connectWifi(wlan):
    global run
    while run:
        if not wlan.isconnected():
            print("Connecting to WiFi...")
            wlan.connect(config.wireless["SSID"], config.wireless["PW"])
            while not wlan.isconnected():
                if not run:
                    break
                await asyncio.sleep(1)
                WDT_tcp.feed()
                print("Still connecting to WiFi...")
            if wlan.isconnected():
                print("Wifi connected!")
                await asyncio.sleep(1)
            else:
                print("WiFi connection interrupted")
        await asyncio.sleep(3)

async def main():
    global run

    print("Setting up WiFi...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wifi = asyncio.create_task(connectWifi(wlan))

    #ntrip = asyncio.create_task(startNtrip(wlan))
    #stream = asyncio.create_task(ublox2tcp(wlan))

    stream = asyncio.create_task(ublox2queue())
    #stream = asyncio.create_task(ublox2queue_sim())

    q2t = asyncio.create_task(queue2tcp(wlan))
    #chkTCP = asyncio.create_task(checkTcp(wlan))
    
    print(3)
    
    #machine.reset()
    '''
    for cmd in sys.stdin:
        if 'q' == cmd.rstrip():
            run = False
            print("Exit")
            await wifi
            await stream
            await q2t
            break
        print("Unknown command: {}".format(cmd))
    '''
    try:
        while True:
            #WDT_tcp.feed()
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Ctrl+C, Stopping client...")
        run = False
    except Exception as ex:
        print("Exception on MAIN:")
        print(ex)

asyncio.run(main())
