# VRCMeeter [![Github All Releases](https://img.shields.io/github/downloads/i5ucc/VRCMeeter/total.svg)](https://github.com/I5UCC/VRCMeeter/releases/latest) <a href='https://ko-fi.com/i5ucc' target='_blank'><img height='35' style='border:0px;height:25px;' src='https://az743702.vo.msecnd.net/cdn/kofi3.png?v=0' border='0' alt='Buy Me a Coffee at ko-fi.com' />

Control Voicemeeter's Virtual Inputs/Outputs in VRChat via OSC. 

https://github.com/I5UCC/VRCVoiceMeeterControl/assets/43730681/d8f16c9c-84de-4aa2-820f-de59572e04fa

# Configuration / Usage

All of the configuration is done in the `config.json` file.
Currently this program only supports controlling gains of any input/output slider in Voicemeeter and loading profiles created in Voicemeeter.

| Option | Explanation |
| ------ | ----------- |
| ip | The IP used to send data to. |
| port | The Port used to send data to. |
| server_port | The Port used to recieve data from. When 0, a port is automatically chosen. |
| http_port | Port used to host the zeroconf server for discovery by vrchat. When 0, a port is a port is automatically chosen. |
| min_gain | ***Minimum*** gain for any slider in Voicemeeter. -60 is the default and doesn't go lower in Voicemeeter |
| max_gain | ***Maximum*** gain for any slider in Voicemeeter. 0 is the default but you can change it to up to 12 if you wish so. |
| voicemeeter_type | The type of voicemeeter application that you are using. Can be either `basic`, `banana` or `potato` |
| strips_in | Indices of ***input*** strips to bind to a VRChat parameter. If left empty, every available strip gets bound. If the only value is -1, no strips will be bound. |
| strips_out | Indices of ***output*** strips to bind to a VRChat parameter. If left empty, every available strip gets bound. If the only value is -1, no strips will be bound. |
| profiles | Array of Profiles that can be bound to VRChat parameters. Use the full name of the xml file, not the path, and have the xml file placed in the same folder as the executable. |
| startup_profile | Profile to load at the startup of this program, leave empty if not needed. |
