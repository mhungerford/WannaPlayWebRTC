#!/usr/bin/env bash

# sudo addgroup uinput
# sudo adduser $USER uinput

# short term
# sudo chgrp uinput /dev/uinput # change group
# sudo chmod g+rwx /dev/uinput # allow group to read and write

echo "Adding new user group called \"uinput\""
sudo groupadd uinput
sudo gpasswd -a $USER uinput

echo "Copying rules to /etc/udev/rules.d/"
sudo tee /etc/udev/rules.d/40-uinput-yoke.rules > /dev/null << 'EOF'
KERNEL=="uinput", MODE="0660", GROUP="uinput"
EOF

echo "Reloading /etc/udev/rules.d/ ..."
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "Done. For the changes to take effect, log in again or type \"su $USER\"".
