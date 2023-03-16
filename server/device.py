import socket
import queue
import _thread
import sys
sys.path.append("/home/bence/data/UBXparser/src")
from UBXparser import UBXparser
import UBXmessage
import logging
from datetime import datetime
import time
class Device:

    def __init__(self, c):
        self.id = None
        self.identifyStatus = 0
        #self.ntrip = {"ip": "152.66.5.152", "port": 2101, "get": "GET /BUTE0 HTTP/1.0\r\nHost: 152.66.5.152\r\nUser-Agent: NTRIP-agent\r\nAuthorization: Basic dHVyYWs6N1E3eWtzQ3c=\r\n\r\n"}
        #self.ntripSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.c = c
        self.c.settimeout(4)
        #self.c.settimeout(5)
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

            self.c.sendall(self.ntripSocket.recv(1024))

    def msgTimeout(self, timeout=10):
        while True:

            logging.info(datetime.timestamp(datetime.now()) - self.lastMsgTime)
            if (datetime.timestamp(datetime.now()) - self.lastMsgTime) > timeout:
                self.shutdown.set()
                break
            time.sleep(1)

        logging.warning("Timeout on TCP stream! Device shuts down")



    def getMsg(self, saveRaw=False):

        while True:
            if self.shutdown.is_set():
                break
            try:
                logging.info("RECV")
                msg = self.c.recv(6000)
                logging.info("AAAAAAAAAAAAAAa")
                logging.info(len(msg))
                if len(msg) == 0:
                    continue
                self.lastMsgTime = datetime.timestamp(datetime.now())
                logging.info("Last message time" + str(self.lastMsgTime))
                #self.c.send(b'received\r\n')
                self.buffer.put(msg)
            except socket.timeout as err:
                logging.error("DSGFSRGTHS")
                logging.error(err)
            except Exception as err:
                logging.error("ERRRRROROORRORORR")
                logging.error(err)
            
            

            if saveRaw:
                dt = datetime.utcnow()
                file_name = "/home/bence/data/nmea_server/RAW/RAW.UBX".format(dt.year, dt.month, dt.day, dt.hour)
                with open(file_name, 'ab') as file:
                    file.write(msg)
            


        return False
    def close(self):
        logging.info("Shut device")
        #self.ntripSocket.close()
        self.shutdown.set()
        self.c.close()

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
                    file_name = "/home/bence/data/nmea_server/{0:4s}/{0:4s}_{1:04d}{2:1d}_{3:02d}.UBX".format(self.id, epoch[0], day, hour)
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
