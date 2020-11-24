#detect platform (Windows, Mac or Linux) and do correct window grab
#eventually clean this up beyond "grab, focus and get pos+size" all in one
import sys
import traceback
from sys import platform
    
if platform == "linux":
  try:
    import Xlib.display
    from Xlib import X, Xatom
  except:
    pass
else: #windows and MAC
  try:
    import pygetwindow as getwindow
  except:
    pass

class GrabWindow():
  def __init__(self, window_name):
    self.window_name = window_name
    self.win_x, self.win_y, self.win_w, self.win_h = self._get_window_pos(self.window_name)

  def get_window_pos(self):
    return (self.win_x, self.win_y, self.win_w, self.win_h)

  def _get_window_pos(self, window_name):
    print("Looking for window: {}".format(window_name))
    if platform == "linux":
      x, y, w, h = (0,0,128,128)
      try:
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
            prop = window.get_full_property(Xatom.WM_NAME, 0)
            #prop = window.get_full_property(disp.intern_atom('_NET_WM_NAME'), 0)
            wm_name = getattr(prop, 'value', '').decode('utf-8', errors='ignore')
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
      gamewindow = getwindow(window_name)[0]
      x = gamewindow.top
      y = gamewindow.left
      w, h = gamewindow.size
      return (x, y, w, h)


