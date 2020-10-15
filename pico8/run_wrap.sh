#!/bin/bash

#export SDL_VIDEODRIVER=dummy
#export SDL_VIDEO_DUMMY_SAVE_FRAMES=1
#export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/app/.apt/usr/lib/x86_64-linux-gnu/pulseaudio"
#export REMOTEKB_LIBSDL_PATH="/app/.apt/usr/lib/x86_64-linux-gnu/libSDL2-2.0.so.0"
#export REMOTEKB_LIBSDL_PATH="/usr/lib/arm-linux-gnueabihf/libSDL2.so"
#export REMOTEKB_LIBSDL_PATH="/usr/lib/x86_64-linux-gnu/libSDL2-2.0.so.0.8.0"
./remotekb_wrap -p 4321 ./tsi -windowed 1 -width 128 -height 128 -frameless 1 -volume 0 -foreground_sleep_ms 25 -home /tmp
