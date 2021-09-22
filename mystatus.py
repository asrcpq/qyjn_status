#!/usr/bin/env python3

import datetime
import glob
import json
import netifaces
import os
import re
import signal
import socket
import sys
import threading
from netaddr import IPAddress
from time import sleep

sleep_time = 1
mystatus = dict()
dirty_flag = False
comma_flag = False
dirty_up_thresh = 100_000
dirty_down_thresh = 10_000
disk_dict = dict()

load_color = '#FFAF00'
bad_color = '#FF00AF'

cpu_usage1 = 0
cpu_usage2 = 0
def module_cpufreq():
	global cpu_usage1, cpu_usage2
	try:
		with open('/proc/cpuinfo', 'r') as f:
			sum_freq=0
			sum_core=0
			for line in f:
				if "MHz" in line:
					sum_freq += float(re.search(r'[0-9]*\.[0-9]*', line).group())
					sum_core += 1
			avg_freq = int(sum_freq / sum_core)
		with open('/proc/stat', 'r') as f:
			t = [int(i) for i in f.readline().split()[1:]]
			new1 = t[0] + t[2]
			new2 = new1 + t[3]
			usage_percent = (new1 - cpu_usage1) * 100 // (new2 - cpu_usage2)
			cpu_usage1 = new1
			cpu_usage2 = new2
		result = {"full_text": "C:" + str(avg_freq) + " " + str(usage_percent) + "%"}
		if usage_percent > 50:
			result['color'] = load_color
		mystatus['cpufreq'] = result
	except FileNotFoundError:
		mystatus.pop('cpufreq', None)
		pass
	timer = threading.Timer(3.0, module_cpufreq, None)
	timer.start()

def module_temp():
	fn_list = glob.glob('/sys/class/hwmon/hwmon*/temp*_input')
	if len(fn_list) == 0:
		return
	temp = -274
	try:
		for filename in fn_list:
			with open(filename) as f:
				new_data = int(f.readline()) // 1000
				if new_data > temp:
					temp = new_data
		result = {"full_text": "T:" + str(temp)}
		if temp > 85:
			result['color'] = bad_color
		mystatus['temp'] = result
	except OSError:
		mystatus.pop('temp', None)
		pass
	timer = threading.Timer(3.0, module_temp, None)
	timer.start()

def module_memory():
	global dirty_flag
	try:
		with open('/proc/meminfo', 'r') as f:
			meminfo = f.read()
		total = int(re.search(r'^MemTotal:\s+(\d+)', meminfo, flags = re.M).groups()[0])
		free = int(re.search(r'^MemFree:\s+(\d+)', meminfo, flags = re.M).groups()[0])
		avail = int(re.search(r'^MemAvailable:\s+(\d+)', meminfo, flags = re.M).groups()[0])
		dirty = int(re.search(r'^Dirty:\s+(\d+)', meminfo, flags = re.M).groups()[0])
		f_per = free * 100 // total
		a_per = avail * 100 // total
		result = {}
		full_text = 'M:' + str(f_per) + '/' + str(a_per)
		if dirty_flag:
			full_text += '-' + str(dirty // 1000)
			if dirty < dirty_down_thresh:
				dirty_flag = False
		if dirty > dirty_up_thresh:
			result['color'] = load_color
			dirty_flag = True
		if a_per < 15:
			result['color'] = bad_color
		result = {'full_text': full_text}
		mystatus['memory'] = result
	except FileNotFoundError:
		mystatus.pop('memory', None)
		pass
	timer = threading.Timer(3.0, module_memory, None)
	timer.start()

def module_busydisk():
	global disk_dict
	new_disk_dict = {}
	busy_thresh = 0.1 # SSD should have low threshold value
	busy_string = ""
	for filename in os.listdir('/sys/block'):
		try:
			with open('/sys/block/' + filename + '/stat', 'r') as f:
				new_value = int(f.readline().split()[9])
				if filename in disk_dict.keys():
					old_value = disk_dict[filename]
					if new_value - old_value > sleep_time * 1000 * busy_thresh:
						busy_string += filename + ' '
				new_disk_dict[filename] = new_value
		except:
			pass
	if busy_string:
		mystatus['busydisk'] = {
			'full_text': 'BD:' + busy_string[:-1],
			'color': load_color,
		}
	else:
		mystatus.pop('busydisk', None)
	disk_dict = new_disk_dict
	timer = threading.Timer(3.0, module_busydisk, None)
	timer.start()

def get_ip_address(ifname):
	data = netifaces.ifaddresses(ifname)[2][0]
	return data['addr'] + '/' + str(IPAddress(data['netmask']).netmask_bits())

def test_internet(host="1.1.1.1", port=53, timeout=1.0):
	try:
		socket.setdefaulttimeout(timeout)
		socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
		return True
	except socket.error as ex:
		return False

def module_default_gateway():
	try:
		with open('/proc/net/route', 'r') as f:
			route = f.read()
			default_nic_search = re.search(r'^([^\t]*)\t0{8}\t[^\t]*', route, flags = re.M)
			if not default_nic_search:
				return
			default_nic = default_nic_search.groups()[0]
			result = {"full_text": default_nic + ':' + get_ip_address(default_nic)}
			if not test_internet():
				result['color'] = bad_color
			mystatus['default_gateway'] = result
	except FileNotFoundError:
		mystatus.pop('default_gateway', None)
		pass
	timer = threading.Timer(10.0, module_default_gateway, None)
	timer.start()

def module_battery():
	try:
		with open('/sys/class/power_supply/BAT0/capacity', 'r') as f:
			line = f.readline()
			bat = int(line)
			result = {"full_text": "B:" + str(bat)}
			if bat < 10:
				result['color'] = bad_color
			mystatus['battery'] = result
	except FileNotFoundError:
		mystatus.pop('battery', None)
		pass
	timer = threading.Timer(10.0, module_battery, None)
	timer.start()

def module_date():
	now = datetime.datetime.now()
	date = now.strftime('%m-%d %H:%M:%S')
	result = {"full_text": date}
	mystatus['date'] = result
	timer = threading.Timer(1.0, module_date, None)
	timer.start()

def calc_module(name):
	globals().get('module_' + name)()

module_list = [
	'cpufreq',
	'temp',
	'memory',
	'busydisk',
	'default_gateway',
	'battery',
	'date',
]

def update_modules():
	for module in module_list:
		calc_module(module)

def flush_status():
	global comma_flag
	if comma_flag:
		print(',', end = "")
	else:
		comma_flag = True
	print(json.dumps(
		[mystatus[key] for key in module_list if key in mystatus.keys()],
		separators = (',', ':'),
	), flush = True)

def main_loop():
	while True:
		sleep(sleep_time)
		flush_status()

def main():
	print('{"version":1}')
	print('[')
	update_modules()
	flush_status()
	main_loop()

if __name__ == '__main__':
	main()
