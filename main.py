import voicemeeter
import json
import os
import sys
from pythonosc import dispatcher, osc_server, udp_client
from tinyoscquery.queryservice import OSCQueryService
from tinyoscquery.utility import get_open_tcp_port, get_open_udp_port, check_if_tcp_port_open, check_if_udp_port_open
from tinyoscquery.query import OSCQueryBrowser, OSCQueryClient
from psutil import process_iter
import time
import traceback
import ctypes
import zeroconf
from threading import Thread


def get_absolute_path(relative_path, script_path=__file__) -> str:
    """Gets absolute path from relative path"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(script_path)))
    return os.path.join(base_path, relative_path)


def get_voicemeeter_gain_from_float(f):
    return (f - 1) * 60


def get_float_from_voicemeeter_gain(g):
    return g / 60 + 1


def is_vrchat_running() -> bool:
    """Checks if VRChat is running."""
    _proc_name = "VRChat.exe" if os.name == 'nt' else "VRChat"
    return _proc_name in (p.name() for p in process_iter())


def wait_get_oscquery_client():
    service_info = None
    print("Waiting for VRChat to be discovered.", end="")
    while service_info is None:
        print(".", end="")
        browser = OSCQueryBrowser()
        time.sleep(2) # Wait for discovery
        service_info = browser.find_service_by_name("VRChat")
    print("\nVRChat discovered!")
    client = OSCQueryClient(service_info)
    print("Waiting for VRChat to be ready.", end="")
    while client.query_node(AVATAR_CHANGE_PARAMETER) is None:
        print(".", end="")
        time.sleep(2)
    print("\nVRChat ready!")
    return OSCQueryClient(service_info)


def set_gain(addr, value):
    print(f"Received {addr} {value}")
    strip = int(addr.split('_')[-1])
    gain = get_voicemeeter_gain_from_float(float(value))
    print(f"Setting gain of {strip} to {gain}, type {type(gain)}")
    vmr.inputs[strip].gain = gain


def avatar_change(addr, value):
    global vmr, strips

    print("Avatar changed!")

    for strip in strips:
        osc_client.send_message(f"{PARAMETER_PREFIX}vm_gain_{strip}", get_float_from_voicemeeter_gain(vmr.inputs[strip].gain))


def osc_server_serve():
    print(f"Starting OSC client on {osc_server_ip}:{osc_server_port}:{http_port}\n")
    server.serve_forever(2)



AVATAR_CHANGE_PARAMETER = "/avatar/change"
PARAMETER_PREFIX = "/avatar/parameters/"
try:
    conf = json.load(open('config.json'))

    # Can be 'basic', 'banana' or 'potato'
    kind = conf['voicemeeter_type']
    strips = conf['strips']
    osc_client_port = conf["port"]
    osc_server_port = conf['server_port']
    osc_server_ip = conf['ip']
    http_port = conf['http_port']
    avatar_changed = False

    vmr = voicemeeter.remote(kind)
    vmr.login()

    if osc_server_port != 9001:
        print("OSC Server port is not default, testing port availability and advertising OSCQuery endpoints")
        if osc_server_port <= 0 or not check_if_udp_port_open(osc_server_port):
            osc_server_port = get_open_udp_port()
        if http_port <= 0 or not check_if_tcp_port_open(http_port):
            http_port = osc_server_port if check_if_tcp_port_open(osc_server_port) else get_open_tcp_port()
    else:
        print("OSC Server port is default.")

    osc_client = udp_client.SimpleUDPClient(osc_server_ip, osc_client_port)

    disp = dispatcher.Dispatcher()
    disp.map(AVATAR_CHANGE_PARAMETER, avatar_change)
    for strip in strips:
        disp.map(f"{PARAMETER_PREFIX}vm_gain_{strip}", set_gain)
        print(f"Bound to {PARAMETER_PREFIX}vm_gain_{strip}")

    server = osc_server.ThreadingOSCUDPServer((osc_server_ip, osc_server_port), disp)
    server_thread = Thread(target=osc_server_serve, daemon=True)
    server_thread.start()

    print("Waiting for VRChat to start.")
    while not is_vrchat_running():
        time.sleep(3)
    print("VRChat started!")
    qclient = wait_get_oscquery_client()
    oscqs = OSCQueryService("VoicemeeterControl", http_port, osc_server_port)
    oscqs.advertise_endpoint(AVATAR_CHANGE_PARAMETER, access="readwrite")
    for strip in strips:
        oscqs.advertise_endpoint(f"{PARAMETER_PREFIX}vm_gain_{strip}", access="readwrite")

    avatar_change(None, None)
    while True:
        time.sleep(1)
except OSError as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, "You can only bind to the port 9001 once.", "AvatarParameterSync - Error", 0)
    sys.exit(1)
except zeroconf._exceptions.NonUniqueNameException as e:
    print("NonUniqueNameException, trying again...")
    os.execv(sys.executable, ['python'] + sys.argv)
except Exception as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, traceback.format_exc(), "AvatarParameterSync - Unexpected Error", 0)
    print(traceback.format_exc())
    sys.exit(1)
