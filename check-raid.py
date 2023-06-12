#!/usr/bin/env python3

import json
import socket
import subprocess
import hashlib
import copy
import paho.mqtt.client as mqtt
import time
import psutil
import argparse
import os
import atexit

parser = argparse.ArgumentParser(description="Check Raid Utility")
parser.add_argument("-v", "--verbose", help="verbose output", action="store_true", default=False)
parser.add_argument("-i", "--interval", help="interval to update the raid status in seconds", type=int, default=900)

args = parser.parse_args()

VERBOSE = args.verbose
interval = max(60, int(args.interval))

def verbose(msg):
    if VERBOSE:
        print(msg)

def error(msg, e):
    print(msg)
    if e:
        print('Exception: ' % e)
    exit(1)

config_file = os.path.abspath('config.json')
try:
    with open(config_file) as file:
        config = json.loads(file.read())

    device_name_base = config['sys']['device_name']
    if device_name_base=='$HOSTNAME':
        device_name_base = socket.gethostname()
except Exception as e:
    error('Failed to read configuration: %s' % config_file, e)

res = subprocess.run(config['sys']['mdadm_bin'] + ['-V'], capture_output=True)
mdadm_version = res.stderr.decode().strip()

res = subprocess.run(['uname', '-r', '-o', '-s', '-m'], capture_output=True)
os_version = res.stdout.decode().strip()

client = None
try:
    client = mqtt.Client(client_id='', clean_session=True, userdata=None, protocol=mqtt.MQTTv311, transport=config['mqtt']['transport'])
    client.connect(config['mqtt']['host'], port=int(config['mqtt']['port']), keepalive=60, bind_address='')
except Exception as e:
    error('Failed to connect to MQTT: %s:%d' % (config['mqtt']['host'], int(config['mqtt']['port'])), e)

def disconnect_mqtt():
    client.publish(topics['avty_t'], payload=OFFLINE, qos=int(config['mqtt']['qos']), retain=True)
    time.sleep(1)
    client.disconnect()

atexit.register(disconnect_mqtt)

# homeassistant config
extra_info = {
    "model": "mdadm",
    "sw_version": mdadm_version,
    "manufacturer": os_version
}

ONLINE = '1'
OFFLINE = '0'

topics = {
    "avty_t": None,
    "pl_avail": ONLINE,
    "pl_not_avail": OFFLINE,
    "stat_t": None
}

device_info = {
    "dev": {
        "identifiers": None,
        "name": None,
        "model": "mdadm",
        "sw_version": mdadm_version,
        "manufacturer": os_version
    }
}

number = 42
for device in config['devices']:
    verbose('------------------------------------')

    unit = device['display_unit'].upper()
    if unit=='B':
        multiplier = 1
    elif unit=='KB':
        multiplier = 1024
    elif unit=='MB':
        multiplier = 1024 << 10
    elif unit=='GB':
        multiplier = 1024 << 20
    elif unit=='TB':
        multiplier = 1024 << 30
    else:
        unit = 'GB'
        multiplier = 1024 << 20
    multiplier = 1 / multiplier

    # get unique id from the device block id
    res = subprocess.run(['blkid', '-o', 'value', device['raid_device']], capture_output=True)
    unique_id = hashlib.sha256(res.stdout).hexdigest()[:12]

    raid_state = None
    raid_level = None
    raid_device = device['raid_device'].split('/').pop()

    args = config['sys']['mdadm_bin'] + ['--misc', '--detail', device['raid_device']]
    res = subprocess.run(args, capture_output=True)
    if res.returncode:
        error('Error executing %d: %s' % (res.returncode, ' '.join(args)), None)
    for line in res.stdout.decode().split('\n'):
        args = line.strip().split(':', maxsplit=2)
        if len(args)==2:
            name = args[0].strip()
            value = args[1].strip()
            key = name.lower().replace(' ', '_')
            if key=='raid_level':
                raid_level = value.lower()
            elif key=='state':
                raid_state = value.capitalize()

    device_name = '%s %s %s' % (device_name_base.capitalize(), raid_level.capitalize(), device['raid_device'])
    unique_id_dev = unique_id + ('%02x' % number)

    topics['avty_t'] = '%s/%s_%s_%s/status' % (config['hass']['base_topic'], device_name_base, raid_level, raid_device)
    topics['stat_t'] = '%s/%s_%s_%s/state' % (config['hass']['base_topic'], device_name_base, raid_level, raid_device)

    device_info['dev']['identifiers'] = [ '%s_%s_%s_%s' % (device_name_base, raid_level, raid_device, unique_id_dev) ]
    device_info['dev']['name'] = '%s_%s_dev_%s' % (device_name_base, raid_level, raid_device)
    
    object_id = '%s_%s_%s' % (device_name_base, raid_level, raid_device)

    # state config
    state = {
        "name": device_name,
        "platform": "mqtt",
        "uniq_id": unique_id_dev,
        "obj_id": object_id + '_state',
        "icon": "mdi:harddisk"
    }
    state.update(topics)
    state.update(extra_info)
    state.update(device_info)
    
    # total space
    number += 23
    total_space = copy.deepcopy(state)
    total_space['name'] += ' Total'
    total_space['obj_id'] = object_id + '_total'
    total_space['uniq_id'] = unique_id + ('%02x' % number)
    total_space['stat_t'] = '%s/%s_%s_%s/total' % (config['hass']['base_topic'], device_name_base, raid_level, raid_device)
    total_space['unit_of_measurement'] = unit

    # free space
    number += 23
    free_space = copy.deepcopy(state)
    free_space['name'] += ' Free'
    free_space['obj_id'] = object_id + '_free'
    free_space['uniq_id'] = unique_id + ('%02x' % number)
    free_space['stat_t'] = '%s/%s_%s_%s/free' % (config['hass']['base_topic'], device_name_base, raid_level, raid_device)
    free_space['unit_of_measurement'] = unit

    # used space percentage
    number += 23
    free_pct_space = copy.deepcopy(state)
    free_pct_space['name'] += ' Total Pct'
    free_pct_space['obj_id'] = object_id + '_free_pct'
    free_pct_space['uniq_id'] = unique_id + ('%02x' % number)
    free_pct_space['stat_t'] = '%s/%s_%s_%s/free_pct' % (config['hass']['base_topic'], device_name_base, raid_level, raid_device)
    free_pct_space['unit_of_measurement'] = '%'

    # used space
    number += 23
    used_space = copy.deepcopy(state)
    used_space['name'] += ' Used'
    used_space['obj_id'] = object_id + '_used'
    used_space['uniq_id'] = unique_id + ('%02x' % number)
    used_space['stat_t'] = '%s/%s_%s_%s/used' % (config['hass']['base_topic'], device_name_base, raid_level, raid_device)
    used_space['unit_of_measurement'] = unit

    # send homeassistant config
    verbose('state: %s\ndevice: %s\nraid device: %s\ndisplay unit: %s' % (raid_state, device_name_base, device['raid_device'], unit))

    topic = '%s/sensor/%s/state/config' % (config['hass']['autoconf_topic'], object_id)
    verbose('---\ntopic: %s\nconfig: %s' % (topic, json.dumps(state)))
    client.publish(topic, payload=json.dumps(state), qos=int(config['mqtt']['qos']), retain=True)

    topic = '%s/sensor/%s/total_space/config' % (config['hass']['autoconf_topic'], object_id)
    verbose('---\ntopic: %s\nconfig: %s' % (topic, json.dumps(total_space)))
    client.publish(topic, payload=json.dumps(total_space), qos=int(config['mqtt']['qos']), retain=True)
    
    topic = '%s/sensor/%s/free_space/config' % (config['hass']['autoconf_topic'], object_id)
    verbose('---\ntopic: %s\nconfig: %s' % (topic, json.dumps(free_space)))
    client.publish(topic, payload=json.dumps(free_space), qos=int(config['mqtt']['qos']), retain=True)
    
    topic = '%s/sensor/%s/free_pct_space/config' % (config['hass']['autoconf_topic'], object_id)
    verbose('---\ntopic: %s\nconfig: %s' % (topic, json.dumps(free_pct_space)))
    client.publish(topic, payload=json.dumps(free_pct_space), qos=int(config['mqtt']['qos']), retain=True)
    
    topic = '%s/sensor/%s/used_space/config' % (config['hass']['autoconf_topic'], object_id)
    verbose('---\ntopic: %s\nconfig: %s' % (topic, json.dumps(used_space)))
    client.publish(topic, payload=json.dumps(used_space), qos=int(config['mqtt']['qos']), retain=True)

    # set online status and last will
    client.publish(topics['avty_t'], payload=ONLINE, qos=int(config['mqtt']['qos']), retain=True)
    client.will_set(topics['avty_t'], payload=OFFLINE, qos=int(config['mqtt']['qos']), retain=True)

client.loop_start()

# send raid status

display_decimal_places = max(min(int(device['display_decimal_places']), 4), 0) # allow 0-4 decimal places

while True:
    try:
        for device in config['devices']:

            raid_state = 'N/A'
            
            
            args = config['sys']['mdadm_bin'] + ['--misc', '--detail', device['raid_device']]
            res = subprocess.run(args, capture_output=True)
            if res.returncode:
                error('Error executing %d: %s' % (res.returncode, ' '.join(args)), None)
            for line in res.stdout.decode().split('\n'):
                args = line.strip().split(':', maxsplit=2)
                if len(args)==2:
                    name = args[0].strip()
                    value = args[1].strip()
                    key = name.lower().replace(' ', '_')
                    if key=='state':
                        raid_state = value.capitalize()
                        break

            result = psutil.disk_usage(device['mount_point'])

            verbose('---\ntopic: %s\message: %s' % (state['stat_t'], raid_state))
            client.publish(state['stat_t'], payload=raid_state, qos=int(config['mqtt']['qos']), retain=True)

            total_space_str = ('%%.%df' % display_decimal_places) % (result.total * multiplier)
            verbose('---\ntopic: %s\message: %s' % (total_space['stat_t'], total_space_str))
            client.publish(total_space['stat_t'], payload=total_space_str, qos=int(config['mqtt']['qos']), retain=True)

            used_space_str = ('%%.%df' % display_decimal_places) % (result.used * multiplier)
            verbose('---\ntopic: %s\message: %s' % (used_space['stat_t'], used_space_str))
            client.publish(used_space['stat_t'], payload=used_space_str, qos=int(config['mqtt']['qos']), retain=True)

            free_space_str = ('%%.%df' % display_decimal_places) % (result.free * multiplier)
            verbose('---\ntopic: %s\message: %s' % (free_space['stat_t'], free_space_str))
            client.publish(free_space['stat_t'], payload=free_space_str, qos=int(config['mqtt']['qos']), retain=True)

            free_pct_space_str = ('%.1f' % (100.0 - result.percent))
            verbose('---\ntopic: %s\message: %s' % (free_pct_space['stat_t'], free_pct_space_str))
            client.publish(free_pct_space['stat_t'], payload=free_pct_space_str, qos=int(config['mqtt']['qos']), retain=True)

    except Exception as e:
        error('An error occurred during publishing the information', e)

    verbose('---\nwaiting %d seconds....' % interval)
    time.sleep(interval)
