import argparse
import json
import logging
import os
import ssl
import sys, traceback
from time import sleep, time
from collections import namedtuple
from pathlib import Path

import asyncio
from aiohttp import web
from aiortc import RTCPeerConnection, RTCConfiguration, RTCSessionDescription
from aiortc import RTCIceCandidate, RTCIceServer
from aiortc import VideoStreamTrack
import av
from multiprocessing import Process, RawArray
from easyprocess import EasyProcess

#support UPNP port forwarding
from upnpportforward import UPNPPortForward

#desktop screenshot support
from mss import mss
import PIL
from PIL import Image
import numpy as np

#grab window support (for apps launched prior to this server)
from grabwindow import GrabWindow

#Virtual Joystick or Virtual Keyboard dependencies
from yoke import yoke # requires uinput and udev.rules (ie. root) (supports 4 controllers)
from sdlkbdsim import SdlKbdSim # requires sdlwrap binary use (supports keyboard)

# optional gpio controller
p1gpios = [23,24,25]
p2gpios = [17,22,27]
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM) #use gpio numbers
    GPIO.setup(p1gpios, GPIO.OUT)
    GPIO.setup(p2gpios, GPIO.OUT)
except RuntimeError:
    print("Error importing RPi.GPIO!  Check permissions, usergroup gpio.")
except ImportError:
    pass

# optional, for better performance than asyncio default loop
try:
    import uvloop
    print("using uvloop for performance")
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#list of Peer Connections to track
pcs = []
pcs_max_size = 0

shared_image_array = None

#instance of SdlKbdSim for keyboard control
sdlkbdsim = SdlKbdSim()

#Note: Don't forget to sdl_controller map these
#yoke.EVENTS.BTN_START, 
events = [
    yoke.EVENTS.BTN_SOUTH,
    yoke.EVENTS.BTN_EAST,
    yoke.EVENTS.BTN_DPAD_UP,
    yoke.EVENTS.BTN_DPAD_LEFT,
    yoke.EVENTS.BTN_DPAD_DOWN,
    yoke.EVENTS.BTN_DPAD_RIGHT
    ]

#list of js allocated
jslist = []
JSDev = namedtuple("JSDev",['dev', 'locked', 'idx'])

#list of pico8 games to switch between in pico mode
gamelist = ['painters', 'doodle_jump', 'they_started_it', 'heman']
gameidx = 0

def jsupdate_vals(js, vals):
  if isinstance(js, yoke.Device):
    for idx, state in enumerate(vals):
      js.emit(events[idx], int(state))
    js.flush()
  elif isinstance(js, str):
    for idx, state in enumerate(vals):
      gpiojs = p1gpios if (js == "gpio_js1") else p2gpios
      if (idx == 0):
        GPIO.output(gpiojs[0], int(state))
      elif (idx == 3):
        GPIO.output(gpiojs[1], int(state))
      elif (idx == 5):
        GPIO.output(gpiojs[2], int(state))
  else:
    for idx, state in enumerate(vals):
      sdlkbdsim.setkey(idx, int(state))


#grab and decode images in a background process and store to shared mp array
def process_dumped_images(shared_image_array,
    image_path='/tmp/sdl', image_prefix='SDL_window2-', image_format='bmp'):

  last_time = time()

  while True:
    pics = list(Path(image_path).glob(image_prefix + '*.' + image_format))
    if len(pics) > 0:
      lastpic = pics[-1]
      filesize = lastpic.stat().st_size
      if filesize >= 49206:
        try:
          with Image.open(lastpic) as img:
            imb = img.tobytes()
            shared_image_array[:] = imb
          for pic in pics:
            pic.unlink()
        except OSError:
          pass
        except PIL.UnidentifiedImageError:
          pass
    curr_time = time()
    sleep(max(0, 0.033 - (curr_time - last_time))) # ~30 FPS image retrieval
    last_time = curr_time


#capture images in a background process and store to shared mp array
def process_capture_images(shared_image_array,
    window_position=(0, 0), window_size=(128, 128)):
  sct = mss()
  sct.compression_level = 0 # disable screenshot compression (for performance)
  # The screen part to capture
  monitor = {
      "top": window_position[1], 
      "left": window_position[0], 
      "width": window_size[0],
      "height": window_size[1]
      }
  last_time = time()

  while True:
    # Grab the data
    sct_img = sct.grab(monitor)
    img_np = np.array(sct_img)
    # "interpret" buffer as numpy array
    img_wrap = np.frombuffer(shared_image_array, img_np.dtype).reshape(img_np.shape)
    np.copyto(img_wrap, img_np)

    curr_time = time()
    sleep(max(0, 0.033 - (curr_time - last_time))) # ~30 FPS image retrieval
    last_time = curr_time



class VideoImageTrack(VideoStreamTrack):
    """
    A video stream track that returns a rotating image.
    """

    kind = "video"

    def __init__(self):
        super().__init__()  # don't forget this!

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        # "interpret" Shared Buffer Image as numpy array
        #raw_image = np.frombuffer(shared_image_array, np.uint8).reshape(win_w, win_h, 4)
        raw_image = np.frombuffer(shared_image_array, np.uint8).reshape(win_h, win_w, image_depth)
        #img = cv2.imread("/tmp/screenshot.png", cv2.IMREAD_COLOR)

        # create video frame
        #frame = av.VideoFrame.from_ndarray(raw_image, format="bgra")
        if image_depth == 3:
          frame = av.VideoFrame.from_ndarray(raw_image, format="rgb24")
        else:
          frame = av.VideoFrame.from_ndarray(raw_image, format="bgra")
        frame.pts = pts
        frame.time_base = time_base
        
        return frame



async def index(request):
    content = open(Path(PROJECT_ROOT, "public_html/index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def offer(request):
    #cap rtc peers at <X>
    if len(pcs) > pcs_max_size:
      return
    
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    uuid = str(params["uuid"])

    pc = next((x for x in pcs if x.uuid == uuid), None)

    if pc is None:
      pc = RTCPeerConnection()
#          configuration=RTCConfiguration(
#            iceServers=[
#            RTCIceServer(urls=["stun:stun.l.google:19302"]),
#            RTCIceServer(urls=["turn:0.peerjs.com:3478"], username="peerjs", credential="peerjsp"),
#            RTCIceServer(urls=["turn:turn.bistri.com:80"], username="homeo", credential="homeo"),
#            RTCIceServer(urls=["turn:turn.anyfirewall.com:443"], username="webrtc", credential="webrtc")
#            ]))

      setattr(pc, 'uuid',uuid)
      pcs.append(pc)
    
      @pc.on("datachannel")
      def on_datachannel(channel):
          print("Channel id: {}".format(channel.id))
          #print("queue position: {}".format(pcs.index(pc)))
          #This transport monitor is necessary, otherwise
          #a closed connection breaks the server on the next connection
          async def monitor():
            while True:
              if channel.transport.transport.state == "closed":
                await pc.close()
                js = getattr(pc, 'js', None)
                if js is not None:
                  jsdev = next((x for x in jslist if x.dev == js), None)
                  if jsdev is not None:
                    print("Freeing joystick:{}".format(jsdev.idx))
                    jslist[jslist.index(jsdev)] = jsdev._replace(locked =  False)
                try:
                  pcs.remove(pc)
                except ValueError:
                  pass
                break 
              await asyncio.sleep(5)
          asyncio.ensure_future(monitor())

          @channel.on("close")
          def on_close():
            print("Close Channel id: {}".format(channel.id))
            js = getattr(pc, 'js', None)
            if js is not None:
              jsdev = next((x for x in jslist if x.dev == js), None)
              if jsdev is not None:
                print("Freeing joystick:{}".format(jsdev.idx))
                jslist[jslist.index(jsdev)] = jsdev._replace(locked =  False)
              setattr(pc, 'js', None)

          @channel.on("message")
          async def on_message(message):
              #we use the 1 a second ping as heartbeat (and query)
              if isinstance(message, str) and message.startswith("ping"):
                try:
                  #if at the top of the queue and not assigned
                  if pcs.index(pc) < len(jslist):
                    if not hasattr(pc, 'js'):
                      # if they don't have a js, and one is available
                      jsdev = next((x for x in jslist if x.locked == False), None)
                      if jsdev is not None:
                        setattr(pc, 'js', jsdev.dev)
                        print("Assigning joystick:{}".format(jsdev.idx))
                        jslist[jslist.index(jsdev)] = jsdev._replace(locked = True)
                        #trigger to start a direct webrtc video feed (low latency)
                        if jsdev.idx == 1:
                          channel.send("start: Player{} (Green)".format(jsdev.idx))
                        elif jsdev.idx == 2:
                          channel.send("start: Player{} (Red)".format(jsdev.idx))
                        else:
                          channel.send("start: Player{}".format(jsdev.idx))
                    else:
                      # if they do have a joystick, and people are waiting
                      if (len(pcs) > len(jslist)):
                        #set future timestamp if not set
                        if not hasattr(pc, 'ts'):
                          #lets do 60 seconds plus a bit of hidden stopped time
                          setattr(pc, 'ts', int(time()) + 60 + 5)
                        remaining_time = pc.ts - int(time())
                        if remaining_time < 0:
                          channel.send("stop")
                          await asyncio.sleep(0.1)
                          channel.close()
                          for t in pc.getTransceivers():
                            await t.stop()
                          await pc.close()
                          js = getattr(pc, 'js', None)
                          if js is not None:
                            jsdev = next((x for x in jslist if x.dev == js), None)
                            if jsdev is not None:
                              print("Freeing joystick:{}".format(jsdev.idx))
                              jslist[jslist.index(jsdev)] = jsdev._replace(locked =  False)
                          try:
                            pcs.remove(pc)
                          except ValueError:
                            pass
                        else:
                          # 5 second hidden game over time
                          channel.send("Time: {}".format(max(0, remaining_time - 5)))
                      else:
                        channel.send("Time: --")
                  else:
                    #send their position in the waitlist
                    channel.send("Waitlist: {} of {}".format(
                      pcs.index(pc) + 1 - len(jslist), len(pcs) - len(jslist)))

                except ConnectionError:
                  pass
            
              elif isinstance(message, str) and message.startswith("controller: "):
                  #if in the last "hidden" 5 seconds of a turn, ignore buttons
                  if hasattr(pc, 'ts') and (pc.ts - int(time()) < 5):
                    return
                  vals = message[12:].split(',')
                  if getattr(pc, 'js', None) is not None:
                    jsupdate_vals(pc.js, vals)

              elif isinstance(message, str) and message.startswith("key"):
                  #if in the last "hidden" 5 seconds of a turn, ignore buttons
                  if hasattr(pc, 'ts') and (pc.ts - int(time()) < 5):
                    return
                  direction = message[3]
                  key = message[7]
                  dval = 1 if direction == "d" else 0
                  keys = ['z','x','u','l','d','r']
                  kpos = keys.index(key)
                  if getattr(pc, 'js', None) is not None:
                    pc.js.emit(events[kpos], int(dval))
                    pc.js.flush()
              elif isinstance(message, str) and message.startswith("gamectl: switch"):
                  #special game control just for pico-8 (for now)
                  gameidx = (gameidx + 1) % len(gamelist)
                  nextgame = gamelist[gameidx]
                  try: 
                    os.symlink('pico8/data_{}.pod'.format(nextgame), 'pico8/data_tmp.pod')
                    os.replace('pico8/data_tmp.pod', 'pico8/data.pod')
                  except FileExistsError:
                    pass
                  #sendkeys CTRL+R 'reload' (super ugly CTRL down, then R, then up, up)
                  #even uglier, need to send a couple of times to ensure it gets caught
                  for _ in  range(6):
                    self.send_sdl_event(0x400000e0, 0xe0, 1, kmod=kmod)
                    self.send_sdl_event(ord('r'), 0x15, 1, kmod=kmod)
                    self.send_sdl_event(0x400000e0, 0xe0, 0, kmod=kmod)
                    self.send_sdl_event(ord('r'), 0x15, 0, kmod=kmod)

      @pc.on("iceconnectionstatechange")
      async def on_iceconnectionstatechange():
          print("ICE connection state is %s" % pc.iceConnectionState)
          if pc.iceConnectionState == "failed":
            await pc.close()
            js = getattr(pc, 'js', None)
            if js is not None:
              jsdev = next((x for x in jslist if x.dev == js), None)
              if jsdev is not None:
                print("Freeing joystick:{}".format(jsdev.idx))
                jslist[jslist.index(jsdev)] = jsdev._replace(locked =  False)
            try:
              pcs.remove(pc)
            except ValueError:
              pass


    # handle offer
    await pc.setRemoteDescription(offer)

    for t in pc.getTransceivers():
        if t.kind == "video":
            pc.addTrack(VideoImageTrack())


    # send answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )

async def run(web, app, args, ssl_context):
    await asyncio.gather(
        web._run_app(app, host='0.0.0.0', port=args.port, ssl_context=ssl_context)
    )
  

async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    #proc.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC webcam demo")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument("--grab-window", help="Grab a currently running app window by WindowName provided.")
    parser.add_argument("--launch-sdl-app", 
        help="Launch the application command (opposite to --grab-window).")
    parser.add_argument("--window_size", type=str, default="128 128",
        help="Set sdl window size (w h) for launch-sdl-app.")
    parser.add_argument("--enable-gpio-buttons", action="store_true", 
        help="Use gpio pins for keys.")
    parser.add_argument("--enable-virtual-keyboard", action="store_true", 
        help="Use sdl event injector for virtual keys. (requires --launch-sdl-app)")
    parser.add_argument("--enable-waitlist", type=int, default=4,
        help="Enable Waitlist and queue size (default: 4 for joysticks, 2 for keyboard)")
    parser.add_argument("--number-of-players", type=int, default=4,
        help="How many controllers to allocate (default: 4 for joysticks, 2 for keyboard)")
    parser.add_argument("--port", type=int, default=8080, 
        help="Port for HTTP server (default: 8080)")
    parser.add_argument("--disable-port-forwarding", action="store_true",
        help="Disable UPNP Port forwarding for external access to host")
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None
    
    pcs_max_size = args.enable_waitlist

    #some games prefer joysticks setup before launching
    if args.enable_virtual_keyboard:
      jslist.append(JSDev(1, False, 1))
    elif args.enable_gpio_buttons:
      jslist.append(JSDev("gpio_js1", False, 1))
      jslist.append(JSDev("gpio_js2", False, 2))
    else:
      #using yoke uinput based virtual joysticks
      #don't use numbers in Yoke name
      for idx in range(0, args.number_of_players):
        jslist.append(JSDev(yoke.Device(idx + 1, 'Yoke', events), False, idx + 1))
        sleep(0.1) #need some delay, otherwise not in correct order
      #send non-pressed buttons for all virtual joystics
      for jsdev in jslist:
        for event in events:
          jsdev.dev.emit(event, 0)
        jsdev.dev.flush()
      print("Make sure to export this controller for SDL based games")
      print("export SDL_GAMECONTROLLERCONFIG='06000000596f6b650000000000000000,Yoke,platform:Linux,a:b0,b:b1,dpup:b2,dpdown:b3,dpleft:b4,dpright:b5,'")

    if args.grab_window:
      image_depth = 4
      window = GrabWindow(args.grab_window)
      win_x, win_y, win_w, win_h = window.get_window_pos()
      print("Window width: {} height: {}".format(win_w, win_h))
      shared_image_array = RawArray('B', win_w * win_h * image_depth)
      process = Process(target=process_capture_images, 
          args=(shared_image_array, (win_x, win_y), (win_w, win_h)))
      process.start()
    else:
      image_depth = 3
      win_x, win_y, win_w, win_h = (0, 0, 
          int(args.window_size.split(" ")[0]), 
          int(args.window_size.split(" ")[1]))
      #using raw as we don't need to lock the data (pixels may flicker)
      shared_image_array = RawArray('B', win_w * win_h * image_depth)
      os.environ["SDL_VIDEODRIVER"]= "dummy"
      os.environ["SDL_VIDEO_DUMMY_SAVE_FRAMES"] = "1"
      os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
      #need to configure our joystick if using our own pico-8 config
      os.environ["SDL_GAMECONTROLLERCONFIG"] = "06000000596f6b650000000000000000,Yoke,platform:Linux,a:b0,b:b1,dpup:b2,dpdown:b3,dpleft:b4,dpright:b5,"

      #enable sdl wrapper for sdlkbdsim and other sdl tweaks
      #sdlwrap_lib = 'sdlwrap_{}_{}.so'.format(os.uname().sysname, os.uname().machine)
      #os.environ["LD_PRELOAD"] = str(PROJECT_ROOT / "pico8" / sdlwrap_lib)
      os.environ["REMOTEKB_PORT"] = "4321"
      #only necessary for arm due to pico-8 forcing non-windowed
      if os.uname().machine == 'armv7l':
        os.environ["LD_LIBRARY_PATH"] = str(PROJECT_ROOT / "pico8")
        os.environ["REMOTEKB_LIBSDL_PATH"] = "/usr/lib/arm-linux-gnueabihf/libSDL2.so"

      #move into /tmp/sdl directory to have sdl image dumps there
      cwd = os.getcwd()
      if not os.path.isdir("/tmp/sdl"):
        os.mkdir("/tmp/sdl")
      os.chdir("/tmp/sdl")


      #requires remotekb_wrap in launch for sdlkbdsim use
      pico8_binary = 'runner_{}_{}'.format(os.uname().sysname, os.uname().machine)
      print(str(PROJECT_ROOT / "pico8" / pico8_binary))
      proc = EasyProcess(
        str(PROJECT_ROOT / "pico8" / pico8_binary) +
        " -windowed 1" +
        " -width 128" +
        " -height 128" +
        " -frameless 1" +
        " -volume 0" +
        " -foreground_sleep_ms 20" +
        " -home /tmp")
      proc.start()

      os.chdir(cwd)

      process = Process(target=process_dumped_images, args=(shared_image_array,))
      process.start()


    if not args.disable_port_forwarding:
      upnp = UPNPPortForward()
      upnp.forward_port(8080, 'TCP')
      upnp.forward_port(8080, 'UDP')
      print("Share URL for remote play: http://{}:8080".format(upnp.get_external_ip()))

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.add_routes([web.static('/', PROJECT_ROOT / 'public_html')])
    app.add_routes([web.static('/img', PROJECT_ROOT / 'public_html/img')])
    app.router.add_post("/offer", offer)

    #web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
    # (For Python < 3.7, below is equivalent to asyncio.run(run())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        run(web, app, args, ssl_context)
    )

