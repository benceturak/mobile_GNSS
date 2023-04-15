import socket
import uasyncio as asyncio

class HTTP:
    
    def __init__(self, host, port=80):
        self.host = host
        self.port = port
        self.params = []
        self.stopStream = True
        
        
        
    def setUserAgent(self):
        pass
        
    async def _open(self):
        #print("OPEN SOCKET")
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

        #self.soc = socket.socket()
        #self.soc.connect((self.host, self.port))
    
    async def _close(self):
        #print("CLOSE SOCKET")
        await self.writer.close()
        await self.reader.close()
    def addParam(self, param, val):
        self.params.append((param, val))
        
    async def get(self, file=""):
        await self._open()
        msg = "GET /{:s} HTTP/1.0\r\nHost: {:s}\r\n".format(file, self.host)
        
        for p in self.params:
            msg += p[0] + ": " + p[1] + "\r\n"
        
        msg += "\r\n"
        self.writer.write(bytes(msg, "utf8"))
        await self.writer.drain()
        resp = self.waitResp()
        self._parse(resp)
        self._close()
        
    def post(self, file=""):
        msg = "GET /{:s} HTTP/1.0\r\nHost: {:s}\r\n".format(file, self.host)
        
        
        
    async def ntrip(self, mountpoint, func=print):
        await self._open()
        msg = "GET /{1:s} HTTP/1.0\r\nHost: {0:s}\r\n".format(self.host, mountpoint)
        
        for p in self.params:
            msg += p[0] + ": " + p[1] + "\r\n"
        
        msg += "\r\n"
        #print(msg)
        self.writer.write(bytes(msg, "utf8"))
        await self.writer.drain()
        resp = await self.readStream(func)
        
    async def readStream(self, func=print):
        streamStatusOK = False
        
        while not streamStatusOK:
            data = await self.reader.read(100)
            for i in range(0, len(data)):
                if data[i:i+4] == b'\r\n\r\n':
                    self.header = str(data[0:i+4], "utf8")
                    streamStatusOK = True
                    self.stopStream = False
                    break
                    
        
        try:
            while not self.stopStream:
                #await asyncio.wait_for(func(self.reader),5)
                await func(self.reader)
        except Exception as err:
            print(err)
        print("CLOSE NTRIP")
        self._close()
            
    def post(self):
        pass
    
    def waitResp(self):
        resp = b""
        while True:
            data = self.reader.read(100)
            print(data)
            if data:
                resp += data
            else:
                return resp
    
    
    def _parse(self, resp, binary=False):
        i = 0
        
        for i in range(0, len(resp)):
            
            #print(resp[i:i+4])
            if resp[i:i+4] == b'\r\n\r\n':
                self.header = str(resp[0:i+4], "utf8")
                if binary:
                    self.content = resp[i+4:-1]
                else:
                    self.content = str(resp[i+4:-1], "utf8")
                break
            
            i += 1
