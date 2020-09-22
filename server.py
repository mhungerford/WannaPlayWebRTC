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

import cv2
from av import VideoFrame

ROOT = os.path.dirname(__file__)


pcs = set()


class VideoImageTrack(VideoStreamTrack):
    """
    A video stream track that returns a rotating image.
    """

    kind = "video"

    def __init__(self):
        super().__init__()  # don't forget this!
        self.idx = 0

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        # rotate image
        PHOTO_PATH = os.path.join(ROOT, "pics/sonic-{:03d}.png".format(self.idx))
        img = cv2.imread(PHOTO_PATH, cv2.IMREAD_COLOR)
        self.idx = (self.idx + 1) % 200

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
