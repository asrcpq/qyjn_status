import qyjn_status
from timeit import timeit

def test_internet_dummy(host="1.1.1.1", port=53, timeout=1.0):
	return True

qyjn_status.test_internet = test_internet_dummy
number = 100
print("x", number)
for module in qyjn_status.module_list:
	t = timeit(
		f"module_{module}()",
		setup = f"from qyjn_status import module_{module}",
		number = number,
	)
	print(f"{module}: {t:.5f}",
	)
