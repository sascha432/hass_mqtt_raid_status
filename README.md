# MQTT linux raid monitoring with Home Assistant auto configuration

Python script to monitor the raid status provided by mdadm with home assistant auto configuration

## Sensors

 - Raid status
 - Last update timestamp
 - Total disk space (default in GB, can be configured)
 - Free disk space
 - Used disk space
 - Used disk space in percent

 ![Sensors](https://raw.githubusercontent.com/sascha432/hass_mqtt_raid_status/master/sensors.png)
 ![Stats](https://raw.githubusercontent.com/sascha432/hass_mqtt_raid_status/master/stats.png)

## Requirements

- python 3.9 (other versions might work)
- paho-mqtt
- psutil
- mdadm (binary must be in PATH)

Python requirements can be installed with `pip3 install -r requirements.txt`

## TODOs

 - Add systemd service with auto restart on failure
 - Run mdadm with sudo
 - Better error/exception handling
 - Auto restart on disconnect

### Debugging

Use `--verbose` to display MQTT config and topic values

## Configuration

Edit `config.json` to change or add your device name and raid devices

## Installation

Execute `check-raid.py` as `root`. `mdadm` requires root privileges to be executed. 

## Home Assistant Integration

The device can be found under Configuration / Devices ([http://homeassistant.local:8123/config/devices/dashboard](http://homeassistant.local:8123/config/devices/dashboard))

![Devices](https://raw.githubusercontent.com/sascha432/hass_mqtt_raid_status/master/device.png)

## Automated Alarm

To trigger any alarm if the raid fails, you can add an automation if the state of the sensor changes from `Clean` or `Active` to another state

### Other States Observed

- Degraded mirrored raid during rebuild `Clean,degraded,recovering`
- Degraded mirrored raid with missing drive `Clean,degraded`
