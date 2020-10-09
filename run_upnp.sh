#!/bin/bash

#activate venv
source venv/bin/activate

#open the ports via port forwarding using PNP
#apt get install miniupnpc
upnpc -r 8554 UDP 8554 UDP
upnpc -r 8554 TCP 8554 TCP

python3 server.py --port 8554 --number-of-players 1 --enable-waitlist 4

upnpc -d 8554 UDP
upnpc -d 8554 TCP
