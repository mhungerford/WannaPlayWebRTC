#!/bin/bash

#activate venv
source venv/bin/activate

#open the ports via port forwarding using PNP
#apt get install miniupnpc
upnpc -r 8080 UDP 8080 UDP
upnpc -r 8080 TCP 8080 TCP

python3 wannaplaywebrtc/server.py --port 8080 --number-of-players 2 --enable-waitlist 40

upnpc -d 8080 UDP
upnpc -d 8080 TCP
