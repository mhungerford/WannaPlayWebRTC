#!/bin/bash

#open the ports via port forwarding using PNP
#apt get install miniupnpc
upnpc -a 192.168.1.126 8554 8554 UDP
upnpc -a 192.168.1.126 8554 8554 TCP

python3 server.py --port 8554 --number-of-players 2 --enable-waitlist 4

upnpc -d 8554 UDP
upnpc -d 8554 TCP
