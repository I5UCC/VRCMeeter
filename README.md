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

After setting up the programs settings to your liking, you need to add the bound parameters to VRChat. Here is an example on how that works:
I only want to control the trips 5, 6 and 7 in Voicemeeter Potato:

![image](https://github.com/I5UCC/VRCMeeter/assets/43730681/47da8ace-ade1-42e0-ac98-54ff8b343d2e)

As i am using Voicemeeter Potato, i set the `voicemeeter_type` setting in the `config.json` file to potato:

`"voicemeeter_type": "potato",`

So we add those to the `config.json` file, and set the stips_out to -1, as we dont need them:

```
"strips_in": [5, 6, 7],
"strips_out": [-1],
```

I also want to be able to load one of my profiles called vr.xml, so i add that to my config:

`"profiles": ["vr.xml"],`

Now after running the program, it shows me the parameters it has bound now:

![image](https://github.com/I5UCC/VRCMeeter/assets/43730681/ace90aa7-a0f4-45d8-8c73-b73805ca98a7)

Now i need to add these Parameters to my VRChat avatar. To do that you open the avatars expression parameters and add as many lines as you need:

![image](https://github.com/I5UCC/VRCMeeter/assets/43730681/f658a2a4-9a41-4f28-8fe8-7870423af95d)

If you don't want to waste Parameter space of your avatar, make sure they are not synced (last checkbox on the right unticked). <br>
For parameters that control the gain of a strip, choose the parameter type ***float*** for anything else choose ***bool***

Now you need to add these Parameters to your expression Menu:

![image](https://github.com/I5UCC/VRCMeeter/assets/43730681/54a20849-8daa-4268-a9c4-521b690490ea)

For every parameter that is a ***bool***, set the type to ***button***, for every ***float*** parameter set it to ***radial puppet*** 

Aaaaaand you are done! You best reset your OSC Configuration after updating an existing avatar with those parameters. You can do that as follows:
- Close VRChat.
- Open 'Run' in Windows (Windows Key + R)
- Type in `%APPDATA%\..\LocalLow\VRChat\VRChat\OSC`
- Delete the folders that start with 'usr_*'.
- Startup VRChat again and it should work.
