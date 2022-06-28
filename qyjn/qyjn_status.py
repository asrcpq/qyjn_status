#!/usr/bin/env python3

import datetime
import json
import os
import re
import socket
import sys
import time
from glob import glob
from threading import Thread
from time import sleep

qyjn_status = dict()
dirty_flag = False
rtx_dict = dict()
comma_flag = False
dirty_up_thresh = 100_000
dirty_down_thresh = 10_000
disk_dict = dict()

load_color = '#00FFAF'
bad_color = '#FF00AF'

class qyjn_module():
	def __init__(self, caller):
		self.caller = caller
	def run(self):
		while True:
			sleeptime = self.caller()
			if sleeptime < 0:
				return
			sleep(sleeptime)

cpu_usage1 = 0
cpu_usage2 = 0
usage_percent = "-1"
def module_cpufreq():
	global cpu_usage1, cpu_usage2, usage_percent
	try:
		with open('/proc/cpuinfo', 'r') as f:
			max_freq = 0
			for line in f:
				if "MHz" in line:
					freq = float(re.search(r'[0-9]*\.[0-9]*', line).group())
					max_freq = max(max_freq, freq)
		with open('/proc/stat', 'r') as f:
			t = [int(i) for i in f.readline().split()[1:]]
			new1 = t[0] + t[1] + t[2]
			new2 = new1 + t[3]
			if new2 > cpu_usage2:
				usage_percent = (new1 - cpu_usage1) * 100 // (new2 - cpu_usage2)
				cpu_usage1 = new1
				cpu_usage2 = new2
		result = {"full_text": f"C:{max_freq:.0f} {usage_percent}%"}
		if usage_percent > 50:
			result['color'] = load_color
		qyjn_status['cpufreq'] = result
	except FileNotFoundError:
		qyjn_status.pop('cpufreq', None)
		pass
	return 3.0

def module_temp():
	fn_list = glob('/sys/class/hwmon/hwmon*/temp*_input')
	if len(fn_list) == 0:
		return -1
	temp = None
	for filename in fn_list:
		try:
			with open(filename) as f:
				new_data = int(f.readline()) // 1000
				if temp is None or new_data > temp:
					temp = new_data
		except OSError:
			pass
	if temp is not None:
		result = {"full_text": "T:" + str(temp)}
		if temp > 85:
			result['color'] = bad_color
		qyjn_status['temp'] = result
	else:
		qyjn_status.pop('temp', None)
	return 3.0

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
		qyjn_status['memory'] = result
	except FileNotFoundError:
		qyjn_status.pop('memory', None)
		pass
	return 3.0

def module_busydisk():
	global disk_dict
	new_disk_dict = {}
	busy_thresh = 0.1 # SSD should have low threshold value
	busy_string = ""
	sleep_time = 3.0
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
		qyjn_status['busydisk'] = {
			'full_text': 'BD:' + busy_string[:-1],
			'color': load_color,
		}
	else:
		qyjn_status.pop('busydisk', None)
	disk_dict = new_disk_dict
	return sleep_time

def module_busynic():
	global rtx_dict
	new_rtx_dict = {}
	sleep_time = 3.0
	busy_string = ""
	try:
		with open('/proc/net/dev') as f:
			f.readline();f.readline()
			line = f.readline()
			while line:
				sp = line.split()
				ifname = sp[0][:-1]
				rxbytes = int(sp[1])
				txbytes = int(sp[9])
				if ifname in rtx_dict:
					drx = rxbytes - rtx_dict[ifname][0]
					dtx = txbytes - rtx_dict[ifname][1]
					# 64KiB/s is busy
					if drx + dtx > 64000 * sleep_time:
						busy_string += ifname + " "
				new_rtx_dict[ifname] = [rxbytes, txbytes]
				line = f.readline()
			if busy_string:
				qyjn_status['busynic'] = {
					'full_text': 'BN:' + busy_string[:-1],
					'color': load_color,
				}
			else:
				qyjn_status.pop('busynic', None)
	except FileNotFoundError:
		pass
	rtx_dict = new_rtx_dict
	return sleep_time

def test_internet(host="one.one.one.one", port=53, timeout=1.0):
	try:
		socket.setdefaulttimeout(timeout)
		socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
		return True
	except socket.error as ex:
		return False

def module_default_gateway():
	sleep_time = 10.0
	try:
		with open('/proc/net/route', 'r') as f:
			route = f.read()
			default_nic_search = re.search(r'^([^\t]*)\t0{8}\t[^\t]*', route, flags = re.M)
			if not default_nic_search:
				return sleep_time
			default_nic = default_nic_search.groups()[0]
			result = {"full_text": default_nic}
			if not test_internet():
				result['color'] = bad_color
				sleep_time = 5.0
			qyjn_status['default_gateway'] = result
	except FileNotFoundError:
		qyjn_status.pop('default_gateway', None)
		pass
	return sleep_time

def module_battery():
	try:
		with open('/sys/class/power_supply/BAT0/capacity', 'r') as f:
			line = f.readline()
			bat = int(line)
			result = {"full_text": "B:" + str(bat)}
			if bat < 10:
				result['color'] = bad_color
			qyjn_status['battery'] = result
	except FileNotFoundError:
		qyjn_status.pop('battery', None)
		pass
	return 10

def module_eyecare():
	qyjn_status.pop('eyecare', None)
	try:
		with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
			s.connect(f"{os.environ['XDG_DATA_HOME']}/eyecare/eyecare.sock")
			s.settimeout(0.1)
			s.send("get score\n".encode())
			data = s.recv(1024).decode("utf-8")
	except Exception as e:
		print(e, file = sys.stderr)
		return 10
	data = int(data)
	result = {"full_text": f"E:{data // 60}"}
	if data > 1800:
		result['color'] = load_color
	if data > 3600:
		result['color'] = bad_color
	qyjn_status['eyecare'] = result
	return 10

def module_mail():
	qyjn_status.pop('mail', None)
	prefix = os.environ["HOME"] + "/xdg/mail/"
	data = []
	for mailbox in glob(prefix + "*/*"):
		if len(glob(mailbox + "/new/*")) > 0:
			if len(data) >= 2:
				data.append("+")
				break
			data.append(mailbox.lstrip(prefix))
	if len(data) > 0:
		result = {"full_text": "I:" + " ".join(data)}
		result['color'] = load_color
		qyjn_status['mail'] = result
	return 30

# placeholder
# the real date implementation is in main_loop
def module_date():
	return -1

module_list = [
	'cpufreq',
	'temp',
	'memory',
	'busydisk',
	'busynic',
	'default_gateway',
	'battery',
	'eyecare',
	'mail',
	'date',
]

def flush_status():
	global comma_flag
	if comma_flag:
		print(',', end = "")
	else:
		comma_flag = True
	print(json.dumps(
		[qyjn_status[key] for key in module_list if key in qyjn_status.keys()],
		separators = (',', ':'),
	), flush = True)

# handle date within main_loop to get precise second
def main_loop():
	while True:
		now = datetime.datetime.now()
		date = now.strftime('%m-%d %H:%M:%S')
		result = {"full_text": date}
		t = now.timestamp()
		dt = round(t) + 1 - t
		if dt > 1.0 or dt < 0.9:
			result['color'] = bad_color
		qyjn_status['date'] = result
		flush_status()
		sleep(dt)

def main():
	print('{"version":1}')
	print('[')
	for module in module_list:
		tmp_module = qyjn_module(globals().get('module_' + module))
		thread = Thread(target = tmp_module.run)
		thread.start()
	main_loop()

if __name__ == '__main__':
	main()
