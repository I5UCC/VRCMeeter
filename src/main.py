import voicemeeter
import json
import os
import sys
import time
import traceback
import ctypes
import zeroconf
from pythonosc import dispatcher, osc_server, udp_client
from tinyoscquery.queryservice import OSCQueryService
from tinyoscquery.utility import get_open_tcp_port, get_open_udp_port, check_if_tcp_port_open, check_if_udp_port_open
from tinyoscquery.query import OSCQueryBrowser, OSCQueryClient
from psutil import process_iter
from threading import Thread, Timer


class RepeatedTimer(object):
	def __init__(self, interval: float, function, *args, **kwargs):
		self._timer: Timer = None
		self.interval = interval
		self.function = function
		self.args = args
		self.kwargs = kwargs
		self.is_running: bool = False
		self.start()

	def _run(self):
		self.is_running = False
		self.start()
		self.function(*self.args, **self.kwargs)

	def start(self):
		if not self.is_running:
			self._timer = Timer(self.interval, self._run)
			self._timer.start()
			self.is_running = True

	def stop(self):
		self._timer.cancel()
		self.is_running = False


def get_absolute_path(relative_path, script_path=__file__) -> str:
    """Gets absolute path from relative path"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(script_path)))
    return os.path.join(base_path, relative_path)


def get_float_from_voicemeeter_gain(g):
    """Maps a gain value between min_gain and max_gain to a float from 0.0 to 1.0."""
    return (g - MIN_GAIN) / (MAX_GAIN - MIN_GAIN)


def get_voicemeeter_gain_from_float(f):
    """Maps a float from 0.0 to 1.0 to a gain value between min_gain and max_gain."""
    return f * (MAX_GAIN - MIN_GAIN) + MIN_GAIN


def is_vrchat_running() -> bool:
    """Checks if VRChat is running."""
    _proc_name = "VRChat.exe" if os.name == 'nt' else "VRChat"
    return _proc_name in (p.name() for p in process_iter())


def wait_get_oscquery_client():
    service_info = None
    print("Waiting for VRChat to be discovered.")
    while service_info is None:
        browser = OSCQueryBrowser()
        time.sleep(2) # Wait for discovery
        service_info = browser.find_service_by_name("VRChat")
    print("VRChat discovered!")
    client = OSCQueryClient(service_info)
    print("Waiting for VRChat to be ready.")
    while client.query_node(AVATAR_CHANGE_PARAMETER) is None:
        time.sleep(2)
    print("VRChat ready!")
    return client


def set_gain_variable(addr, value):
    global gains_in, changed
    strip = int(addr.split('_')[-1])
    gain = get_voicemeeter_gain_from_float(float(value))
    gains_in[strip] = round(gain, 1)
    changed = True


def set_gains():
    global changed
    global vmr, gains_in

    if not changed:
        return

    for strip in STRIPS_IN:
        if round(vmr.inputs[strip].gain, 1) == gains_in[strip]:
            continue
        print(f"Setting gain for strip {strip} to {gains_in[strip]}")
        vmr.inputs[strip].gain = gains_in[strip]
    for strip in STRIPS_OUT:
        if round(vmr.outputs[strip].gain, 1) == gains_out[strip]:
            continue
        print(f"Setting gain for strip {strip} to {gains_out[strip]}")
        vmr.outputs[strip].gain = gains_out[strip]
    changed = False


def avatar_change(addr, value):
    global vmr

    print("Avatar changed/reset...")

    for strip in STRIPS_IN:
        osc_client.send_message(f"{PARAMETER_PREFIX_IN}{strip}", get_float_from_voicemeeter_gain(vmr.inputs[strip].gain))
    for strip in STRIPS_OUT:
        osc_client.send_message(f"{PARAMETER_PREFIX_OUT}{strip}", get_float_from_voicemeeter_gain(vmr.outputs[strip].gain))


def osc_server_serve():
    print(f"Starting OSC client on {OSC_SERVER_IP}:{OSC_SERVER_PORT}:{HTTP_PORT}\n")
    server.serve_forever(2)


def main():
    global osc_client, vmr, server, server_thread, qclient, oscqs, update_timer, gains_in
    vmr = voicemeeter.remote(KIND)
    vmr.login()

    for strip in STRIPS_IN:
        gains_in[strip] = round(vmr.inputs[strip].gain, 1)
        print(f"Strip {strip} gain: {gains_in[strip]}")
    for strip in STRIPS_OUT:
        gains_out[strip] = round(vmr.outputs[strip].gain, 1)
        print(f"Strip {strip} gain: {gains_out[strip]}")

    osc_client = udp_client.SimpleUDPClient(OSC_SERVER_IP, OSC_CLIENT_PORT)

    disp = dispatcher.Dispatcher()
    disp.map(AVATAR_CHANGE_PARAMETER, avatar_change)
    for strip in STRIPS_IN:
        disp.map(f"{PARAMETER_PREFIX_IN}{strip}", set_gain_variable)
        print(f"Bound to {PARAMETER_PREFIX_IN}{strip}")
    for strip in STRIPS_OUT:
        disp.map(f"{PARAMETER_PREFIX_OUT}{strip}", set_gain_variable)
        print(f"Bound to {PARAMETER_PREFIX_OUT}{strip}")

    server = osc_server.ThreadingOSCUDPServer((OSC_SERVER_IP, OSC_SERVER_PORT), disp)
    server_thread = Thread(target=osc_server_serve, daemon=True)
    server_thread.start()

    print("Waiting for VRChat to start.")
    while not is_vrchat_running():
        time.sleep(3)
    print("VRChat started!")
    qclient = wait_get_oscquery_client()
    oscqs = OSCQueryService("VoicemeeterControl", HTTP_PORT, OSC_SERVER_PORT)
    oscqs.advertise_endpoint(AVATAR_CHANGE_PARAMETER, access="readwrite")
    for strip in STRIPS_IN:
        oscqs.advertise_endpoint(f"{PARAMETER_PREFIX_IN}{strip}", access="readwrite")
    for strip in STRIPS_OUT:
        oscqs.advertise_endpoint(f"{PARAMETER_PREFIX_OUT}{strip}", access="readwrite")

    avatar_change(None, None)

    update_timer = RepeatedTimer(0.3, set_gains)
    update_timer.start()
    
    while is_vrchat_running():
        time.sleep(3)

    print("VRChat closed, exiting.")
    exit()


def exit():
    print("Exiting...")
    if vmr:
        vmr.logout()
    if update_timer:
        update_timer.stop()
    if oscqs:
        oscqs.stop()
    sys.exit(0)

conf = json.load(open(get_absolute_path('config.json')))
changed = False
gains_in = {}
gains_out = {}
osc_client: udp_client.SimpleUDPClient = None
vmr: voicemeeter.remote = None
server: osc_server.ThreadingOSCUDPServer = None
server_thread: Thread = None
qclient: OSCQueryClient = None
oscqs: OSCQueryService = None
update_timer: RepeatedTimer = None

KIND = conf['voicemeeter_type']
STRIPS_IN = conf['strips_in']
STRIPS_OUT = conf['strips_out']
OSC_CLIENT_PORT = conf["port"]
OSC_SERVER_PORT = conf['server_port']
OSC_SERVER_IP = conf['ip']
HTTP_PORT = conf['http_port']
MIN_GAIN = conf['min_gain']
MAX_GAIN = conf['max_gain']
AVATAR_CHANGE_PARAMETER = "/avatar/change"
PARAMETER_PREFIX_IN = "/avatar/parameters/vm_in_gain_"
PARAMETER_PREFIX_OUT = "/avatar/parameters/vm_out_gain_"

if len(STRIPS_IN) == 0:
    match KIND:
        case "basic":
            STRIPS_IN = [0, 1, 2]
        case "banana":
            STRIPS_IN = [0, 1, 2, 3, 4]
        case "potato":
            STRIPS_IN = [0, 1, 2, 3, 4, 5, 6, 7]

if len(STRIPS_IN) == 1 and STRIPS_IN[0] == -1:
    STRIPS_IN = {}

if len(STRIPS_OUT) == 0:
     match KIND:
        case "basic":
            STRIPS_OUT = [0, 1]
        case "banana":
            STRIPS_OUT = [0, 1, 2, 3, 4]
        case "potato":
            STRIPS_OUT = [0, 1, 2, 3, 4, 5, 6, 7]

if len(STRIPS_OUT) == 1 and STRIPS_OUT[0] == -1:
    STRIPS_OUT = {}

if OSC_SERVER_PORT != 9001:
    print("OSC Server port is not default, testing port availability and advertising OSCQuery endpoints")
    if OSC_SERVER_PORT <= 0 or not check_if_udp_port_open(OSC_SERVER_PORT):
        OSC_SERVER_PORT = get_open_udp_port()
    if HTTP_PORT <= 0 or not check_if_tcp_port_open(HTTP_PORT):
        HTTP_PORT = OSC_SERVER_PORT if check_if_tcp_port_open(OSC_SERVER_PORT) else get_open_tcp_port()
else:
    print("OSC Server port is default.")

try:
    main()
except OSError as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, "You can only bind to the port 9001 once.", "VRCVoiceMeeterControl - Error", 0)
    exit()
except zeroconf._exceptions.NonUniqueNameException as e:
    print("NonUniqueNameException, trying again...")
    os.execv(sys.executable, ['python'] + sys.argv)
except KeyboardInterrupt:
    exit()
except Exception as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, traceback.format_exc(), "VRCVoiceMeeterControl - Unexpected Error", 0)
    print(traceback.format_exc())
    exit()
