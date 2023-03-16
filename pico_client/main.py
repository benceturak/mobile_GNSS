import uasyncio as asyncio
import machine
import network
import wifi_config
import http
from identifycation import identifycation
import queue
import socket
import time
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

def checksum(msg):
    cs_a = 0
    cs_b = 0

    for b in msg:
        cs_a = (cs_a + b)%256
        cs_b = (cs_b + cs_a)%256

    return ((cs_b << 8) | cs_a).to_bytes(2,'little')

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

    
    
        
async def queue2tcp(wifi):
    WDT_tcp.feed()
    bin = b''
    while True:
        try:
            while not wifi.isconnected():
                await asyncio.sleep(1)
            tcpReader, tcpWriter = await asyncio.open_connection("ip address", "port")
            id_msg = identifycation(ID)
                
            tcpWriter.write(id_msg)
            
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
                    print("OK")
                
                    try:
                        tcpWriter.write(msg)
                        await tcpWriter.drain()
                        print(msg)
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
                print("Bin reload------------------------------------------------------------")
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
            print("TCP error")
            print(err)
        #print("ReadQueue stops!")

async def startNtrip(wifi):
    while True:
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
    
    while True:
        if not wlan.isconnected():
            print("Connect to wifi...")
            wlan.connect(wifi_config.wireless["SSID"], wifi_config.wireless["PW"])

            while not wlan.isconnected():pass
            print("Wifi connected!")
            
            await asyncio.sleep(1)
    
        await asyncio.sleep(2)
    
        

async def main():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print(1)
    wifi = asyncio.create_task(connectWifi(wlan))
    print(2)
    ntrip = asyncio.create_task(startNtrip(wlan))
    #stream = asyncio.create_task(ublox2tcp(wlan))
    stream = asyncio.create_task(ublox2queue())
    q2t = asyncio.create_task(queue2tcp(wlan))
    #chkTCP = asyncio.create_task(checkTcp(wlan))
    
    print(3)
    
    
    #machine.reset()
    

    while True:
        #WDT_tcp.feed()
        await asyncio.sleep(1)

asyncio.run(main())


















