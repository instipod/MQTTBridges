#!python3
#Reads DSL bonding info from the Actiontec C3000A
#I use this modem in transparent bridging mode, so I don't monitor the modem PPP status here

import requests
import os
import time
import json
import paho.mqtt.client as mqtt

def publish_config(client, name, type, unique_id, unit, value_name, icon, avail_topic, serial_number, mac_address, sw_version, gated=True):
    config_payload = {
        "name": name,
        "unique_id": unique_id,
        "state_topic": "homeassistant/" + type + "/" + unique_id + "/state",
        "icon": icon,
        "device": {
            "connections": [
                ["mac", mac_address]
            ],
            "identifiers": [
                serial_number
            ],
            "manufacturer": "Actiontec",
            "model": "C3000A",
            "name": "DSL Modem " + serial_number,
            "sw_version": sw_version
        }
    }
    if (type == "sensor"):
        config_payload["unit_of_measurement"] = unit
        #config_payload["value_template"] = "{{ value_json." + value_name + "}}"
    if (gated):
        availability = {
            "topic": avail_topic,
            "payload_available": "ON",
            "payload_not_available": "OFF"
        }
        config_payload["availability"] = availability

    print("Publishing HA autodiscovery information for sensor " + unique_id)
    client.publish("homeassistant/" + type + "/" + unique_id + "/config", json.dumps(config_payload), retain=True)

def publish_sensor_config(client, shortname, shortid, unit, valuename, icon, serial_number, mac_address, sw_version, type="sensor", gated=True):
    publish_config(client, "Modem " + serial_number + " " + shortname, type, "modem_" + serial_number + "_" + shortid, unit, valuename, icon, "homeassistant/binary_sensor/modem_" + serial_number + "_communicating/state", serial_number, mac_address, sw_version, gated)

modemip = os.getenv("MODEM_IP", "")
modemuser = os.getenv("MODEM_USER", "admin")
modempass = os.getenv("MODEM_PASS", "")

timeout = os.getenv("TIMEOUT", "10")
interval = os.getenv("FETCH_INTERVAL", "60")

mqtthost = os.getenv("MQTT_HOST", "")
mqttuser = os.getenv("MQTT_USER", "")
mqttpass = os.getenv("MQTT_PASS", "")

hamode = os.getenv("HA_MODE", "enabled")
hamode = (hamode == "enabled")

if (modemip == ""):
    print("Modem IP address must be provided!")
    exit(1)

try:
    timeout = int(timeout)
except:
    print("Timeout must be a valid integer!")
    exit(1);

try:
    interval = int(interval)
except:
    print("Fetch interval must be a valid integer!")
    exit(1);

client = mqtt.Client("PyDSLModem")
if (mqttuser != ""):
    print("Using MQTT authentication as " + str(mqttuser))
    client.username_pw_set(mqttuser, mqttpass)
else:
    print("Not using MQTT authentication")
client.connect(mqtthost)

headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 6.0; WOW64; rv:24.0) Gecko/20100101 Firefox/24.0' }
firstrun = True
knownserial = ""

while (True):
    if (not firstrun):
        print("Sleeping for " + str(interval) + " seconds...")
        time.sleep(interval)
    else:
        firstrun = False

    try:
        s = requests.Session()
        if (modempass != ""):
            print("Authenticating to the modem as " + str(modemuser))
            login = s.post("http://" + str(modemip) + "/login.cgi", verify=False, headers=headers, data={"nothankyou": "1", "adminUserName": modemuser, "adminPassword": modempass})
        status = s.get("http://" + str(modemip) + "/modemstatus_home_refresh.html", verify=False, headers=headers, timeout=timeout)
    except:
        if (knownserial != ""):
            #serial number is known, report failure
            client.publish("modems/" + knownserial + "/communicating", False, qos=1, retain=True)
            if (hamode):
                client.publish("homeassistant/binary_sensor/modem_" + knownserial + "_communicating/state", "OFF",
                               qos=1, retain=True)

        print("Device is not available")
        continue

    try:
        content = str(status.content)

        firstsplit = content.split("|")
        serialnumber = firstsplit[2]
        macaddress = firstsplit[0].split(":")[8].replace("-", ":")
        sw_version = firstsplit[3]
        speeddata = firstsplit[1].split("+")
        totalupload = int(speeddata[1]) / 1000
        totaldownload = int(speeddata[2]) / 1000
        status = firstsplit[5].split("+")
        dslstatus = status[2]
        line1status = firstsplit[24].split("+")[6]
        line2status = firstsplit[26].split("+")[1]
        line1download = int(firstsplit[26].split("+")[0]) / 1000
        line1upload = int(firstsplit[25]) / 1000
        line2download = int(firstsplit[28].split("+")[0]) / 1000
        line2upload = int(firstsplit[27]) / 1000

        if (serialnumber == "N/A"):
            #user did not login, use ip as serial number
            serialnumber = modemip.replace(".", "_").replace(":", "_")

        if (knownserial != ""):
            if (knownserial != serialnumber):
                #serial number has changed
                #old modem is no longer communicating
                client.publish("modems/" + knownserial + "/communicating", False, qos=1, retain=True)
                if (hamode):
                    client.publish("homeassistant/binary_sensor/modem_" + knownserial + "_communicating/state", "OFF",
                                   qos=1, retain=True)

        if (knownserial == "" or knownserial != serialnumber):
            #modem first load yet
            if (hamode):
                publish_sensor_config(client, "Line 1 RX Rate", "l1rxrate", "Mbps", "rate", "mdi:speedometer", serialnumber,
                                      macaddress, sw_version)
                publish_sensor_config(client, "Line 2 RX Rate", "l2rxrate", "Mbps", "rate", "mdi:speedometer", serialnumber,
                                      macaddress, sw_version)
                publish_sensor_config(client, "Line 1 TX Rate", "l1txrate", "Mbps", "rate", "mdi:speedometer", serialnumber,
                                      macaddress, sw_version)
                publish_sensor_config(client, "Line 2 RX Rate", "l2rxrate", "Mbps", "rate", "mdi:speedometer", serialnumber,
                                      macaddress, sw_version)
                publish_sensor_config(client, "DSL RX Rate", "dslrxrate", "Mbps", "rate", "mdi:speedometer", serialnumber,
                                      macaddress, sw_version)
                publish_sensor_config(client, "DSL TX Rate", "dsltxrate", "Mbps", "rate", "mdi:speedometer", serialnumber,
                                      macaddress, sw_version)
                publish_sensor_config(client, "Communicating", "communicating", "", "status", "mdi:lan", serialnumber,
                                      macaddress, sw_version, "binary_sensor", False)
                publish_sensor_config(client, "DSL Online", "dslstatus", "", "status", "mdi:lan",
                                      serialnumber,
                                      macaddress, sw_version, "binary_sensor")
                publish_sensor_config(client, "Line 1 Online", "l1status", "", "status", "mdi:lan",
                                      serialnumber,
                                      macaddress, sw_version, "binary_sensor")
                publish_sensor_config(client, "Line 2 Online", "l2status", "", "status", "mdi:lan",
                                      serialnumber,
                                      macaddress, sw_version, "binary_sensor")

        knownserial = serialnumber

        client.will_set("modems/" + knownserial + "/communicating", False, qos=1, retain=True)
        client.publish("modems/" + knownserial + "/communicating", True, qos=1)

        if (hamode):
            client.will_set("homeassistant/binary_sensor/modem_" + serialnumber + "_communicating/state", "OFF", qos=1, retain=True)
            client.publish("homeassistant/binary_sensor/modem_" + serialnumber + "_communicating/state", "ON", qos=1, retain=True)

        client.publish("modems/" + knownserial + "/lines/1/rx-rate", line1download)
        if (hamode):
            client.publish("homeassistant/sensor/modem_" + serialnumber + "_l1rxrate/state", line1download, retain=True)

        client.publish("modems/" + knownserial + "/lines/1/tx-rate", line1upload)
        if (hamode):
            client.publish("homeassistant/sensor/modem_" + serialnumber + "_l1txrate/state", line1upload, retain=True)

        if (line1status == "Up"):
            client.publish("modems/" + knownserial + "/lines/1/online", True)
            if (hamode):
                client.publish("homeassistant/binary_sensor/modem_" + serialnumber + "_l1status/state", "ON",
                               retain=True)
        else:
            client.publish("modems/" + knownserial + "/lines/1/online", False)
            if (hamode):
                client.publish("homeassistant/binary_sensor/modem_" + serialnumber + "_l1status/state", "OFF",
                               retain=True)

        client.publish("modems/" + knownserial + "/lines/2/rx-rate", line2download)
        if (hamode):
            client.publish("homeassistant/sensor/modem_" + serialnumber + "_l2rxrate/state", line2download,
                           retain=True)

        client.publish("modems/" + knownserial + "/lines/2/tx-rate", line1upload)
        if (hamode):
            client.publish("homeassistant/sensor/modem_" + serialnumber + "_l2txrate/state", line2upload,
                           retain=True)

        if (line2status == "Up"):
            client.publish("modems/" + knownserial + "/lines/2/online", True)
            if (hamode):
                client.publish("homeassistant/binary_sensor/modem_" + serialnumber + "_l2status/state", "ON",
                               retain=True)
        else:
            client.publish("modems/" + knownserial + "/lines/2/online", False)
            if (hamode):
                client.publish("homeassistant/binary_sensor/modem_" + serialnumber + "_l2status/state", "OFF",
                               retain=True)

        client.publish("modems/" + knownserial + "/dsl/rx-rate", totaldownload)
        if (hamode):
            client.publish("homeassistant/sensor/modem_" + serialnumber + "_dslrxrate/state", totaldownload,
                           retain=True)

        client.publish("modems/" + knownserial + "/dsl/tx-rate", totalupload)
        if (hamode):
            client.publish("homeassistant/sensor/modem_" + serialnumber + "_dsltxrate/state", totalupload,
                           retain=True)

        if (dslstatus == "Up"):
            client.publish("modems/" + knownserial + "/dsl/online", True)
            if (hamode):
                client.publish("homeassistant/binary_sensor/modem_" + serialnumber + "_dslstatus/state", "ON",
                               retain=True)
        else:
            client.publish("modems/" + knownserial + "/dsl/online", False)
            if (hamode):
                client.publish("homeassistant/binary_sensor/modem_" + serialnumber + "_dslstatus/state", "OFF",
                               retain=True)

        print("Polled modem with serial number " + str(serialnumber))
        print("Line 1 is " + line1status + " (Speed " + str(line1download) + "/" + str(line1upload) + ")")
        print("Line 2 is " + line2status + " (Speed " + str(line2download) + "/" + str(line2upload) + ")")
        print("DSL is " + dslstatus + " (Total Speed " + str(totaldownload) + "/" + str(totalupload) + ")")
    except Exception as ex:
        print("Data conversion error")
        print(ex)