import uasyncio as asyncio
import machine
import network
from pico_client import wifi_config
from pico_client import http
from pico_client import queue
import socket
import time
import sys
#uart = UART(4, 9600, timeout=0)  # timeout=0 prevents blocking at low baudrates
uart = machine.UART(1, baudrate=38400, bits=8, parity=None, tx=machine.Pin(8), rx=machine.Pin(9))
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

async def rtcm2ublox(tcpReader):
    #print("AAAAAAAAAAA")
    data = await tcpReader.read(5000)
    #print(data)
    swriter.write(data)
    await swriter.drain()  # Transmission starts now.
    
async def ublox2queue():
    print("PFPFPFPFPFPFP")
    while True:
        res = await sreader.read(10000)
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
            tcpReader, tcpWriter = await asyncio.open_connection("192.168.0.45", 50000)
            id_msg = identifycation(ID)
            tcpWriter.write(id_msg)
            print("Connection is UP, streaming...")
            
            while True:
                try:
                    bin += q.get_nowait()
                    
                except Exception as err:
                    await asyncio.sleep(1)
                    continue
                    #print("Queue error!")
                    #logging.warning("Queue timeout! Queue is empty!")
                #logging.info("GET FROM QUEUE")

                binLen = len(bin) 
                lastMsgEnd = 0 
            
                if binLen < 6:
                    continue
                for i in range(0, binLen):
                    if bin[i:i+2] != pream:
                        continue
                    #print("AAA")
                    msglen = int.from_bytes(bin[i+4:i+6], 'little')
                    startIndex = i
                    endIndex = i + msglen + 8

                    if len(bin) < endIndex:
                        #print("Message length error!")
                        continue
                    msg = bin[startIndex:endIndex]  
                

                    cs = msg[6+msglen:6+msglen+2]

                    if cs != checksum(msg[2:6+msglen]):
                        #logging.warning("_______________________")
                        #logging.warning(startIndex)
                        #logging.warning(msg)
                        #logging.warning(msg[2:6+msglen])
                        #print("Checksum")
                        #print(checksum(msg[2:6+msglen]))
                        #print(cs)
                        #logging.warning(len(msg))

                        continue
                    #print("OK")
                
                    try:
                        tcpWriter.write(msg)
                        await tcpWriter.drain()
                        #print(msg)
                        WDT_tcp.feed()

                        lastMsgEnd = endIndex
                    except Exception as err:
                        print(err)
                        
                        #print("error")
                        #print(err)
                        #print(msg)
                        #print(err)
                    
                            
                #print(lastMsgEnd)
            
                bin = bin[lastMsgEnd:]
                #print(bin)
                #print("Bin reload------------------------------------------------------------")
                '''
                try:
                    print("01")
                    
                    bin += q.get_nowait()
                    print(len(bin))
                    print("02")
                    if len(bin) > 0:
                        tcpWriter.write(bin)
                        await tcpWriter.drain()
                        WDT_tcp.feed()
                        print("FEED")
                        bin = b''
                    
                except Exception as err:
                    await asyncio.sleep(1)
                    print("Queue error!")
                    print(type(err))
                '''
        except Exception as err:
            retryCnt += 1
            print("TCP error on try #{}, retrying in 1s...".format(retryCnt))
            print(err)
            await asyncio.sleep(1)
        #print("ReadQueue stops!")
    print("End of tries, go kill myself")

async def startNtrip(wifi):
    global run
    while run:
        try:
            print(0)
            while not wifi.isconnected():
                await asyncio.sleep(1)
            print(1)
            
            client = http.HTTP("ip address", 2101)
            client.addParam("User-Agent", "NTRIP-agent")
            client.addParam("Authorization", "Authorization")

            
            await client.ntrip("BUTE0", rtcm2ublox)
            
            await asyncio.sleep(1)
        except Exception as err:
            print("Ntrip error")
            print(err)


        

async def connectWifi(wlan):
    global run
    while run:
        if not wlan.isconnected():
            print("Connect to wifi...")
            wlan.connect(wifi_config.wireless["SSID"], wifi_config.wireless["PW"])

            while not wlan.isconnected():pass
            print("Wifi connected!")
            
            await asyncio.sleep(1)
    
        await asyncio.sleep(2)
    
        

async def main():
    global run
    print(0)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print(1)
    wifi = asyncio.create_task(connectWifi(wlan))
    print(2)
    #ntrip = asyncio.create_task(startNtrip(wlan))
    #stream = asyncio.create_task(ublox2tcp(wlan))
    #stream = asyncio.create_task(ublox2queue())
    stream = asyncio.create_task(ublox2queue_sim())
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
    while True:
        #WDT_tcp.feed()
        await asyncio.sleep(1)

asyncio.run(main())


















