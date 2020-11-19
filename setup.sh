#!/bin/bash
# exit on error
set -e

#enable uinput based virtual joysticks
./wannaplaywebrtc/yoke/yoke-enable-uinput.sh

#install all ubuntu apt packages
sed 's/#.*//' apt-packages.txt | xargs sudo apt-get -y install

#create local virtualenv
if [ ! -d venv ]; then
   python3 -m venv venv
fi


#setup
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
