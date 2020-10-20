from platform import system

from . import yoke_events as EVENTS

ALIAS_TO_EVENT = {
    'j1':  'ABS_X,ABS_Y',
    'j2':  'ABS_RX,ABS_RY',
    'j3':  'ABS_MISC,ABS_MAX',
    's1':  'ABS_X,ABS_Y',
    's2':  'ABS_RX,ABS_RY',
    's3':  'ABS_TOOL_WIDTH,ABS_MAX',
    'mx':  'ABS_MISC',
    'my':  'ABS_RZ',
    'mz':  'ABS_Z',
    'ma':  'ABS_TILT_X',
    'mb':  'ABS_WHEEL',
    'mg':  'ABS_TILT_Y',
    'pa':  'ABS_GAS',
    'pb':  'ABS_BRAKE',
    'pt':  'ABS_THROTTLE',
    'k1':  'ABS_VOLUME',
    'k2':  'ABS_RUDDER',
    'k3':  'ABS_PRESSURE',
    'k4':  'ABS_DISTANCE',
    'a1':  'ABS_HAT0X',
    'a2':  'ABS_HAT0Y',
    'a3':  'ABS_HAT1X',
    'a4':  'ABS_HAT1Y',
    'a5':  'ABS_HAT2X',
    'a6':  'ABS_HAT2Y',
    'a7':  'ABS_HAT3X',
    'a8':  'ABS_HAT3Y',
    'bs':  'BTN_START',
    'bg':  'BTN_SELECT',
    'bm':  'BTN_MODE',
    'b1':  'BTN_GAMEPAD',
    'b2':  'BTN_EAST',
    'b3':  'BTN_WEST',
    'b4':  'BTN_NORTH',
    'b5':  'BTN_TL',
    'b6':  'BTN_TR',
    'b7':  'BTN_TL2',
    'b8':  'BTN_TR2',
    'b9':  'BTN_A',
    'b10': 'BTN_B',
    'b11': 'BTN_C',
    'b12': 'BTN_X',
    'b13': 'BTN_Y',
    'b14': 'BTN_Z',
    'b15': 'BTN_TOP',
    'b16': 'BTN_TOP2',
    'b17': 'BTN_PINKIE',
    'b18': 'BTN_BASE',
    'b19': 'BTN_BASE2',
    'b20': 'BTN_BASE3',
    'b21': 'BTN_BASE4',
    'b22': 'BTN_BASE5',
    'b23': 'BTN_BASE6',
    'b24': 'BTN_THUMB',
    'b25': 'BTN_THUMB2',
    'b26': 'BTN_TRIGGER',
    'dp':  'BTN_DPAD_UP,BTN_DPAD_LEFT,BTN_DPAD_DOWN,BTN_DPAD_RIGHT',
}

from glob import glob


ABS_EVENTS = [getattr(EVENTS, n) for n in dir(EVENTS) if n.startswith('ABS_')]

class Device:
    def __init__(self, id=1, name='Yoke', events=(), bytestring=b'!impossible?aliases#string$'):
        self.name = name + '-' + str(id)
        #for fn in glob('/sys/class/input/js*/device/name'):
        #    with open(fn) as f:
        #        fname = f.read().split()[0]  # need to split because there seem to be newlines
        #        if name == fname:
        #            print('Device name "{}" already taken. Set another name with --name NAME'.format(name))
        #            raise AttributeError('Device name "{}" already taken. Set another name with --name NAME'.format(name))

        # set range (0, 255) for abs events
        self.events = events
        self.bytestring = bytestring
        events = [e + (0, 255, 0, 0) if e in ABS_EVENTS else e for e in events]
        print("about it init joystick: " + self.name)

        BUS_VIRTUAL = 0x06
        try:
            import uinput
            self.device = uinput.Device(events, name, BUS_VIRTUAL)
            print("Started joystick: " + self.name)
        except Exception as e:
            print("Failed to initialize device via uinput.")
            print("Hint: try loading kernel driver with `sudo modprobe uinput`.")
            print("Hint: make sure you've run `yoke-enable-uinput` to configure permissions.")
            print("")
            print("More info: {}".format(e.args))
            raise

    def emit(self, d, v):
        if d not in self.events:
            print('Event {d} has not been registered… yet?')
        self.device.emit(d, int(v), False)

    def flush(self):
        self.device.syn()

    def close(self):
        self.device.destroy()


# Override on Windows
if system() is 'Windows':
    print('Warning: This is not well tested on Windows!')

    from yoke.vjoy.vjoydevice import VjoyDevice

    class Device:
        def __init__(self, id=1, name='Yoke', events=(), bytestring=b'!impossible?aliases#string$'):
            super().__init__()
            self.name = name + '-' + str(id)
            self.device = VjoyDevice(id)
            self.lib = self.device.lib
            self.id = self.device.id
            self.struct = self.device.struct
            self.events = []
            self.bytestring = bytestring
            #a vJoy controller has up to 8 axis with fixed names, and 128 buttons with no names.
            #TODO: Improve mapping between uinput events and vJoy controls.
            axes = 0
            buttons = 0
            for event in events:
                if event[0] == 0x01: # button/key
                    self.events.append((event[0], buttons)); buttons += 1
                elif event[0] == 0x03: # analog axis
                    self.events.append((event[0], axes)); axes += 1
            self.axes = [0,] * 15
            self.buttons = 0
        def emit(self, d, v):
            if d is not None:
                if d[0] == 0x03: #analog axis
                    # To map from [0, 255] to [0x1, 0x8000], take the bitstring abcdefgh,
                    # parse the bitstring abcdefghabcdefg, and then sum 1.
                    self.axes[d[1]] = ((v << 7) | (v >> 1)) + 1
                else:
                    self.buttons |= (v << d[1])
        def flush(self):
            # Struct JOYSTICK_POSITION_V2's definition can be found at
            # https://github.com/shauleiz/vJoy/blob/2c9a6f14967083d29f5a294b8f5ac65d3d42ac87/SDK/inc/public.h#L203
            # It's basically:
            # 1 BYTE for device ID
            # 3 unused LONGs
            # 8 LONGs for axes
            # 7 unused LONGs
            # 1 LONGs for buttons
            # 4 DWORDs for hats
            # 3 LONGs for buttons
            self.lib.UpdateVJD(self.id, self.struct.pack(
                self.id, # 1 BYTE for device ID
                0, 0, 0, # 3 unused LONGs
                *self.axes, # 8 LONGs for axes and 7 unused LONGs
                self.buttons & 0xffffffff, # 1 LONG for buttons
                0, 0, 0, 0, # 4 DWORDs for hats
                (self.buttons >> 32) & 0xffffffff,
                (self.buttons >> 64) & 0xffffffff,
                (self.buttons >> 96) & 0xffffffff # 3 LONGs for buttons
            ))

            # This allows a very simple emit() definition:
            self.buttons = 0
        def close(self):
            self.device.close()

