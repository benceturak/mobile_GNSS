import sys
import os
# put UBXParser root next to mobile_GNSS root for this to work
sys.path.append(os.path.dirname(sys.path[0]))
from common import util
from common import config
from common import localconfig
sys.path.append(os.path.join(localconfig.importRoot, 'UBXparser', 'src'))
#sys.path.append(localconfig.importRoot)
#from UBXParser.src import UBXParser
from UBXparser import UBXparser
import UBXmessage
import socket
import queue
import _thread
import logging
import datetime
from datetime import datetime

import time

class Device:

    def __init__(self, sock):
        self.id = None
        self.identifyStatus = 0
        self.sock = sock
        self.sock.settimeout(4)
        self.logger = None



        self.buffer = queue.Queue()
        self.lastMsgTime = datetime.timestamp(datetime.now())

        self.parser = UBXparser(self.buffer)

    def addShutdownEvent(self, event):
        self.shutdown = event
            

    def startNtripProxy(self):
        self.ntripSocket.connect((self.ntrip['ip'], self.ntrip['port']))
        self.ntripSocket.sendall(self.ntrip['get'].encode('ascii'))
        _thread.start_new_thread(self.sendNtrip,())

    def sendNtrip(self):
        while True:

            self.sock.sendall(self.ntripSocket.recv(1024))

    def msgTimeout(self, timeout=10):
        while True:
            if (datetime.timestamp(datetime.now()) - self.lastMsgTime) > timeout:
                logging.warning("Timeout on TCP stream! Device shuts down")
                self.shutdown.set()
                break
            time.sleep(1)

    def tcpWatchdog(self):
        while not self.shutdown.is_set():
            try:
                self.sock.send(config.heartbeatMsg)
            except Exception as err:
                logging.error("Error while trying to send heartbeat: {}".format(err))
            time.sleep(config.heartbeatInterval)
            
    def getMsg(self, saveRaw=False):

        while not self.shutdown.is_set():
            try:
                logging.debug("RECV")
                msg = self.sock.recv(6000)
                
                if len(msg) == 0:
                    continue

                self.lastMsgTime = datetime.timestamp(datetime.now())
                logging.debug("Received {} bytes".format(len(msg)))
                self.buffer.put(msg)
                
                if saveRaw:
                    dt = datetime.utcnow()
                    file_name = localconfig.basePath + "RAW.UBX".format(dt.year, dt.month, dt.day, dt.hour)
                    with open(file_name, 'ab') as file:
                        file.write(msg)
            except socket.timeout as err:
                # socket timeout is normal
                pass
                #logging.error("Socket timed out: ")
                #logging.error(err)
            except OSError as err:
                if err.errno == 10038 and self.shutdown.is_set(): # socket is not a socket (anymore)
                    # recv() throws if socket is closed, that is normal during a shutdown
                    pass
                elif err.errno == 10053 or err.errno == 10054:
                    logging.warning("Connection was actively closed")
                    self.close()
                else:
                    logging.error("Unexpected socket error:")
                    logging.error(err)

            except Exception as err:
                logging.error("Unknown socket exception:")
                logging.error(type(err).__name__)
                logging.error(err)

        return False
    
    def close(self):
        logging.info("Shutting down device...")
        #self.ntripSocket.close()
        self.shutdown.set()
        self.sock.close()

    def identify(self, timeout=10):

        start_ts = datetime.timestamp(datetime.now())

        for msg in self.parser.readQueue(shutFunc=self.shutdown.is_set):
            print(msg)
            
            try:
                if isinstance(msg, UBXmessage.UBX_CUS_ID):
                    self.id = msg.data['ID']
                    return True

            except Exception as err:
                logging.error(err)

            if (datetime.timestamp(datetime.now()) - start_ts) > timeout:
                break

        return False

    def startParser(self):
        file_name = None
        
        epoch = [0, 0]
        buffer = []

        timeStr = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        file_name = localconfig.basePath + "/{}/{}_{}.UBX".format(self.id, self.id, timeStr)
        logging.info("Dump file: " + file_name)

        for msg in self.parser.readQueue(shutFunc=self.shutdown.is_set):
            #if self.shutdown.is_set():
            #    break
            
            try:
                #print(msg.data['iTOW'])
                if not isinstance(msg, UBXmessage.UBX_CUS):
                    buffer.append(msg)
             

                if isinstance(msg, UBXmessage.UBX_CUS_ID):
                    self.id = msg.data['ID']
                    self.logger = logging.getLogger(self.id+".log")
                else:
                    pass
                    #print(msg.data['iTOW'])
                
                if isinstance(msg, UBXmessage.UBX_NAV_TIMEGPS):
                    epoch[0] = msg.data['week']
                    epoch[1] = msg.data['iTOW']/1000
                    
                
                if isinstance(msg, UBXmessage.UBX_NAV_EOE):
                    #iTOW = msg.data['iTOW']/1000

                    day = int(epoch[1]/86400)
                    TOD = epoch[1]%86400
                    hour = int(TOD/3600)

                    

                    if self.id == None:
                        continue
                    #file_name = localconfig.basePath + "/{0:4s}/{0:4s}_{1:04d}{2:1d}_{3:02d}.UBX".format(self.id, epoch[0], day, hour)
                    
                    #print(file_name)
                    #print(len(buffer))

                    try:
                        for i in buffer:
                            #print(i)
                            if file_name != None:
                                #print("WRITE")
                                with open(file_name, "ab") as test:
                                    test.write(i.bin)
                    except Exception as err:
                        print(err)
                    #print("______________")
                    buffer = []

                    
                    
                
            #
            #print(file_name)
            #print(msg)
            except Exception as err:
                logging.error(err)
            
            #print(msg)
            #print(msg.data['iTOW'])
            #print(msg.getEpoch())





    def commandParser(self, command):
        pass
