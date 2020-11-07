# Wanna Play WebRTC
Game streaming platform powered by WebRTC. Allows for desktop games to be shared and played with friends on their desktop browsers or mobile browser (ex: iPhone, Android).

:video_game: :keyboard: :vibration_mode: \
Play it now, live at: [http://wanna.play.ai](http://wanna.play.ai) \
Hosted on Raspberry Pi 4 \
:iphone: :computer: :desktop_computer:

## Mobile Browser (and desktop) support
Provides an HTML interface with touchscreen gamepad, keyboard support, and low-latency video playback.

## Python Powered
- AIORTC python framework provides WebRTC support.  
- Yoke python library provides virtual joysticks (uinput based on Linux, vJoy based on Windows).
- MSS python library utilized for fast screenshot grabbing.
- PyAV library enables low-latency H.264 video encoding of video game screen.
- UPnPy provides UPnP based port-forwarding to allow remote users access to game server.

## Desktop Game support
Select game by it's "Window Name", places window in focus and retrieves window information necessary for screen-grabbing game images.  Full-screen games not recommended due to high-resolution causing h.264 encoding and transmission lag.

## Optimized for libSDL based games
SDL provides a render-to-image backend that avoids rendering to graphics then using a screen-grabbing library to retrieve those images.  Avoids issues of window detection, rendering latency, and window focus (joystick focus is forced).

SDL based games on Linux require the Yoke controller layout below (add to ~.bashrc, or export directly before launching that game from command line)
```export SDL_GAMECONTROLLERCONFIG='06000000596f6b650000000000000000,Yoke,platform:Linux,a:b0,b:b1,dpup:b2,dpdown:b3,dpleft:b4,dpright:b5,'"```

## Pico-8 special support
Pico-8 is a great fantasy console platform with thousands of free retro style games, with up to 4 player joystick support.  Thanks to its 128x128 resolution, it can be encoded in software on a Raspberry Pi without issue and requires little bandwidth.

## Installation
This platform was written to be cross-platform, but several features are only tested on Linux.  The included Pico-8 game is only setup to run on Linux (x86_64 and Raspberry Pi).

Note: There is a convenience script "setup.sh" that will do the below inside of a python virtualenvironment (venv).

On Ubuntu:
```
#enable uinput based virtual joysticks
./src/yoke/yoke-enable-uinput.sh

#install all ubuntu apt packages
sed 's/#.*//' apt-packages.txt | xargs sudo apt-get install

#setup
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Usage considerations and notes
- Does not work in Heroku or PythonAnywhere due to UDP incoming and outgoing being blocked.
- 
