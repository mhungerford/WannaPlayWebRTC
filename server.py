import argparse
import asyncio
import json
import logging
import os
import platform
import ssl
import sys, traceback
from sys import platform

from aiohttp import web

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer

import numpy as np
import cv2
from av import VideoFrame

from mss import mss #fast screen-shots
from mss import tools as msstools

#local dependencies
import yoke

#Note: Don't forget to sdl_controller map these
#yoke.EVENTS.BTN_START, 
events = [
    yoke.EVENTS.BTN_EAST,
    yoke.EVENTS.BTN_NORTH,
    yoke.EVENTS.BTN_DPAD_UP,
    yoke.EVENTS.BTN_DPAD_LEFT,
    yoke.EVENTS.BTN_DPAD_DOWN,
    yoke.EVENTS.BTN_DPAD_RIGHT
    ]
#don't use numbers in Yoke name
js1 = yoke.Device(1, 'Yoke', events)

def jsupdate_vals(vals):
  for e in range(0, len(vals)):
    js1.emit(events[e], int(vals[e]))
  js1.flush()

def get_window_pos(window_name):
  print("Looking for window: {}".format(window_name))
  if platform == "linux":
    x, y, w, h = (0,0,128,128)
    try:
      import Xlib.display
      disp = Xlib.display.Display()
      root = disp.screen().root

      def sendEvent(window, ctype, data, mask=None):
        """ Send a ClientMessage event to the root """
        if not window: window = self.root
        if type(data) is str:
          dataSize = 8
        else:
          data = (data+[0]*(5-len(data)))[:5]
          dataSize = 32
        ev = Xlib.protocol.event.ClientMessage(window=window, client_type=ctype, data=(dataSize,(data)))
        if not mask:
          mask = (Xlib.X.SubstructureRedirectMask|Xlib.X.SubstructureNotifyMask)
        root.send_event(ev, event_mask=mask)

      def raiseWindow(window, window_id):
        #newer focus command to root window
        sendEvent(window, disp.intern_atom('_NET_ACTIVE_WINDOW'), [window_id]) 

      def findWindow(window_name):
        window_ids = root.get_full_property(disp.intern_atom('_NET_CLIENT_LIST'), Xlib.X.AnyPropertyType).value
        for window_id in window_ids:
          window = disp.create_resource_object('window', window_id)
          #cannot use get_wm_name, as it errors on certain windows (firefox)
          prop = window.get_full_property(disp.intern_atom('_NET_WM_NAME'), 0)
          wm_name = getattr(prop, 'value', '')
          if wm_name == window_name:
            return (window, window_id)

      def getWindowGeometry(window):
        geometry = window.get_geometry()
        abs_coords = root.translate_coords(window, 0, 0)
        return (abs_coords.x, abs_coords.y, geometry.width, geometry.height)

      (window, window_id) = findWindow(window_name)
      if window != None:
        print("Found window: {}".format(window_id))
        raiseWindow(window, window_id)
        (x, y, w, h) = getWindowGeometry(window)
        print("Window geometry +{}+{},{}x{}".format(x,y,w,h))
      else:
        print("Error: Window {} not found".format(window_name))
    except:
      print("XLIB error {}".format(sys.exc_info()[0]))
      print("XLIB line: {}".format(sys.exc_info()[2].tb_lineno))
      print(traceback.format_exc())
    return (x, y, w, h)
  else:
    import pygetwindow as getwindow
    gamewindow = getwindow(window_name)[0]
    x = gamewindow.top
    y = gamewindow.left
    w, h = gamewindow.size
    return (x, y, w, h)



ROOT = os.path.dirname(__file__)
#PHOTO_PATH = os.path.join("/tmp/", "screenshot.png")


pcs = []
sct = mss()
sct.compression_level = 0 # disable screenshot compression (for performance)

raw_image = None

win_x, win_y, win_w, win_h = get_window_pos('PICO-8')

def capture_screenshot():
  # The screen part to capture
  monitor = {"top": win_y, "left": win_x, "width": win_w, "height": win_h}
  # Grab the data
  sct_img = sct.grab(monitor)
  # Save to the picture file
  #msstools.to_png(sct_img.rgb, sct_img.size, output="/tmp/screenshot.png")  
  global raw_image #use global so we can reuse frames from process thread
  raw_image = np.array(sct_img)


class VideoImageTrack(VideoStreamTrack):
    """
    A video stream track that returns a rotating image.
    """

    kind = "video"

    def __init__(self):
        super().__init__()  # don't forget this!

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        # rotate image
        capture_screenshot()
        #img = cv2.imread("/tmp/screenshot.png", cv2.IMREAD_COLOR)

        # create video frame
        #frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame = VideoFrame.from_ndarray(raw_image, format="bgra")
        frame.pts = pts
        frame.time_base = time_base
        
        return frame



async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def javascript(request):
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)

async def basecss(request):
    content = open(os.path.join(ROOT, "base.css"), "r").read()
    return web.Response(content_type="application/javascript", text=content)

async def basejs(request):
    content = open(os.path.join(ROOT, "base.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)

async def dpadcss(request):
    content = open(os.path.join(ROOT, "dpad.css"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.append(pc)

    @pc.on("datachannel")
    def on_datachannel(channel):
        @channel.on("message")
        def on_message(message):
            if isinstance(message, str) and message.startswith("ping"):
                channel.send("pong" + message[4:])
                print("Channel id: {}".format(channel.id))
                print(message)
            elif isinstance(message, str) and message.startswith("controller: "):
                vals = message[12:].split(',')
                jsupdate_vals(vals)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print("ICE connection state is %s" % pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()
            pcs.remove(pc)

    await pc.setRemoteDescription(offer)
    for t in pc.getTransceivers():
        if t.kind == "video":
            pc.addTrack(VideoImageTrack())

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC webcam demo")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument("--play-from", help="Read the media from a file and sent it."),
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default: 8080)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    app.router.add_get("/base.js", basejs)
    app.router.add_get("/base.css", basecss)
    app.router.add_get("/dpad.css", dpadcss)
    app.add_routes([web.static('/img','img')])
    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
