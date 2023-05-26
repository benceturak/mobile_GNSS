import uasyncio as asyncio
import machine
import network
import micropython
from common import config
from common import localconfig
from common import util
from pico_client import http
from pico_client import queue
import time
from pico_client.ringBuffer import RingBuffer
uart = machine.UART(1, baudrate=config.uartBaudRate, bits=8, parity=None, tx=machine.Pin(8), rx=machine.Pin(9))
#q = queue.Queue()
#parser = ubxparser.UBXParser(q)
ID = "TES1"
status_ntrip=0
status_wifi=0
status_tcp=0
pream = b'\xb5\x62'

maxMissedHeartbeatCnt = config.maxLostConnectionTime / config.heartbeatInterval

ntripLed = machine.Pin(config.ledPin1, machine.Pin.OUT)
wifiLed = machine.Pin(config.ledPin2, machine.Pin.OUT)
tcpLed = machine.Pin(config.ledPin3, machine.Pin.OUT)
wifiLed.low()
tcpLed.low()
ntripLed.high()
time.sleep(0.1)
ntripLed.low()
wifiLed.high()
time.sleep(0.1)
wifiLed.low()
tcpLed.high()
time.sleep(0.1)
tcpLed.low()

q = queue.Queue()

#WDT_tcp = machine.WDT(timeout=8000)
#WDT_ntrip = machine.WDT(timeout=8000)

sreader = asyncio.StreamReader(uart)
swriter = asyncio.StreamWriter(uart, {})

run = True
wlanConnected = False
serverConnected = False
ntripConnected = False

heartbeatTik = True

def statusLeds(timer):
    global heartbeatTik
    print("Scheduler heartbeat " + ("tik" if heartbeatTik else "tok"))
    heartbeatTik = not heartbeatTik
    wifiLed.value(wlanConnected)
    time.sleep(0.1)
    wifiLed.low()
    tcpLed.value(serverConnected)
    time.sleep(0.1)
    tcpLed.low()
    ntripLed.value(ntripConnected)
    time.sleep(0.1)
    ntripLed.low()

statusLedTimer = machine.Timer()
statusLedTimer.init(period=5000, mode=machine.Timer.PERIODIC, callback=statusLeds)

ntripBuffer = bytearray(5000)
ubxBuffer = bytearray(10000)
queueBuffer = RingBuffer(10000)
tcpBuffer = bytearray(10000)

def identifycation(ID):
    msg = b"\xb5\x62\xCA\x01\x04\x00" + ID.encode("ascii")
    return msg + util.checksum(msg[2:])

async def rtcm2ublox(tcpReader):
    global ntripConnected
    global ntripBuffer
    print("NTRIP heartbeat")

    bytesRead = await tcpReader.readinto(ntripBuffer)
    if not ntripConnected and bytesRead > 0:
        print("NTRIP connection is UP")
        ntripConnected = True

    swriter.write(ntripBuffer)
    await swriter.drain()  # Transmission starts now.
    
async def ublox2queue():
    global run
    global queueBuffer
    print("Listening on UART...")
    while run:
        print("UART heartbeat")
        bytesRead = await sreader.readinto(ubxBuffer)
        #WDT_tcp.feed()
        #print("Read {} bytes from UART".format(len(res)))
        #await q.put(ubxBuffer)
        queueBuffer.putFrom(ubxBuffer, 0, bytesRead)

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

    msgChecksum = util.checksum(msgHeader + msgPayload)

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
    global wlanConnected
    global serverConnected
    #WDT_tcp.feed()
    bin = b''
    bufferLen = 0
    retryCnt = 0
    failedMsgCnt = 0
    missedHeartbeatCnt = 0
    connected = False
    while run:
        try:
            while run:
                # check WiFi
                if not wifi.isconnected():
                    wlanConnected = False
                    if connected:
                        print("WiFi connection lost while TCP channel was active")
                        connected = False
                    await asyncio.sleep(1)
                    continue
                else:
                    wlanConnected = True
                
                # check TCP
                if not connected:
                    serverConnected = False
                    print("WiFi connection is UP, establishing TCP connection...")
                    while run:
                        try:
                            tcpReader, tcpWriter = await asyncio.open_connection(localconfig.server["IP"], localconfig.server["port"])
                            break
                        except Exception as err:
                            retryCnt += 1
                            retryDelay = config.tcpRetryDelay / 1000
                            print("TCP error on try #{}, retrying in {}s...".format(retryCnt, retryDelay))
                            print(err)
                            await asyncio.sleep(retryDelay)
                            continue
                    
                    print("TCP channel established, awaiting TCP handshake...")

                    retryCnt = 0
                    while run and not connected:
                        try:
                            ack = await asyncio.wait_for(tcpReader.read(2), timeout=1)
                            if ack == b'OK':
                                print("TCP handshake completed, connection is UP")
                                retryCnt = 0
                                missedHeartbeatCnt = 0
                                id_msg = identifycation(ID)
                                tcpWriter.write(id_msg)
                                tcpWriter.drain()
                                connected = True
                                serverConnected = True
                            else:
                                print("TCP channel is up, but server handshake was invalid")
                                tcpReader.close()
                                tcpWriter.close()
                                await tcpReader.wait_closed()
                                await tcpWriter.wait_closed()
                        except asyncio.TimeoutError:
                            print("Still awaiting TCP handshake...")
                            retryCnt += 1
                            if retryCnt > config.maxFailedMsgCnt:
                                print("Did not receive handshake in time, retrying connection...")
                                tcpReader.close()
                                tcpWriter.close()
                                await tcpReader.wait_closed()
                                await tcpWriter.wait_closed()
                                break
                            else:
                                continue
                        except Exception as err:
                            print("Exception while writing TCP:")
                            print(err)
                            break

                # detect connection loss
                try:
                    resp = await asyncio.wait_for(tcpReader.read(1), timeout=config.heartbeatInterval)
                    # if read didn't time out, we (presumably) received heartbeat
                    if resp == config.heartbeatMsg:
                        missedHeartbeatCnt = 0
                    else:
                        missedHeartbeatCnt += 1
                except asyncio.TimeoutError:
                    missedHeartbeatCnt += 1
                    print("Missed heartbeat #" + str(missedHeartbeatCnt))
                    pass
                except OSError as err:
                    if err.errno == 104 or err.errno == 103: # ECONNRESET || ECONNABORTED
                        print("TCP connection lost, reconnecting...")
                        connected = False

                        tcpReader.close()
                        tcpWriter.close()
                        await tcpReader.wait_closed()
                        await tcpWriter.wait_closed()
                        continue
                    else:
                        print("Unexpected TCP OS error while checking connection:")
                        print(err)
                        continue
                except Exception as err:
                    print("Exception while checking TCP link:")
                    print(err)
                    continue

                if missedHeartbeatCnt > maxMissedHeartbeatCnt:
                    print("Lost server hearbeat, reconnecting...")
                    connected = False

                    tcpReader.close()
                    tcpWriter.close()
                    await tcpReader.wait_closed()
                    await tcpWriter.wait_closed()
                    continue


                # === END OF CONNECTION HANDLING ===
                print("Process heartbeat")
                
                # do the real work
                try:
                    bufferLen += queueBuffer.popInto(tcpBuffer, bufferLen, len(tcpBuffer) - bufferLen)
                    #bin += await asyncio.wait_for(q.get(), timeout=1)
                except queue.QueueEmpty:
                    print("Queue empty")
                    await asyncio.sleep(0)
                    continue
                except asyncio.TimeoutError:
                    # No data, yield and look for termination signal
                    await asyncio.sleep(0)
                    continue
                except Exception as err:
                    print("Error while reading queue: " + str(err))
                    await asyncio.sleep(0)
                    continue

                #binLen = len(bin)
                lastMsgEnd = 0 
            
                if bufferLen < 6:
                    continue

                # DEBUG
                #print("Buffer length = " + str(binLen))
                #print(util.bytesToHexStr(bin))

                i = 0
                while i < bufferLen:
                #for i in range(0, binLen):

                    if tcpBuffer[i:i+2] != pream:
                        #print("Did not find start bits in stream - maybe started in situ?")
                        i += 1
                        continue

                    msgLen = int.from_bytes(tcpBuffer[i+4:i+6], 'little')
                    startIndex = i
                    endIndex = i + msgLen + 8

                    if bufferLen < endIndex:
                        print("Awaiting message of length {}B, but so far only {}B received, waiting...".format(endIndex - startIndex, bufferLen - startIndex))
                        break

                    #print("Found complete message in queue")
                    msg = tcpBuffer[startIndex:endIndex]
                    #cs = msg[6+msgLen:6+msgLen+2]

                    #if cs != util.checksum(msg[2:6+msgLen]):
                        #print("Invalid checksum: {} instead of {}".format(util.bytesToHexStr(msg[msgLen-2:msgLen]), util.bytesToHexStr(util.checksum(msg[2:6+msgLen]))))
                        #continue

                    #print("Sending message via TCP...")
                
                    for sendRetryCnt in range(1,config.maxFailedMsgCnt):
                        try:
                            print("Sending message (len: {}), try #{}".format(len(msg), sendRetryCnt))
                            tcpWriter.write(msg)
                            await asyncio.wait_for(tcpReader.drain(), timeout=0.2)
                            i = endIndex
                            #print("Send successful")
                            
                            #WDT_tcp.feed()

                            lastMsgEnd = endIndex
                            print("Sent OK")
                            break
                        except asyncio.TimeoutError:
                            print("Timeout when trying to send message on try #{}".format(sendRetryCnt))
                            if sendRetryCnt >= config.maxFailedMsgCnt - 1:
                                print("Assuming connection is down")
                                connected = False
                                serverConnected = False
                                tcpReader.close()
                                tcpWriter.close()
                                await tcpReader.wait_closed()
                                await tcpWriter.wait_closed()
                                break

                        except Exception as err:
                            print("Sending TCP packet unsuccessful: " + str(err))
                            failedMsgCnt += 1
                            if failedMsgCnt >= config.maxFailedMsgCnt:
                                print("TCP connection is assumed down, reconnecting...")
                                connected = False
                    
                    if connected:
                        continue
                    else:
                        break
            
                tcpBuffer[0 : bufferLen - lastMsgEnd] = tcpBuffer[lastMsgEnd : bufferLen]
                bufferLen -= lastMsgEnd
                # trim buffer
                #bin = bin[lastMsgEnd:]

        except Exception as err:
            print("Unhandled exception in message queue:")
            print(err)
            await asyncio.sleep(0)

    print("Go kill myself")
    statusLedTimer.deinit()

async def startNtrip(wifi):
    global run
    while run:
        try:
            while not wifi.isconnected():
                await asyncio.sleep(1)

            print("Connecting to NTRIP...")
            
            client = http.HTTP(config.ntrip["IP"], config.ntrip["port"])
            client.addParam("User-Agent", "NTRIP-agent")
            client.addParam("Authorization", config.ntrip["auth"])
            
            await client.ntrip("BUTE0", rtcm2ublox)

            print("NTRIP connection terminated")
            
            await asyncio.sleep(1)
        except Exception as err:
            print("Ntrip error")
            print(err)

    await asyncio.sleep(1) # asyncio is not preemtive, so yield()

async def connectWifi(wlan):
    global run
    while run:
        if not wlan.isconnected():
            print("Connecting to WiFi: {}...".format(localconfig.wireless["SSID"]))
            wlan.connect(localconfig.wireless["SSID"], localconfig.wireless["PW"])
            retryCnt = 0
            while not wlan.isconnected() and retryCnt < config.wifiReconnectTimeout:
                if not run:
                    break
                await asyncio.sleep(1)
                #WDT_tcp.feed()
                print("Still connecting to WiFi...")
                retryCnt += 1
            if wlan.isconnected():
                print("Wifi connected!")
                retryCnt = 0
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

    ntrip = asyncio.create_task(startNtrip(wlan))
    #stream = asyncio.create_task(ublox2tcp(wlan))

    stream = asyncio.create_task(ublox2queue())
    #stream = asyncio.create_task(ublox2queue_sim())

    q2t = asyncio.create_task(queue2tcp(wlan))
    #chkTCP = asyncio.create_task(checkTcp(wlan))
    
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
    except Exception as ex:
        print("Exception on MAIN:")
        print(ex)

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Manual interrupt, Stopping client...")
    run = False
    statusLedTimer.deinit()
except MemoryError as err:
    print("Memory error: {}".format(err))
    print(micropython.mem_info(1))
except Exception as ex:
    print("Globally unhandled exception: {}".format(ex))
    run = False
    statusLedTimer.deinit()

