import os
import struct
import socket
from time import time, sleep
from multiprocessing import Process, Array, RawArray

#may need to set libSDL2 path if not in normal paths
#os.environ["REMOTEKB_LIBSDL_PATH"] = "/usr/lib/x86_64-linux-gnu/libSDL2-2.0.so.0"

class SdlKbdSim():
  def __init__(self):
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.keylist = [
      (0x7a, 0x1d),# z key
      (0x78, 0x1b),# x key
      (0x40000052, 0x52),# up key
      (0x40000050, 0x50),# left key
      (0x40000051, 0x51),# down key
      (0x4000004f, 0x4f)# right key
      ]
    #using raw as we don't need to lock the data (pixels may flicker)
    self.shared_keyboard_array = RawArray('i', 6)
    self.keyboard_update_process = Process(
        target=self.process_keyboard_updates, args=(self.shared_keyboard_array,))
    self.keyboard_update_process.start()

  def wrap_sdlexec_cmd(sdlexec_cmd):
    sdlwraper = os.path.join(os.path.dirname(os.path.abspath(__file__)) + "tsi/remotekb_wrap")
    return sdlwrapper + "-p 4321 {}".format(sdlexec_cmd)


  def setkey(self, idx, pressed):
    self.send_sdl_event(self.keylist[idx][0], self.keylist[idx][1], pressed)
    self.shared_keyboard_array[idx] = pressed

  # b=int8, i=int32, I=uint32, 
  # type, ts, wid, state, repeat, padding, scancode, sym, mod, padding
  #look to repeat every 30 ms
  def send_sdl_event(self, key, code, state, repeat=0):
    etype = 0x0300 if state else 0x0301
    sdlevent = struct.pack("iiibbhiihhi6i",
      etype, #0x0300, #type 0x0300 keydown, 0x0301 keyup
      0,0, #ts, wid
      state, #(1=down)
      repeat, #(1=repeating)
      0, #short padding
      code, #scancode
      key, #sym
      0, #short mod (ie. ctrl+alt)
      0, #short mod padding (missing from header)
      0, #key padding
      0,0,0,0,0,0) #24 bytes padding
    self.sock.sendto(sdlevent,('127.0.0.1', 4321))

  def process_keyboard_updates(self, shared_keyboard_array):
    last_time = time()
    while True:
      #handle keypress repeat for all keys still pressed
      for idx, status in enumerate(shared_keyboard_array):
        if status == 1:
          self.send_sdl_event(self.keylist[idx][0], self.keylist[idx][1], 1, 1)
      curr_time = time()
      sleep(max(0, 0.030 - (curr_time - last_time))) # 30 ms key repeat rate
      last_time = curr_time

