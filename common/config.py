# CLIENT CONFIG
ntrip = {
    "IP": "",
    "port": 0,
    "auth": ""
}
wifiReconnectTimeout = 10 # [s]   Time to wait after a WiFi connection attempt for a connection before re-establishing
tcpRetryDelay = 5000      # [ms]  Time to wait inbetween TCP connection attempts
maxFailedMsgCnt = 5       # [1]   Number of failed TCP messages requred to assume TCP connection is down
uartBaudRate = 38400      # [b/s] Baud rate of the UART connection to/from uBlox
ledPin1 = 18
ledPin2 = 19
ledPin3 = 20

# SERVER CONFIG
tcpTimeout = 10           # [s] Time to wait after the last message of a TCP channel before it is considered dead and is actively closed