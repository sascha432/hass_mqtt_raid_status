# MQTT linux raid monitoring with Home Assistant auto configuration

Simple bash script to monitor the raid status provided by mdadm with home assistant auto configuration

## Requirements

- mdadm
- mosquitto_pub

Binaries must be in PATH

## Configuration

Edit `config` to change your device name and the raid device

### Multiple Devices

Currently only one device is supported. To monitor multiple devices just create a copy of `config` and `check-raid` in different directories

## Installation

Run as `root` from /etc/cron.hourly to get hourly updates. `mdadm` requires root privileges to be executed

## Home Assistant Integration

The device can be found under Configuration / Devices (`http://YOURDOMAIN:8123/config/devices/dashboard`)

The entity name is `sensor.acidpi4_raid1_dev_md0`. After modifying the configuration, the name, raid level and device will change

![Devices](https://raw.githubusercontent.com/sascha432/hass_mqtt_raid_status/master/device.png)

## Automation Alarm

To trigger any alarm if the raid fails, you can add an automation if the state of the sensor changes from `Clean` to another state

