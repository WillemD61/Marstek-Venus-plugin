# Marstek Venus A plugin for Domoticz, developed using Basic Python Plugin Framework as provided by GizMoCuz for Domoticz
#
# author WillemD61
# version 1.0.0
#
# This plugin re-uses the UDP API library developed by Ivan Kablar for his MQTT bridge (https://github.com/IvanKablar/marstek-venus-bridge)
# The library was extended to cover all elements from the specification and was made more responsive and reliable.
#
# Please make sure the Open API feature has been enabled via the Marstek mobile app
#
# Reference is made to the Marstek Open API specification version rev. 1.0
#
# Modifications done to the venus_api.py library of Ivan Kablar:
# 1) Added the Masrtek.GetDevice function for device discovery (par 2.2.2 and 3.1.1)
# 2) Added both the Wifi and Bluetooth Getstatus functions (par 3.2.1. and 3.3.1)
# 3) Added the PV GetStatus function (par 3.5.1)
# 4) Changed the buffer size for the data reception.
# 5) Remove fixed period 0 for manual mode configuration
# Also the test_api.py program was extended to include the above in the tests.
#
# So the venus_api_v2 library now covers the full specification of Marstek Open API and can be used in any python program.
#
# Even though the functions are now present in the API library, the current version of this plugin does NOT (!!!) do the following:
#  1) implement the marstek.GetDevice UDP discovery to find Marstek devices on the network (par. 2.2.2 and 3.1.1). Instead, the Marstek device
#     to be used has to be specified manually in the configuration parameters of this plugin.
#  2) implement the Wifi.GetStatus (par 3.2.1) to configure or obtain Wifi info
#  3) implement the BLE.GetStatus (par 3.3.1) to obtain Bluetooth info
#  4) configuration of up to 10 periods for manual operating mode. For now it will handle one single period.
#
# It does implement the following:
#  1) Get Battery, PV, ES (Energy System) and EM (Energy Meter) status info (par. 3.4, 3.5, 3.6.1 and 3.7.1)
#  2) Get current Eenergy System operating mode (par 3.6.3)
#  3) Change Energy System operating mode (auto, AI, manual, passive as shown in par 3.6.2)
#       note the config of periods for manual mode needs to be further developed in future version of this plugin.
#  4) Create all required Domoticz devices and load received data onto the devices.
#  5) Send an alert when an error is received (if configured)
#  6) Show data received in the domoticz log for debugging/monitoring (if configured)
#
# This plugin was not tested in a multi-system environment. Only one Marstek Venus A was available for testing.
#
# Observations on teh Marstek Open Api specification:
# 1) The specification includes reference to ID and SRC, maybe for multi-system environments, but that is not clear.
# 2) par 3.2.1 : the wifi response also includes a wifi_mac field
# 3) par 3.5.1 : the pv response also includes a pv_state field and reports all fields for each  of the PV connections (4x)
# 4) par 3.6.3 : the response depends on the mode. For auto (=self-consumption) the energy meter mode fields are also includes but
#                often with all values=0. For AI the energy meter mode fields are included with actual values. Note also that the UPS mode
#                in the APP is reported as a manual mode. (in UPS mode backup-power is switched on)
# 5) par 3.7.1 : the response also includes total input energy and output energy of the P1 meter.
#
# Some duplications are present when looking at all responses (soc 3x, ongrid and offgrid power 2x, EM data depending on mode 2x

"""
<plugin key="MarstekOpenAPI" name="Marstek Open API" author="WillemD61" version="1.0.0" >
    <description>
        <h2>Marstek Open API plugin</h2><br/>
        This plugin uses the API for Marstek battery systems to get the values of various parameters<br/>
        and then load these values onto Domoticz devices. Devices will be created if they don't exists already.<br/><br/>
        Note the Open API feature needs to be enabled in the Marstek app first.<br/>
        Configuration options...
    </description>
    <params>
        <param field="Address" label="Marstek IP Address" width="200px" required="true"/>
        <param field="Port" label="Marstek Port" width="100px" required="true" default="30000"/>
        <param field="Mode1" label="Polling Interval" width="150px">
            <options>
                <option label="30 seconds" value="30" /> # maximum domoticz heartbeat time is 30 seconds
                <option label="1 minute" value="60" default="true" />
                <option label="2 minutes" value="120" />
                <option label="3 minutes" value="180" />
                <option label="4 minutes" value="240" />
                <option label="5 minutes" value="300" />
            </options>
        </param>
        <param field="Mode2" label="Alerts On" width="150px">
            <options>
                <option label="Yes" value="Yes" default="true" />
                <option label="No" value="No" />
            </options>
        </param>
        <param field="Mode3" label="Show data in log" width="150px">
            <options>
                <option label="Yes" value="Yes" />
                <option label="No" value="No" default="true" />
            </options>
        </param>
        <param field="Mode4" label="Max output W configured" width="150px" required="true">
        </param>
    </params>
</plugin>
"""


import DomoticzEx as Domoticz
import json,requests   # make sure these are available in your system environment
from requests.exceptions import Timeout

from venus_api_v2 import VenusAPIClient
debug=False

# A dictionary to list all parameters that can be retrieved from Marstek and to define the Domoticz devices to hold them.
# currently only english names are provided, can be extended with other languages later

# Dictionary structure is as follows: Property (from API spec) : [ Unit, Type, Subtype, Switchtype, OptionsList{}, Multiplier, Name, Source ],

DEVSLIST={
# response Bat.GetStatus
    "soc"             : [1,  243,  6, 0, {}, 1   ,"Battery SOC","BAT"], # duplicate ? (soc, bat_soc)
    "charg_flag"      : [2,  244, 73, 0, {}, 1   ,"Charge permission","BAT"],
    "dischrg_flag"    : [3,  244, 73, 0, {}, 1   ,"Discharge permission","BAT"],
    "bat_temp"        : [4,   80,  5, 0, {}, 1   ,"Battery temperature","BAT"],
    "bat_capacity"    : [5,  113,  0, 0, {}, 1   ,"Remaining Capacity","BAT"],
    "rated_capacity"  : [6,  113,  0, 0, {}, 1   ,"Rated Capacity","BAT"],
# response PV.GetStatus
    "pv1_power"       : [7,  248,  1, 0, {}, 1   ,"PV1 power","PV"], # 4 groups, although not in specification ver. 1.0
    "pv1_voltage"     : [8,  243,  8, 0, {}, 1   ,"PV1 voltage","PV"],
    "pv1_current"     : [9,  243, 23, 0, {}, 1   ,"PV1 current","PV"],
    "pv1_state"       : [10, 244, 73, 0, {}, 1   ,"PV1 state","PV"], # pv_state not in specification ver. 1.0
    "pv2_power"       : [11, 248,  1, 0, {}, 1   ,"PV2 power","PV"],
    "pv2_voltage"     : [12, 243,  8, 0, {}, 1   ,"PV2 voltage","PV"],
    "pv2_current"     : [13, 243, 23, 0, {}, 1   ,"PV2 current","PV"],
    "pv2_state"       : [14, 244, 73, 0, {}, 1   ,"PV2 state","PV"],
    "pv3_power"       : [15, 248,  1, 0, {}, 1   ,"PV3 power","PV"],
    "pv3_voltage"     : [16, 243,  8, 0, {}, 1   ,"PV3 voltage","PV"],
    "pv3_current"     : [17, 243, 23, 0, {}, 1   ,"PV3 current","PV"],
    "pv3_state"       : [18, 244, 73, 0, {}, 1   ,"PV3 state","PV"],
    "pv4_power"       : [19, 248,  1, 0, {}, 1   ,"PV4 power","PV"],
    "pv4_voltage"     : [20, 243,  8, 0, {}, 1   ,"PV4 voltage","PV"],
    "pv4_current"     : [21, 243, 23, 0, {}, 1   ,"PV4 current","PV"],
    "pv4_state"       : [22, 244, 73, 0, {}, 1   ,"PV4 state","PV"],
# response ES.GetMode
    "mode"            : [23, 243, 19, 0, {}, 1   ,"ES mode","ESM"],
    "ongrid_power"    : [24, 248,  1, 0, {}, 1   ,"ES on-grid power","ESM"], # duplicate ?
    "offgrid_power"   : [25, 248,  1, 0, {}, 1   ,"ES off-grid power","ESM"], # duplicate ?
    "bat_soc"         : [26, 243,  6, 0, {}, 1   ,"ES Battery Soc","ESM"], # duplicate ?
# note in case of auto or AI mode the response of Es.GetMode also includes EM.GetStatus data
# reponse ES.GetStatus
    "es_bat_soc"      : [27, 243,  6, 0, {}, 1   ,"ES Total SOC","ESS"],  # duplicate ? note es_ added to name to create unique key
    "bat_cap"         : [28, 113,  0, 0, {}, 1   ,"ES Total capacity","ESS"], # duplicate value but still unique name (other is bat_capacity)
    "pv_power"        : [29, 248,  1, 0, {}, 1   ,"ES PV charging power","ESS"],
    "es_ongrid_power" : [30, 248,  1, 0, {}, 1   ,"ES on-grid power","ESS"], # duplicate ? note es_ added to name to create unique key
    "es_offgrid_power": [31, 248,  1, 0, {}, 1   ,"ES off-grid power","ESS"], # duplicate ? note es_ added to name to create unique key
#    "bat_power"      : "ES battery power W"], # not present in ES.getStatus response, although in specification ver 1.0
    "total_pv_energy"          : [32, 113,  0, 0, {}, 1   ,"ES Total PV energy generated","ESS"],
    "total_grid_output_energy" : [33, 113,  0, 0, {}, 1   ,"ES Total grid output energy","ESS"],
    "total_grid_input_energy"  : [34, 113,  0, 0, {}, 1   ,"ES Total grid input energy","ESS"],
    "total_load_energy"        : [35, 113,  0, 0, {}, 1   ,"ES Total off-grid energy consumed","ESS"],
# response EM.GetStatus
    "ct_state"        : [36, 244, 73, 0, {}, 1,  "P1 CT state","EMS"],
    "a_power"         : [37, 248,  1, 0, {}, 1   ,"P1 Phase A power","EMS"],
    "b_power"         : [38, 248,  1, 0, {}, 1   ,"P1 Phase B power","EMS"],
    "c_power"         : [39, 248,  1, 0, {}, 1   ,"P1 Phase C power","EMS"],
    "total_power"     : [40, 248,  1, 0, {}, 1   ,"P1 Total power","EMS"],
    "input_energy"    : [41, 113,  0, 0, {}, 0.1 ,"P1 Total input energy","EMS"], # in response, although not in specification ver 1.0
    "output_energy"   : [42, 113,  0, 0, {}, 0.1 ,"P1 Total output energy","EMS"], # in response, although not in specification ver 1.0
# device for holding one single manual mode setting
    "time_period"     : [43, 243, 19, 0, {}, 1   ,"Manual Mode periodnr","MM"],
    "start_time"      : [44, 243, 19, 0, {}, 1   ,"Manual Mode starttime","MM"],
    "end_time"        : [45, 243, 19, 0, {}, 1   ,"Manual Mode endtime","MM"],
    "week_set"        : [46, 243, 19, 0, {}, 1   ,"Manual Mode weekdays","MM"],
    "mm_power"        : [47, 248,  1, 0, {}, 1   ,"Manual Mode power","MM"], # note mm_ added to create unique key
# device for holding passive mode countdown
    "pm_power"        : [48, 248,  1, 0, {}, 1   ,"Passive Mode power","PM"], # note pm_ added to create unique key
    "countdown"       : [49, 243, 19, 0, {}, 1   ,"Passive Mode countdown s","PM"],
# device to activate mode switch
# do not change name, used on onCommand code below
    "select Marstek mode"     : [50, 244, 62, 18, {"LevelActions":"||||","LevelNames":"|AutoSelf|AI|Manual|Passive","LevelOffHidden":"true","SelectorStyle":"0"}, 1 ,"Select Marstek mode","SM"],
} # end of dictionary

class MarstekPlugin:
    enabled = False
    def __init__(self):
        return

    def onStart(self):
        Domoticz.Log("onStart called with parameters")
        for elem in Parameters:
            Domoticz.Log(str(elem)+" "+str(Parameters[elem]))
        self.IPAddress=str(Parameters["Address"])
        self.Port=int(Parameters["Port"])
        if int(Parameters["Mode1"])<=30: # heartbeat is max 30 seconds, so >30 seconds requires skipping action on heartbeat
            Domoticz.Heartbeat(int(Parameters["Mode1"]))
            self.heartbeatWaits=0
        else:
            Domoticz.Heartbeat(30)
            self.heartbeatWaits=int(int(Parameters["Mode1"])/30 - 1)
        self.notificationsOn=(Parameters["Mode2"]=="Yes")
        self.emailAlertSent=False
        self.showDataLog=(Parameters["Mode3"]=="Yes")
        self.maxOutputPower=int(Parameters["Mode4"])
        self.heartbeatCounter=0
        self.stillbusy=False
        self.Hwid=Parameters['HardwareID']
        # cycle through device list and create any non-existing devices when the plugin/domoticz is started
        for Dev in DEVSLIST:
            Unit=DEVSLIST[Dev][0]
            DeviceID="{:04x}{:04x}".format(self.Hwid,Unit)
            Type=DEVSLIST[Dev][1]
            Subtype=DEVSLIST[Dev][2]
            Switchtype=DEVSLIST[Dev][3]
            Options=DEVSLIST[Dev][4]
            Name="MV:"+DEVSLIST[Dev][6]
            if DeviceID not in Devices:
                Domoticz.Status(f"Creating device for Field {Dev} ...")
                if ((Type==243) and (Subtype==29)):
                    # below code puts an initial svalue on the kwh device and then changes the type to "computed". This is to work around a BUG in Domoticz for computed kwh devices. See issue 6194 on Github.
                    Domoticz.Unit(DeviceID=DeviceID,Unit=Unit, Name=Name, Type=Type, Subtype=Subtype, Switchtype=Switchtype, Options={}, Used=1).Create()
                    Devices[DeviceID].Units[Unit].sValue="0;0"
                    Devices[DeviceID].Units[Unit].Update()
                    Devices[DeviceID].Units[Unit].Options=Options
                    Devices[DeviceID].Units[Unit].Update(UpdateOptions=True)
                else:
                    Domoticz.Unit(DeviceID=DeviceID,Unit=Unit, Name=Name, Type=Type, Subtype=Subtype, Switchtype=Switchtype, Options=Options, Used=1).Create()
        for Dev in DEVSLIST:
            Domoticz.Log("DEVSLIST "+str(DEVSLIST[Dev][0])+DEVSLIST[Dev][6])


    def onStop(self):
        Domoticz.Log("onStop called")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log("onConnect called")

    def onMessage(self, Connection, Data):
        Domoticz.Log("onMessage called")

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        # used when a mode is selected using the selector switch in Domoticz
        if debug: Domoticz.Log("onCommand called for Device " + str(DeviceID) + " Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
        modeSelectorUnit=DEVSLIST["select Marstek mode"][0]
        expectedDeviceID="{:04x}{:04x}".format(self.Hwid,modeSelectorUnit)
        if str(Command)=="Set Level" and DeviceID==expectedDeviceID: # it is a mode change initiated using the selector switch
            client = VenusAPIClient(ip=self.IPAddress, port=self.Port, timeout=5)
            if Level==10: # auto mode (=self consumption)
                success=client.set_auto_mode()
                if success:
                    if debug: Domoticz.Log("Succesfully changed to auto mode (=self consumption mode).")
                    Devices[DeviceID].Units[Unit].sValue=str(Level)
                    Devices[DeviceID].Units[Unit].sValue=Level
                    Devices[DeviceID].Units[Unit].Update()
                else:
                    Domoticz.Log("Change to auto mode (=self consumption mode) failed.")
            elif Level==20: # AI mode
                success=client.set_ai_mode()
                if success:
                    Domoticz.Log("Succesfully changed to AI optimisation mode.")
                    Devices[DeviceID].Units[Unit].sValue=str(Level)
                    Devices[DeviceID].Units[Unit].sValue=Level
                    Devices[DeviceID].Units[Unit].Update()
                else:
                    Domoticz.Log("Change to AI optimisation mode failed.")
            elif Level==30: # manual mode
                # check and build parameters. the following devices should contain config data
                timeperiodUnit=DEVSLIST["time_period"][0]
                starttimeUnit=DEVSLIST["start_time"][0]
                endtimeUnit=DEVSLIST["end_time"][0]
                weekdayUnit=DEVSLIST["week_set"][0]
                mmpowerUnit=DEVSLIST["mm_power"][0]
                timeperiod=Devices["{:04x}{:04x}".format(self.Hwid,timeperiodUnit)].Units[timeperiodUnit].sValue
                starttime=Devices["{:04x}{:04x}".format(self.Hwid,starttimeUnit)].Units[starttimeUnit].sValue
                endtime=Devices["{:04x}{:04x}".format(self.Hwid,endtimeUnit)].Units[endtimeUnit].sValue
                weekday=Devices["{:04x}{:04x}".format(self.Hwid,weekdayUnit)].Units[weekdayUnit].sValue
                mmpower=Devices["{:04x}{:04x}".format(self.Hwid,mmpowerUnit)].Units[mmpowerUnit].sValue
                if int(timeperiod)>=0 and int(timeperiod)<=9:
                    startHr=int(starttime[0:2])
                    startMm=int(starttime[3:5])
                    endHr=int(endtime[0:2])
                    endMm=int(endtime[3:5])
                    if (startHr>=0 and startHr<=23 and startMm>=0 and startMm<=59) and (endHr>=0 and endHr<=23 and endMm>=0 and endMm<=59):
                        if (startHr*60+startMm)<(endHr*60+endMm):
                            starttimestring=starttime[0:2]+":"+starttime[3:5] # make sure separator is ":"
                            endtimestring=endtime[0:2]+":"+endtime[3:5] # make sure separator is ":"
                            weekdayValid=True
                            weekdayvalue=0
                            bitvalue=64
                            # should be string of 7 x 0 or 1, indicating on/off of weekday starting with Sunday, to match the APP
                            # note the value passed in the API is low to high bit, starting with Monday
                            for dayCharacter in weekday:
                                if (dayCharacter!="0" and dayCharacter!="1") or len(weekday)!=7:
                                    weekdayValid=False
                                else:
                                    weekdayvalue+=bitvalue*int(dayCharacter)
                                if bitvalue==64:
                                    bitvalue=1
                                else:
                                    bitvalue=bitvalue*2
                            if weekdayValid:
                                mmpower=int(mmpower)
                                # positive is charge, negative is discharge
                                if mmpower<=1200 and mmpower>=-1*self.maxOutputPower:
                                    # all validation done
                                    enable=1 # assuming period should be active
                                    success=client.set_manual_mode(mmpower,int(timeperiod),starttimestring,endtimestring,weekdayvalue,enable)
                                    if success:
                                        Domoticz.Log("Succesfully changed to manual mode."+str(mmpower))
                                        Devices[DeviceID].Units[Unit].sValue=str(Level)
                                        Devices[DeviceID].Units[Unit].sValue=Level
                                        Devices[DeviceID].Units[Unit].Update()
                                    else:
                                        Domoticz.Log("Change to manual mode failed")
                                else:
                                    Domoticz.Log("Error: power settings not valid for manual mode.")
                            else:
                                Domoticz.Log("Error: weekday settings not valid for manual mode, must be 7x 0/1")
                        else:
                            Domoticz.Log("Error: start time must be before end time for manual mode")
                    else:
                        Domoticz.Log("No valid start or end time set for manual mode")
                else:
                    Domoticz.Log("No valid timeperiod set for manual mode")
            elif Level==40: # passive mode
                # check and build parameters for passive mode
                pmpowerUnit=DEVSLIST["pm_power"][0]
                countdownUnit=DEVSLIST["countdown"][0]
                pmpower=Devices["{:04x}{:04x}".format(self.Hwid,pmpowerUnit)].Units[pmpowerUnit].sValue
                countdown=Devices["{:04x}{:04x}".format(self.Hwid,countdownUnit)].Units[countdownUnit].sValue
                pmpower=int(pmpower)
                countdown=int(countdown)
                if pmpower<=1200 and pmpower>=-1*self.maxOutputPower:
                    # all validation done
                    success=client.set_passive_mode(pmpower,countdown)
                    if success:
                        Domoticz.Log("Succesfully changed to passive mode.")
                        Devices[DeviceID].Units[Unit].sValue=str(Level)
                        Devices[DeviceID].Units[Unit].sValue=Level
                        Devices[DeviceID].Units[Unit].Update()
                    else:
                        Domoticz.Log("Change to passive mode failed")
                else:
                    Domoticz.Log("No valid power setting for passive mode")
        else:
            if debug: Domoticz.Log("Command "+str(Command)+" DeviceID "+DeviceID+" ExpectedID "+expectedDeviceID)

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Log("onDisconnect called")

    def onHeartbeat(self):
        Domoticz.Log("onHeartbeat called")
        self.heartbeatCounter+=1
        if self.stillbusy and self.heartbeatCounter<5: # max 5 cycles total wait
            if debug: Domoticz.Log("Skipping another heartbeat - data collection still busy")
            return
        else:
            # skip one or more heartbeats if polling interval > 30 seconds
            if self.heartbeatWaits==self.heartbeatCounter-1:
                self.stillbusy=True
                self.getVenusData()
                self.heartbeatCounter=0
                self.stillbusy=False

    def processValues(self, source, response):
        if self.showDataLog: Domoticz.Log(response)
        if debug: Domoticz.Log(response)
        for Dev in response:

            # do not process ID or the energy meter data received from getmode command in certain modes
            if Dev!="id" and not (source=="ESM" and (Dev=="mode" or Dev=="ongrid_power" or Dev=="offgrid_power" or Dev=="bat_soc")) :

                if source=="ESS": # handle the duplicate ESS field names, also received in other commands
                    if (Dev=="bat_soc" or Dev=="ongrid_power" or Dev=="offgrid_power"):
                        DevName="es_"+Dev
                    else:
                        DevName=Dev
                else:
                    DevName=Dev

                # first check whether any unexpected/new fields are received, avoid key errors
                if DEVSLIST.get(DevName)==None:
                    Domoticz.Log("Unexpected/new field received, source : "+source+" field "+DevName)
                    Domoticz.Log("API might have changed. Needs to be investigated.")
                else:

                    type=DEVSLIST[DevName][1]
                    subtype=DEVSLIST[DevName][2]
                    Unit=DEVSLIST[DevName][0]
                    DeviceID="{:04x}{:04x}".format(self.Hwid,Unit)

                    if debug: Domoticz.Log("processing values "+source+" "+DevName+" "+str(response[Dev]))

                    if (Devices[DeviceID].Units[Unit].Used==1) : # only process active devices
                        if ((type==80) or # temperature device
                           (type==113) or # counter device
                           ((type==243) and (subtype==6)) or # percentage device
                           ((type==243) and (subtype==8)) or # percentage device
                           ((type==243) and (subtype==23)) or # percentage device
                           ((type==243) and (subtype==31)) # custom device
                              ):
                            multiplier=DEVSLIST[DevName][5]
                            if multiplier==1:
                                fieldValue=round(float(multiplier*response[Dev]),0)
                            else:
                                fieldValue=round(float(multiplier*response[Dev]),1)
                            Devices[DeviceID].Units[Unit].nValue=int(fieldValue)
                            Devices[DeviceID].Units[Unit].sValue=str(int(fieldValue))
                            Devices[DeviceID].Units[Unit].Update()
                        if ((type==243) and (subtype==19)): # text device
                            fieldValue=response[Dev]
                            Devices[DeviceID].Units[Unit].nValue=0
                            fieldText=str(fieldValue)
                            Devices[DeviceID].Units[Unit].sValue=fieldText
                            Devices[DeviceID].Units[Unit].Update()
                        if ((type==244) or (type==248)) : # switch device
                            fieldValue=response[Dev]
                            if fieldValue==True:
                                fieldValue=1
                            else:
                                fieldValue=0
                            Devices[DeviceID].Units[Unit].nValue=fieldValue
                            fieldText=str(fieldValue)
                            Devices[DeviceID].Units[Unit].sValue=fieldText
                            Devices[DeviceID].Units[Unit].Update()


    def getVenusData(self):
        if debug: Domoticz.Log("Marstek Plugin getVenusData called")
        self.Hwid=Parameters['HardwareID']
        try:
            client = VenusAPIClient(ip=self.IPAddress, port=self.Port, timeout=5)
            response=client.get_battery_status()
            if debug: Domoticz.Log("battery status data received"+str(response))
            if response is not None:
                self.processValues("BAT",response)

            response=client.get_pv_status()
            if debug: Domoticz.Log("pv status data received"+str(response))
            if response is not None:
                self.processValues("PV",response)

            response=client.get_em_status()
            if debug: Domoticz.Log("em status data received"+str(response))
            if response is not None:
                self.processValues("EMS",response)

            response=client.get_energy_status()
            if debug: Domoticz.Log("es status data received"+str(response))
            if response is not None:
                self.processValues("ESS",response)

            response=client.get_mode()
            if debug: Domoticz.Log("get mode data received"+str(response))
            if response is not None:
                self.processValues("ESM",response)

            if self.emailAlertSent==True:
                self.emailAlertSent=False
                #sendemail=requests.get("http://127.0.0.1:8080/json.htm?type=command&param=sendnotification&subject='Venus comms working again'&body='Problem solved'")

        except Timeout:
            Domoticz.Error("Timeout on getting Venus data. Check connection.")
            if self.notificationsOn and self.emailAlertSent==False:
                #sendemail=requests.get("http://127.0.0.1:8080/json.htm?type=command&param=sendnotification&subject='ATTENTION: Venus communication timeout'&body='Please check'")
                self.emailAlertSent=True
        except:
            Domoticz.Error("No proper Venus data received. Check results.")
            if self.notificationsOn and self.emailAlertSent==False:
                #sendemail=requests.get("http://127.0.0.1:8080/json.htm?type=command&param=sendnotification&subject='ATTENTION: Venus communication data error'&body='Please check the log and solve the error.'")
                self.emailAlertSent=True


global _plugin
_plugin = MarstekPlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        Domoticz.Debug("Device ID:       '" + str(Device.DeviceID) + "'")
        Domoticz.Debug("--->Unit Count:      '" + str(len(Device.Units)) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            Domoticz.Debug("--->Unit:           " + str(UnitNo))
            Domoticz.Debug("--->Unit Name:     '" + Unit.Name + "'")
            Domoticz.Debug("--->Unit nValue:    " + str(Unit.nValue))
            Domoticz.Debug("--->Unit sValue:   '" + Unit.sValue + "'")
            Domoticz.Debug("--->Unit LastLevel: " + str(Unit.LastLevel))
    return
