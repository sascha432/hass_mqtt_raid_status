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
import sys
import atexit
import shutil

parser = argparse.ArgumentParser(description="Check Raid Utility")
parser.add_argument("-v", "--verbose", help="verbose output", action="store_true", default=False)
parser.add_argument("-c", "--config", help="configuration file", default="config.json")
parser.add_argument("-i", "--interval", help="interval to update the raid status in seconds", type=int, default=900)
parser.add_argument("-p", "--print", help="print configuration and exit", action="store_true", default=False)

args = parser.parse_args()

def verbose(msg):
    if args.verbose:
        print(msg)

def error(msg, e=None):
    print(msg, file=sys.stderr)
    if e:
        print('Exception: %s' % e, file=sys.stderr)
    exit(1)

def has_mqtt_username(username):
    return username!=None and username!=''

def get_mqtt_username(username):
    if has_mqtt_username(username):
        return username
    return 'Anonymous'

def get_mqtt_password(password):
    if isinstance(password, str):
        return len(password) * '*'
    return '<None>'

def get_mqtt_account(config):
    if has_mqtt_username(config['username']):
        return '%s:%s' % (config['username'], get_mqtt_password(config['password']))
    return 'Anonymous'

device_name = None
state = {
    'connected': False,
    'current_delay': None,
    'resend_online_status': False
}
client = None
config_file = os.path.abspath(args.config);
config = {
    'sys': {},
    'hass': {},
    'mqtt': {},
    'devices': None,
    'info': {}
}
try:
    with open(config_file) as file:
        config = dict(config | json.loads(file.read()))
except Exception as e:
    error('Failed to read configuration: %s' % config_file, e)

# get mdadm command line args
def mdadm_cmd(args):
    if config['sys']['sudo']:
        return [config['sys']['sudo'], config['sys']['mdadm_bin']] + args
    else:
        return [config['sys']['mdadm_bin']] + args

# default config for devices
default_device_config = {
    'display_unit': 'TB',
    'display_decimal_places': 2
}

# default settings
config_defaults = {
    'sys': {
        'device_name': '$HOSTNAME',
        'mdadm_bin': 'mdadm',
        'sudo': False,
        'interval': args.interval
    },
    'hass': {
        'autoconf_topic': 'homeassistant',
        'base_topic': 'home',
        'availability_topic': '${base_topic}/${device_name}-check-raid/status'
    },
    'mqtt': {
        'host': None,
        'port': 1883,
        'qos': 2,
        'keepalive': 60,
        'version': mqtt.MQTTv311,
        'transport': 'tcp',
        'username': None,
        'password': None,
        'status': [ 'OFF', 'ON' ],
        'icon': 'mdi:harddisk'
    },
    'info': {
        'mdadm_version': None,
        'os_version': None
    }
};
# merge default settings per key
for (key, val) in config_defaults.items():
    if key not in config:
        config[key] = val
    else:
        config[key] = dict(val | config[key]);

# validate configuration
if 'default_config' in config:
    del config['default_config']

# resolve device name
if config['sys']['device_name']=='$HOSTNAME':
    config['sys']['device_name'] = socket.gethostname()
device_name = config['sys']['device_name']

# check if any devices have been configured
if not isinstance(config['devices'], list) or len(config['devices'])==0:
    error('No devices configured')

# apply config defaults per device and normalize values
idx = 0
for device in config['devices']:
    tmp = dict(default_device_config | device)
    if not 'raid_device' in tmp:
        raise Exception('raid_device missing for device #%u' % idx)
    if not 'mount_point' in tmp:
        raise Exception('mount_point missing for device #%u' % idx)
    try:
        psutil.disk_usage(tmp['mount_point'])
    except Exception as e:
        error('Cannot find mount point: %s' % tmp['mount_point'], e)
    unit = tmp['display_unit'].upper()
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
        raise Exception('Invalid unit %s for device %s' % (unit, tmp['raid_device']))
    multiplier = 1 / multiplier
    tmp['display_unit'] = unit
    tmp['multiplier'] = multiplier
    tmp['display_decimal_places'] = max(min(int(tmp['display_decimal_places']), 4), 0) # allow 0-4 decimal places
    tmp['num'] = idx
    config['devices'][idx] = tmp
    idx += 1

# normalize qos
qos = int(config['mqtt']['qos'])
if not qos in(0, 1, 2):
    error('Invalid QoS value: %d' % qos)
config['mqtt']['qos'] = qos

# replace variables
s = config['hass']['availability_topic'];
s = s.replace('${base_topic}', config['hass']['base_topic'])
s = s.replace('${device_name}', config['sys']['device_name'])
config['hass']['availability_topic'] = s

# keepalive 5-3600 seconds
config['mqtt']['keepalive'] = min(3600, max(5, int(config['mqtt']['keepalive'])))

# normalize port
config['mqtt']['port'] = int(config['mqtt']['port'])

# update interval
config['sys']['interval'] = max(30, int(config['sys']['interval']))

# find binary if no absolute path was given
if not os.path.isabs(config['sys']['mdadm_bin']):
    config['sys']['mdadm_bin'] = shutil.which(config['sys']['mdadm_bin'])

if config['sys']['sudo']:
    config['sys']['sudo'] = shutil.which('sudo')

# mdadm version
res = subprocess.run(mdadm_cmd(['-V']), capture_output=True)
mdadm_version = res.stderr.decode().strip()
config['info']['mdadm_version'] = mdadm_version

# os version
res = subprocess.run(['uname', '-r', '-o', '-s', '-m'], capture_output=True)
os_version = res.stdout.decode().strip()
config['info']['os_version'] = os_version

# print config and exit
if args.print:
    print('Configuration:')
    try:
        import pprint
        pprint.pprint(config, indent=1, sort_dicts=False)
    except:
        print(config)
    exit(0)

# config helpers
def get_online_status():
    return config['mqtt']['status'][1]

def get_offline_status():
    return config['mqtt']['status'][0]

def get_qos_value():
    return config['mqtt']['qos']

# home assistant config
extra_info = {
    "model": "mdadm",
    "sw_version": mdadm_version,
    "manufacturer": os_version
}
topics = {
    "avty_t": None,
    "pl_avail": get_online_status(),
    "pl_not_avail": get_offline_status(),
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

def publish_online(client):
    verbose('sending online status')
    client.publish(config['hass']['availability_topic'], payload=get_online_status(), qos=2, retain=True)

def publish_offline(client):
    verbose('sending offline status')
    client.publish(config['hass']['availability_topic'], payload=get_offline_status(), qos=2, retain=True)

# returns True, False or None for connection terminated
def is_connected():
    return state['connected']

def set_connected(connected):
    state['connected'] = connected

def reset_main_loop_delay(delay = 2):
    if delay<=0:
        delay = None
    if delay==state['current_delay']:
        return
    verbose('reset main delay')
    state['current_delay'] = delay

def set_resend_online_status(resend):
    state['resend_online_status'] = resend

# set connection online
def on_connect(client, userdata, flags, rc, *args):
    if is_connected()==None:
        verbose('client terminated')
        return
    if rc!=0:
        verbose('bad connection rc=%s' % str(rc))
        set_connected(False)
        return
    if is_connected()==False:
        set_connected(True)
        set_resend_online_status(False)
        # subscribe to availability topic
        client.subscribe(config['hass']['availability_topic'], qos=2)
        publish_online(client)
        reset_main_loop_delay()
    else:
        raise Exception('Invalid connection state')

# set connection offline
def on_disconnect(client, userdata, rc, *args):
    if is_connected():
        set_connected(False)
        if rc==0:
            try:
                publish_offline(client)
            except Exception as e:
                verbose('Exception: %s' % e)

# update online status on connection failures
def on_message(client, userdata, message, *args):
    if is_connected():
        if message.topic==config['hass']['availability_topic']:
            payload = message.payload.decode('utf-8')
            if payload==get_online_status():
                set_resend_online_status(False)
            else:
                set_resend_online_status(True)
                reset_main_loop_delay()

# at exit, set device offline
def disconnect_mqtt():
    flag = is_connected()
    set_connected(None) # mark as terminated
    if flag:
        publish_offline(client)
        time.sleep(1)
        client.disconnect()
        client.loop_stop(True)

# publish message
def publish(client, topic, payload):
    verbose('topic: %s\nmessage: %s' % (topic, payload))
    client.publish(topic, payload=payload, qos=get_qos_value(), retain=True)

# publish config
def publish_config(client, topic, payload, object_id):
    if not isinstance(payload, dict):
        raise Exception('Invalid config payload topic: %s' % topic)
    topic = '%s/sensor/%s/%s/config' % (config['hass']['autoconf_topic'], object_id, topic)
    publish(client, topic, json.dumps(payload))

# connect to MQTT server
try:
    # configure client
    version = int(config['mqtt']['version'])
    client = mqtt.Client(client_id=None, clean_session=version <= mqtt.MQTTv311 and True or None, userdata=None, protocol=version, transport=config['mqtt']['transport'], reconnect_on_failure=True)
    if has_mqtt_username(config['mqtt']['username']):
        verbose('setting username=%s password=%s' % (config['mqtt']['username'], get_mqtt_password(config['mqtt']['password'])))
        client.username_pw_set(config['mqtt']['username'], config['mqtt']['password'])

    # callbacks and exit routines
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    atexit.register(disconnect_mqtt)

    # last will in case the connection is aborted
    client.will_set(config['hass']['availability_topic'], payload=get_offline_status(), qos=2, retain=True)

    # connect client
    verbose('connecting to %s@%s:%d' % (get_mqtt_account(config['mqtt']), config['mqtt']['host'], config['mqtt']['port']))
    set_connected(False)
    client.connect(config['mqtt']['host'], port=config['mqtt']['port'], keepalive=config['mqtt']['keepalive'], bind_address='')

except Exception as e:
    error('Failed to connect to MQTT: %s@%s:%d' % (get_mqtt_account(config['mqtt']), config['mqtt']['host'], config['mqtt']['port']), e)


# start mqtt client loop
client.loop_start()

# generate autoconf
number = 42
for device in config['devices']:
    verbose('------------------------------------')

    # get unique id from the device block id
    res = subprocess.run(['blkid', '-o', 'value', device['raid_device']], capture_output=True)
    unique_id = hashlib.sha256(res.stdout).hexdigest()[:12]

    raid_state = None
    raid_level = None
    raid_device = device['raid_device'].split('/').pop()

    args = mdadm_cmd(['--misc', '--detail', device['raid_device']])
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

    display_device_name = '%s %s %s' % (device_name.capitalize(), raid_level.capitalize(), device['raid_device'])
    unique_id_dev = unique_id + ('%02x' % number)

    topics['avty_t'] = config['hass']['availability_topic']
    topics['stat_t'] = '%s/%s_%s_%s/state' % (config['hass']['base_topic'], device_name, raid_level, raid_device)

    device_info['dev']['identifiers'] = [ '%s_%s_%s_%s' % (device_name, raid_level, raid_device, unique_id_dev) ]
    device_info['dev']['name'] = '%s_%s_dev_%s' % (device_name, raid_level, raid_device)

    object_id = '%s_%s_%s' % (device_name, raid_level, raid_device)

    # state config / template for all
    device_state = {
        'name': display_device_name,
        'platform': 'mqtt',
        'uniq_id': unique_id_dev,
        'obj_id': object_id + '_state',
        'icon': config['mqtt']['icon']
    }
    device_state.update(topics)
    device_state.update(extra_info)
    device_state.update(device_info)

    # total space
    number += 23
    total_space = copy.deepcopy(device_state)
    total_space['name'] += ' Total Space'
    total_space['obj_id'] = object_id + '_total'
    total_space['uniq_id'] = unique_id + ('%02x' % number)
    total_space['stat_t'] = '%s/%s_%s_%s/total' % (config['hass']['base_topic'], device_name, raid_level, raid_device)
    total_space['unit_of_measurement'] = device['display_unit']

    # free space
    number += 23
    free_space = copy.deepcopy(device_state)
    free_space['name'] += ' Free Space'
    free_space['obj_id'] = object_id + '_free'
    free_space['uniq_id'] = unique_id + ('%02x' % number)
    free_space['stat_t'] = '%s/%s_%s_%s/free' % (config['hass']['base_topic'], device_name, raid_level, raid_device)
    free_space['unit_of_measurement'] = device['display_unit']

    # used space percentage
    number += 23
    free_pct_space = copy.deepcopy(device_state)
    free_pct_space['name'] += ' Free Space Pct'
    free_pct_space['obj_id'] = object_id + '_free_pct'
    free_pct_space['uniq_id'] = unique_id + ('%02x' % number)
    free_pct_space['stat_t'] = '%s/%s_%s_%s/free_pct' % (config['hass']['base_topic'], device_name, raid_level, raid_device)
    free_pct_space['unit_of_measurement'] = '%'

    # used space
    number += 23
    used_space = copy.deepcopy(device_state)
    used_space['name'] += ' Used Space'
    used_space['obj_id'] = object_id + '_used'
    used_space['uniq_id'] = unique_id + ('%02x' % number)
    used_space['stat_t'] = '%s/%s_%s_%s/used' % (config['hass']['base_topic'], device_name, raid_level, raid_device)
    used_space['unit_of_measurement'] = device['display_unit']

    # append State to name
    device_state['name'] = device_state['name'] + ' State'

    # send homeassistant config
    verbose('device %u\nstate: %s\ndevice: %s\nraid device: %s\nmount point: %s\ndisplay unit: %s' % (device['num'], raid_state, device_name, device['raid_device'], device['mount_point'], device['display_unit']))

    publish_config(client, 'state', device_state, object_id)
    publish_config(client, 'total_space', total_space, object_id)
    publish_config(client, 'free_space', free_space, object_id)
    publish_config(client, 'free_pct_space', free_pct_space, object_id)
    publish_config(client, 'used_space', used_space, object_id)

# update raid status
def main_loop(client):
    for device in config['devices']:
        raid_state = 'N/A'
        args = mdadm_cmd(['--misc', '--detail', device['raid_device']])
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

        verbose('---')
        publish(client, device_state['stat_t'], raid_state)
        publish(client, total_space['stat_t'], ('%%.%df' % device['display_decimal_places']) % (result.total * device['multiplier']))
        publish(client, used_space['stat_t'], ('%%.%df' % device['display_decimal_places']) % (result.used * device['multiplier']))
        publish(client, free_space['stat_t'], ('%%.%df' % device['display_decimal_places']) % (result.free * device['multiplier']))
        publish(client, free_pct_space['stat_t'], ('%.1f' % (100.0 - result.percent)))


# run indefinitely
while True:
    try:
        if is_connected():
            # check if we have to resend the online status
            if state['resend_online_status']:
                set_resend_online_status(False)
                publish_online(client)

            # publish raid state
            try:
                main_loop(client)
            except Exception as e:
                error('Main loop aborted', e)

            verbose('---\nwaiting %d seconds....' % config['sys']['interval'])
            state['current_delay'] = config['sys']['interval']
        else:
            state['current_delay'] = 1

        while state['current_delay']:
            time.sleep(1)
            try:
                state['current_delay'] -= 1 # TypeError if None
            except:
                break
    except KeyboardInterrupt:
        error('Aborted')
