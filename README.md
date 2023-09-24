# MQTT linux raid monitoring with Home Assistant auto configuration

Python script to monitor the raid status provided by mdadm with home assistant auto configuration

## Changelog

  - Rewritten connection handler (last will, online status)
  - Pass configuration file as argument
  - Added MQTT username and password
  - Default configuration built-in
  - Updated systemd script

## Sensors

 - Raid status
 - Last update timestamp
 - Total disk space (default in GB, can be configured)
 - Free disk space
 - Free disk space in percent
 - Used disk space
 
 ![Sensors](https://raw.githubusercontent.com/sascha432/hass_mqtt_raid_status/master/sensors.png)
 ![Stats](https://raw.githubusercontent.com/sascha432/hass_mqtt_raid_status/master/stats.png)

## Requirements

- python 3.9 (other versions might work)
- paho-mqtt
- psutil
- mdadm, blkid, uname

Python requirements can be installed with `pip3 install -r requirements.txt`

## Configuration

Edit `config.json` to change or add your device name and raid devices

### Testing the Configuration

Execute `check-raid.py -v` as `root`. `mdadm` requires root privileges to be executed.

### Installation as Service

Copy `hass_raid_status.service` to your systemd directory, modify the location of the python script and add any required services (for example mosquitto as dependency)

Enable, start and check the service with
EEE
``` sh
systemctl enable hass_raid_status.service
systemctl start hass_raid_status.service
systemctl status hass_raid_status.service

● hass_raid_status.service - Raid status for Home Assistant
     Loaded: loaded (/etc/systemd/system/hass_raid_status.service; enabled; vendor preset: enabled)
     Active: active (running) since Fri 2023-02-17 04:19:54 PST; 27ms ago
   Main PID: 14967 (python3)
      Tasks: 1 (limit: 4915)
        CPU: 14ms
     CGroup: /system.slice/hass_raid_status.service
             └─14967 python3 /root/hass_mqtt_raid_status/check-raid.py

```

## Home Assistant Integration

The device can be found under Configuration / Devices ([http://homeassistant.local:8123/config/devices/dashboard](http://homeassistant.local:8123/config/devices/dashboard))

![Devices](https://raw.githubusercontent.com/sascha432/hass_mqtt_raid_status/master/device.png)
![Entities](https://raw.githubusercontent.com/sascha432/hass_mqtt_raid_status/master/entities.png)

## Automated Alarm

To trigger any alarm if the raid fails, you can add an automation if the state of the sensor changes from `Clean` or `Active` to another state

### Other States Observed

- Degraded mirrored raid during rebuild `Clean,degraded,recovering`
- Degraded mirrored raid with missing drive `Clean,degraded`
