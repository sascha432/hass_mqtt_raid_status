# MQTT linux raid monitoring with Home Assistant auto configuration

Simple bash script to monitor the raid status provided by mdadm with home assistant auto configuration

## Sensors

 - Raid status
 - Last update timestamp
 - Total disk space
 - Free disk space
 - Used disk space
 - Used disk space in percent

## Requirements

- mdadm
- mosquitto_pub
- df
- sed
- cut

Binaries must be in PATH

### Optional for Debugging

Use --debug to display MQTT config and topic values

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

The device can be found under Configuration / Devices ([http://homeassistant.local:8123/config/devices/dashboard](http://homeassistant.local:8123/config/devices/dashboard))

![Devices](https://raw.githubusercontent.com/sascha432/hass_mqtt_raid_status/master/device.png)

### Template with state and last update time

Replace `acidpi4_raid1_md0_*` with your entity ids

```ninja
{{ states.sensor.acidpi4_raid1_md0_state.state }}
{{ relative_time(states.sensor.acidpi4_raid1_md0_last_update.last_updated) }} ago
```

Output:

```txt
Clean
3 minutes ago
```

## Automation Alarm

To trigger any alarm if the raid fails, you can add an automation if the state of the sensor changes from `Clean` or `Active` to another state

### Other States Observed

- Degraded mirrored raid during rebuild `Clean,degraded,recovering`
- Degraded mirrored raid with missing drive `Clean,degraded`
