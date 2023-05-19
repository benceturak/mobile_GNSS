import sys
import os
sys.path.append(os.path.dirname(sys.path[0]))
from common import config
from common import localconfig
import socket
import asyncio
import signal
import _thread
import time
from device import Device
import logging
import threading

logFile = localconfig.basePath + "test.log"
logging.basicConfig(filename=logFile, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# display log in stdout as well
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

def on_new_client(addr, dev):
    print("Connected:", addr)
    logging.info("Connected:" + str(addr))

    shutDevice = threading.Event()
    dev.addShutdownEvent(shutDevice)
    stream2queue = threading.Thread(target=dev.getMsg, args=(True, ))
    stream2queue.start()
    #msgTimeout = threading.Thread(target=dev.msgTimeout, args=(config.tcpTimeout, ))
    #msgTimeout.start()
    watchdog = threading.Thread(target=dev.tcpWatchdog, args=())
    watchdog.start()

    if dev.identify():
        dev.startParser()

    logging.info("Shutting down TCP client handler...")
    dev.close()

    logging.info("Shutting down buffer queue...")
    stream2queue.join()
    watchdog.join()
    
    #logging.info("Shutting down TCP watchdog...")
    #msgTimeout.join()

    logging.info("TCP client handler cleaned up successfully")

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
        serv = socket.create_server((localconfig.server["IP"], localconfig.server["port"]), family=socket.AF_INET)
        serv.settimeout(1)
        print('Server started!')
        print('Waiting for clients...')
        serv.listen(5)

        while run:
            try:
                sock, addr = serv.accept()
                print("Incoming connection, sending ACK...")
                # send useless return msg as aysncio socket doesn't know if TCP handshake was actually done, always returns OK
                sock.send(b'OK')
                dev = Device(sock)
                print("New client connected successfully, starting message loop...")
                _thread.start_new_thread(on_new_client,(addr, dev))
            except socket.timeout:
                await asyncio.sleep(0)
                continue
    except Exception as ex:
        print("Server interrupted: ")
        print(ex)

async def main():
    networkThread = asyncio.create_task(listen())
    await networkThread

def sigintHandler(signal, frame):
    global run
    print("SIGINT, Stopping server...")
    run = False

signal.signal(signal.SIGINT, sigintHandler)

asyncio.run(listen())
