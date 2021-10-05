import qyjn_status
from timeit import timeit

def sleep_call_dummy(interval, callback):
	pass

def test_internet_dummy(host="1.1.1.1", port=53, timeout=1.0):
	return True

qyjn_status.sleep_call = sleep_call_dummy
qyjn_status.test_internet = test_internet_dummy

module_list = [
	'cpufreq',
	'temp',
	'memory',
	'busydisk',
	'busynic',
	'default_gateway',
	'battery',
	'date',
]
number = 100
print("x", number)
for module in module_list:
	t = timeit(
		f"module_{module}()",
		setup = f"from qyjn_status import module_{module}",
		number = number,
	)
	print(f"{module}: {t:.5f}",
	)
