from cx_Freeze import setup, Executable

packages = ["pythonosc", "psutil", "zeroconf", "json", "threading", "time", "os", "sys", "ctypes", "traceback"]
file_include = ["config.json", "app.vrmanifest"]

build_exe_options = {"packages": packages, "include_files": file_include, 'include_msvcr': True, 'optimize': 2}

setup(
    name="VRCVoiceMeeterControl",
    version="0.1",
    description="Lets you control Voicemeeter from within VRChat over OSC",
    options={"build_exe": build_exe_options},
    executables=[Executable("main.py", target_name="VRCVoiceMeeterControl.exe", base=False), Executable("main.py", target_name="VRCVoiceMeeterControl_NoConsole.exe", base="Win32GUI")],
)