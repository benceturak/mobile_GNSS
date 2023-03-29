#!/usr/bin/python3
import asyncio
import sys
import socket               # Import socket module
import _thread
import time
from device import Device
import logging
import threading

#logging.basicConfig()
logging.basicConfig(filename="d:/BME/_ur/2/proj/dump/test.log", level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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

def listen():
    try:
        host = "192.168.0.45" # Get local machine name
        port = 50000                # Reserve a port for your service.
        s = socket.create_server((host,port), family=socket.AF_INET)
        print('Server started!')
        print('Waiting for clients...')
        s.listen(5)

        while run:
            c, addr = s.accept()
            dev = Device(c)
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

listen()
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