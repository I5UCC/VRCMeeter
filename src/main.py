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
import logging
import openvr


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
    logging.info("Waiting for VRChat to be discovered.")
    while service_info is None:
        browser = OSCQueryBrowser()
        time.sleep(2) # Wait for discovery
        service_info = browser.find_service_by_name("VRChat")
    logging.info("VRChat discovered!")
    client = OSCQueryClient(service_info)
    logging.info("Waiting for VRChat to be ready.")
    while client.query_node(AVATAR_CHANGE_PARAMETER) is None:
        time.sleep(2)
    logging.info("VRChat ready!")
    return client


def set_gain_variable_in(addr, value):
    global gains_in, changed
    strip = int(addr.split('_')[-1])
    gain = get_voicemeeter_gain_from_float(float(value))
    gains_in[strip] = round(gain, 1)
    changed = True


def set_gain_variable_out(addr, value):
    global gains_out, changed
    strip = int(addr.split('_')[-1])
    gain = get_voicemeeter_gain_from_float(float(value))
    gains_out[strip] = round(gain, 1)
    changed = True


def set_gains():
    global changed
    global vmr, gains_in

    if not changed:
        return

    for strip in STRIPS_IN:
        if round(vmr.inputs[strip].gain, 1) == gains_in[strip]:
            continue
        logging.info(f"Setting gain for strip {strip} to {gains_in[strip]}")
        vmr.inputs[strip].gain = gains_in[strip]
    for strip in STRIPS_OUT:
        if round(vmr.outputs[strip].gain, 1) == gains_out[strip]:
            continue
        logging.info(f"Setting gain for strip {strip} to {gains_out[strip]}")
        vmr.outputs[strip].gain = gains_out[strip]
    changed = False


def set_profile(addr, value):
    global vmr
    if type(addr) is int:
        logging.info(f"Setting profile to {PROFILES[addr]}")
        vmr.load(get_absolute_path(PROFILES[addr]))
    else:
        logging.info(f"Setting profile to {addr}")
        vmr.load(get_absolute_path(addr))
    time.sleep(1)
    avatar_change(None, None)


def avatar_change(addr, value):
    global vmr

    logging.info("Avatar changed/reset...")

    for strip in STRIPS_IN:
        osc_client.send_message(f"{PARAMETER_PREFIX_IN}gain_{strip}", get_float_from_voicemeeter_gain(vmr.inputs[strip].gain))
    for strip in STRIPS_OUT:
        osc_client.send_message(f"{PARAMETER_PREFIX_OUT}gain_{strip}", get_float_from_voicemeeter_gain(vmr.outputs[strip].gain))


def osc_server_serve():
    logging.info(f"Starting OSC client on {OSC_SERVER_IP}:{OSC_SERVER_PORT}:{HTTP_PORT}")
    server.serve_forever(2)


def exit():
    logging.info("Exiting...")
    if vmr:
        vmr.logout()
    if update_timer:
        update_timer.stop()
    if oscqs:
        oscqs.stop()
    sys.exit(0)


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S', handlers=[logging.StreamHandler()])

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
PROFILES = conf['profiles']
OSC_CLIENT_PORT = conf["port"]
OSC_SERVER_PORT = conf['server_port']
OSC_SERVER_IP = conf['ip']
HTTP_PORT = conf['http_port']
MIN_GAIN = conf['min_gain']
MAX_GAIN = conf['max_gain']
AVATAR_CHANGE_PARAMETER = "/avatar/change"
PARAMETER_RESTART = "/avatar/parameters/vm_restart"
PARAMETER_PREFIX_IN = "/avatar/parameters/vm_in_"
PARAMETER_PREFIX_OUT = "/avatar/parameters/vm_out_"
PARAMETER_PREFIX_PROFILE = "/avatar/parameters/vm_profile_"

if OSC_SERVER_PORT != 9001:
    logging.info("OSC Server port is not default, testing port availability and advertising OSCQuery endpoints")
    if OSC_SERVER_PORT <= 0 or not check_if_udp_port_open(OSC_SERVER_PORT):
        OSC_SERVER_PORT = get_open_udp_port()
    if HTTP_PORT <= 0 or not check_if_tcp_port_open(HTTP_PORT):
        HTTP_PORT = OSC_SERVER_PORT if check_if_tcp_port_open(OSC_SERVER_PORT) else get_open_tcp_port()
else:
    logging.info("OSC Server port is default.")

try:
    application = openvr.init(openvr.VRApplication_Utility)
    openvr.VRApplications().addApplicationManifest(get_absolute_path("app.vrmanifest"))
    logging.info("Added VRManifest.")
    vmr = voicemeeter.remote(KIND)
    vmr.login()
    logging.info("Logged in to Voicemeeter.")
    if conf["startup_profile"] is not None and conf["startup_profile"] != "":
        set_profile(conf["startup_profile"], None)
except Exception as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, traceback.format_exc(), "VRCMeeter - Error", 0)
    logging.error(traceback.format_exc())
    exit()

if STRIPS_IN is None or len(STRIPS_IN) == 1 and STRIPS_IN[0] == -1:
    STRIPS_IN = {}
elif len(STRIPS_IN) == 0:
    STRIPS_IN = [i for i in range(len(vmr.inputs))]

if STRIPS_OUT is None or len(STRIPS_OUT) == 1 and STRIPS_OUT[0] == -1:
    STRIPS_OUT = {}
elif len(STRIPS_OUT) == 0:
    STRIPS_OUT = [i for i in range(len(vmr.outputs))]

for strip in STRIPS_IN:
    gains_in[strip] = round(vmr.inputs[strip].gain, 1)
    logging.debug(f"IN-{strip} gain: {gains_in[strip]}")
for strip in STRIPS_OUT:
    gains_out[strip] = round(vmr.outputs[strip].gain, 1)
    logging.debug(f"OUT-{strip} gain: {gains_out[strip]}")

try:
    osc_client = udp_client.SimpleUDPClient(OSC_SERVER_IP, OSC_CLIENT_PORT)

    disp = dispatcher.Dispatcher()
    disp.map(AVATAR_CHANGE_PARAMETER, avatar_change)
    disp.map(PARAMETER_RESTART, lambda addr, value: vmr.restart())
    logging.info(f"Bound restart to {PARAMETER_RESTART}")
    for i in range(len(PROFILES)):
        disp.map(f"{PARAMETER_PREFIX_PROFILE}{i}", lambda addr, value: set_profile(int(addr.split('_')[-1]), value))
        logging.info(f"Bound profile {PROFILES[i]} to {PARAMETER_PREFIX_PROFILE}{i}")

    for strip in STRIPS_IN:
        disp.map(f"{PARAMETER_PREFIX_IN}gain_{strip}", set_gain_variable_in)
        logging.info(f"Bound IN-{strip} to {PARAMETER_PREFIX_IN}gain_{strip}")

    for strip in STRIPS_OUT:
        disp.map(f"{PARAMETER_PREFIX_OUT}gain_{strip}", set_gain_variable_out)
        logging.info(f"Bound OUT-{strip} to {PARAMETER_PREFIX_OUT}gain_{strip}")

    server = osc_server.BlockingOSCUDPServer((OSC_SERVER_IP, OSC_SERVER_PORT), disp)
    server_thread = Thread(target=osc_server_serve, daemon=True)
    server_thread.start()

    logging.info("Waiting for VRChat to start.")
    while not is_vrchat_running():
        time.sleep(5)
    logging.info("VRChat started!")
    qclient = wait_get_oscquery_client()
    oscqs = OSCQueryService("VoicemeeterControl", HTTP_PORT, OSC_SERVER_PORT)
    oscqs.advertise_endpoint(AVATAR_CHANGE_PARAMETER, access="readwrite")
    oscqs.advertise_endpoint(PARAMETER_RESTART, access="readwrite")
    for i in range(len(PROFILES)):
        oscqs.advertise_endpoint(f"{PARAMETER_PREFIX_PROFILE}{i}", access="readwrite")

    for strip in STRIPS_IN:
        oscqs.advertise_endpoint(f"{PARAMETER_PREFIX_IN}gain_{strip}", access="readwrite")

    for strip in STRIPS_OUT:
        oscqs.advertise_endpoint(f"{PARAMETER_PREFIX_OUT}gain_{strip}", access="readwrite")


    avatar_change(None, None)

    update_timer = RepeatedTimer(0.3, set_gains)
    update_timer.start()
    
    while is_vrchat_running():
        time.sleep(5)

    logging.info("VRChat closed, exiting.")
    exit()
except OSError as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, "You can only bind to the port 9001 once.", "VRCMeeter - Error", 0)
    exit()
except zeroconf._exceptions.NonUniqueNameException as e:
    logging.error("NonUniqueNameException, trying again...")
    os.execv(sys.executable, ['python'] + sys.argv)
except KeyboardInterrupt:
    exit()
except Exception as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, traceback.format_exc(), "VRCMeeter - Unexpected Error", 0)
    logging.error(traceback.format_exc())
    exit()
