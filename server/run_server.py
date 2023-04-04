import sys
import os
sys.path.append(os.path.dirname(sys.path[0]))
from common import config
import socket
import asyncio
import signal
import _thread
import time
from device import Device
import logging
import threading

logFile = config.basePath + "test.log"
logging.basicConfig(filename=logFile, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# display log in stdout as well
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

def on_new_client(addr, dev):
    print("Connected:", addr)
    logging.info("Connected:" + str(addr))
    #dev.startNtripProxy()
    #dev.identify()

    shutDevice = threading.Event()
    dev.addShutdownEvent(shutDevice)
    stream2queue = threading.Thread(target=dev.getMsg, args=(True, ))
    stream2queue.start()
    msgTimeout = threading.Thread(target=dev.msgTimeout, args=(8, ))
    msgTimeout.start()
    #_thread.start_new_thread(dev.getMsg, (False,))
    #_thread.start_new_thread(dev.startParser,())

    if dev.identify():
        dev.startParser()

    dev.close()
    logging.info("STOP1")

    stream2queue.join()
    logging.info("STOP2")
    msgTimeout.join()

    logging.info("CLOSE")
    #while True:

        #if dev.getMsg(True) == 0:
            #break
        #msg = clientsocket.recv(1024)
        

        #do some checks and if msg == someWeirdSignal: break:
        #print(msg)
        #clientsocket.sendall(bytes(str(num), 'utf-8'))
    #clientsocket.

def counter(clientsocket, addr):
    print("Connected:", addr)
    num = 10000
    while True:
        #msg = clientsocket.recv(1024)
        #do some checks and if msg == someWeirdSignal: break:
        print(num)
        #clientsocket.sendall(bytes(str(num), 'utf-8'))
        num = num + -1
        time.sleep(1)
    clientsocket.close()


         # Create a socket object


run = True

async def listen():
    try:
        s = socket.create_server((config.server["IP"], config.server["port"]), family=socket.AF_INET)
        print('Server started!')
        print('Waiting for clients...')
        s.listen(5)

        while run:
            c, addr = s.accept()
            print("Incoming connection, sending ACK...")
            # send useless return msg as aysncio socket doesn't know if TCP handshake was actually done, always returns OK
            c.send(b'OK')
            dev = Device(c)
            print("New client connected successfully, starting message loop...")
            _thread.start_new_thread(on_new_client,(addr, dev))
    except Exception as ex:
        print("Server interrupted: ")
        print(ex)

async def main():
    networkThread = asyncio.create_task(listen())
    await networkThread

'''
    for cmd in sys.stdin:
        if 'q' == cmd.rstrip():
            run = False
            print("Exit")
            await networkThread
            break
        print("Unknown command: {}".format(cmd))
'''

def sigintHandler():
    global run
    print("SIGINT, Stopping client...")
    run = False

signal.signal(signal.SIGINT, sigintHandler)

#listen()
asyncio.run(listen())
#asyncio.run(main())

'''
#print('Got connection from', addr)
while True:
   c, addr = s.accept()     # Establish connection with client.
   dev = Device(c)
   _thread.start_new_thread(on_new_client,(addr, dev))
   #_thread.start_new_thread(counter, (1111,2222))
   #Note it's (addr,) not (addr) because second parameter is a tuple
   #Edit: (c,addr)
   #that's how you pass arguments to functions when creating new threads using thread module.
s.close()
'''