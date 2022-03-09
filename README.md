# MQTT linux raid monitoring with Home Assistant auto configuration

Simple bash script to monitor the raid status provided by mdadm with home assistant auto configuration

## Requirements

- mdadm
- mosquitto_pub

Binaries must be in PATH

### Optional for Debugging

 - mosquitto_sub
 - jq

## Configuration

Edit `config` to change your device name and the raid device

### Multiple Devices

Currently only one device is supported. To monitor multiple devices just create a copy of `config` and `check-raid` in different directories

## Installation

Run as `root` from /etc/cron.hourly to get hourly updates. `mdadm` requires root privileges to be executed

Alternatively run it from `/etc/crontab` every 15min or the desired interval

```bash
*/15 *  * * *   root    <DIR>/check-raid
```

## Home Assistant Integration

The device can be found under Configuration / Devices (`http://YOURDOMAIN:8123/config/devices/dashboard`)

![Devices](https://raw.githubusercontent.com/sascha432/hass_mqtt_raid_status/master/device.png)

## Automation Alarm

To trigger any alarm if the raid fails, you can add an automation if the state of the sensor changes from `Clean` or `Active` to another state. Other states might be `Degraded`, `Resync`, `Rebuild`, ... Check the mdadm man page for more details

