# Marstek-Venus-plugin
Domoticz plugin for Marstek Venus battery

Marstek Venus A plugin for Domoticz, developed using Basic Python Plugin Framework as provided by GizMoCuz for Domoticz</br></br>
* author WillemD61</br>
* current version: 1.0.5 see release notes within code </br>

Credit: This plugin re-uses the UDP API library developed by Ivan Kablar for his MQTT bridge (https://github.com/IvanKablar/marstek-venus-bridge).
The library was extended to cover all elements from the Open API specification and was made more responsive and reliable.</br></br>

Reference is made to the Marstek Open API specification version rev. 1.0

# Please make sure the Open API feature has been enabled via the Marstek mobile app.</br></br>

In my experience, sometimes the Open API enable setting in the Marstek App is automatically reset, resulting in timeouts in datacommunication.  If this happens you will have to enable it again.

# Modifications done to the venus_api.py library of Ivan Kablar:
1) Added the Masrtek.GetDevice function for device discovery (par 2.2.2 and 3.1.1)
2) Added both the Wifi and Bluetooth Getstatus functions (par 3.2.1. and 3.3.1)
3) Added the PV GetStatus function (par 3.5.1)
4) Changed the buffer size for the data reception.
5) Remove fixed period 0 for manual mode configuration
Also the test_api.py program was extended to include the above in the tests.

So the venus_api_v2 library now covers the full specification of Marstek Open API and can be used in any python program.

# Even though the functions are now present in the API library, the current version of this plugin does NOT (!!!) do the following:
1) implement the marstek.GetDevice UDP discovery to find Marstek devices on the network (par. 2.2.2 and 3.1.1). Instead, the Marstek device
    to be used has to be specified manually in the configuration parameters of this plugin.
2) implement the Wifi.GetStatus (par 3.2.1) to configure or obtain Wifi info
3) implement the BLE.GetStatus (par 3.3.1) to obtain Bluetooth info
4) configuration of up to 10 periods for manual operating mode in one go. It is possible to configure a manual period in Domoticz and then send it to the battery. Then you can configure a next and and send it. etc etc

# It does implement the following:
1) Get Battery, PV (photovoltaic) , ES (Energy System) and EM (Energy Meter) status info (par. 3.4, 3.5, 3.6.1 and 3.7.1)
2) Get current Eenergy System operating mode (par 3.6.3)
3) Change Energy System operating mode (auto, AI, manual, passive, UPS as shown in par 3.6.2) via a Domoticz selector switch.</br>
   A number of Domoticz devices are created to hold the manual mode configuration. These can be updated, for example using DzVents, and when the selector switch is activated (by hand of by software) the configuration will be sent to the battery. This can be repeated to send multiple period configurations.
5) Create all required Domoticz devices and load received data onto the devices.
6) Send an alert email when an error is received (if configured) or 3x full cycle timeouts occur, from version 1.0.4 onwards
7) Show data received in the domoticz log for debugging/monitoring (if configured)

# This plugin was tested using a single Marstek Venus A and a double Marstek Venus E v3.

Note on some systems the default Open API port seems to be 28416 instead of 30000. This can be configured in the startup page of the Domoticz plugin.</br>

To find out whch port on your system is used, you can use the following command on a Linux system:</br>
sudo nmap -sUV IPaddress -p 28000-30000</br>
of courses replacing IPaddress with your real IP address of the Marstek battery.</br>
It will scan the defined range and report back which port is open.</br>
Even then, on some (older?) systems the Open API port seems not to be working.

# Observations on the Marstek Open Api specification:
1) The specification includes reference to ID and SRC, maybe for multi-system environments, but that is not clear.
2) par 3.2.1 : the wifi response also includes a wifi_mac field
3) par 3.5.1 : the pv response also includes a pv_state field and reports all fields for each  of the PV connections (4x)
4) par 3.6.3 : the response depends on the mode. For auto (=self-consumption) the energy meter mode fields are also includes but
               often with all values=0. For AI the energy meter mode fields are included with actual values. Note also that the UPS mode
               in the APP is reported as a manual mode. (in UPS mode backup-power is switched on)
5) par 3.7.1 : the response also includes total input energy and output energy of the P1 meter.
6) Passive mode requires power and countdown as parameters, but these don't seem to have any effect. Passive is passive, so no action, no mode active.

Some duplicate values are present when looking at all data responses (soc 3x, ongrid and offgrid power 2x, EM data depending on mode 2x)
For now these are included but might be removed later.

If multiple plugins are installed for multi-system environments then some devices will be duplicated (like the devices holding the P1 values). These duplicate devices can be disabled in Domoticz. The plugin will skip the updates of disabled devices.

# Installation instructions

1) Login to the Domoticz server and obtain a command line.
2) Change to the plugin directory with "cd domoticz/plugins".
3) Create a new plugin directory with "mkdir Marstek-Venus-plugin".
4) Change to the new directory with "cd Marstek-Venus-plugin".
5) Copy the file plugin.py and venus_api_v2.py from this Github repository into the Marstek-Venus-plugin directory.
6) Restart Domoticz with "sudo service domoticz restart".
7) Once restarted, select the Marstek Open API plugin via the Domoticz Setup-Hardware menu, give it a name, fill in the required fields and confirm.
8) It will now create the new devices and after the first polling interval, it will start collecting the data.
9) Check the Domoticz log file for any issues and progress. 

Step 3 to 5 above can be replaced with "git clone https://github.com/WillemD61/Marstek-Venus-plugin" if git is installed on your server.

# Usage

A DzVents script is available here to set initial values on the devices for manual mode and passive mode. Copy that file and run it once at a time suitable to you.
After that you can switch Marstek operating mode by pressing the selector switch on the Domoticz switch tab. Switching might take a short time because it will wait until the ongoing data collection has finished.</br></br>
This can also be triggered by software, if desired.</br>

Note setting power to -1 for the manual mode and then sending it to the battery by pressing the switch will activate manual mode in self-consumption (Dutch: nul-op-de-meter) setting for the defined period. If you want full time self consumption you just select that on the switch.

Further DzVents or python programs can be developed to customize your battery usage, for example setting the system to passive mode when the car is charging, assuming you have sensors for that in your system.</br></br>

Note the UDP communication is not very reliable. A change of operating mode might not always be done, despite retries. In that case the switch will not change to the selected mode either and you
have to try again. Also data collection sometimes runs into timeouts. It will retry automatically to collect data.

Two test programs are available to check all API commands in your environment. For the test program the config.json file has to be adapted with the correct IP number and MAC address.
I am curious to see what response is given in multi-system and multi-battery environments.

Any feedback appreciated.

# Release Notes

Release notes are included in the plugin.py file, not repeated here. Please also install the venus_api_v2.py file when installing a new plugin version.

# Undocumented API features

1) Activation of UPS mode is possible, although not mentioned in the Open API specification
2) Setting the power to -1 in manual mode means "self consumption" mode at the defined interval.

# Bugs

In Open API (so needs to be solved by Marstek)</br>
1) If UPS was set and the APP is used to switch to manual mode, the Open API continues to report UPS mode.
2) The power and countdown settings for passive mode, as per Open API specification, do not have an effect.
3) A power setting for UPS mode is required in the request, but does not have an effect, and therefore cannot be configured.
4) pv1_power is reported a factor 10 too high, pv2_power is reported corrrectly (3 and 4 not tested)
5) ES.Getstatus always reports pv_power 0 and total_pv_energy 0, even if solar panels are connected to pv1 and pv2 and produce energy.

In the plugin:
1) Between initial startup and first data update the log shows "Error: Invalid Number sValue: '%' for device idx: '%'". This is probably due to creation of P1 device without initial value. The error message does not return after first data update.


