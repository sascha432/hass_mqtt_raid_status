# Changelog

## 0.0.3

 - Removed redundant `last_update` topic
 - Added systemd service script
 - Config option how to execute the mdadm binary
 - Raid device and mount point can be configured separately
 - Support for multiple raid devices
 - Last will to show if the script is not running anymore
 - Rewritten in python

## 0.0.2

 - Added option for mount point
 - Added option to select disk space unit
 - Limited df to a single line per device to avoid displaying subvolumes
 - Added total, free, used and used space in percent
 - Template example with state and last updated time
 - Removed topic prefix from object_id
 - Added last update timestamp
 - Debug options to display CLI commands and MQTT messages

## 0.0.1

- Initial commit

