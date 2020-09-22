import argparse
import asyncio
import json
import logging
import os
import platform
import ssl

from aiohttp import web

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer

import numpy as np
import cv2
from av import VideoFrame

from mss import mss #fast screen-shots
from mss import tools as msstools

from sys import platform

win_x = 0
win_y = 0
win_w = 0
win_h = 0

if platform == "linux":
  try:
    import Xlib.display
    disp = Xlib.display.Display()
    root = disp.screen().root
    #some windows are nested, like SDL games
    #so use recursion to find all windows
    def findWindow(win, name):
      if win.get_wm_name() == name:
        return win
      children = win.query_tree().children
      for awin in children:
        thewin = findWindow(awin, name)
        if thewin != None:
          return thewin

    mywin = findWindow(root, 'PICO-8')
    if mywin != None:
      print("Found: " + mywin.get_wm_name())
      geometry = mywin.get_geometry()
      abs_coords = root.translate_coords(mywin, 0, 0)
      win_x = abs_coords.x
      win_y = abs_coords.y
      win_w = geometry.width
      win_h = geometry.height
      print("geometry {},{} {}x{}".format(x,y,w,h))
  except:
    pass
else:
  import pygetwindow as getwindow
  gamewindow = getwindow('pico8')[0]
  win_x = gamewindow.top
  win_y = gamewindow.left
  win_w, win_h = gamewindow.size



ROOT = os.path.dirname(__file__)
#PHOTO_PATH = os.path.join("/tmp/", "screenshot.png")


pcs = set()
sct = mss()
sct.compression_level = 0 # disable screenshot compression (for performance)

raw_image = []

def capture_screenshot():
  # The screen part to capture
  monitor = {"top": win_y, "left": win_x, "width": win_w, "height": win_h}
  # Grab the data
  sct_img = sct.grab(monitor)
  # Save to the picture file
  msstools.to_png(sct_img.rgb, sct_img.size, output="/tmp/screenshot.png")  
  #raw_image = np.array(sct_img)


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
        #img = raw_image
        img = cv2.imread("/tmp/screenshot.png", cv2.IMREAD_COLOR)

        # create video frame
        frame = VideoFrame.from_ndarray(img, format="bgr24")
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
    pcs.add(pc)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print("ICE connection state is %s" % pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()
            pcs.discard(pc)

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
