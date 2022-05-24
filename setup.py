import setuptools

setuptools.setup(
	name = "qyjn",
	packages = setuptools.find_packages(),
	entry_points = {
		"console_scripts": ["qyjn_status = qyjn.qyjn_status:main"],
	},
	python_requires = ">=3.6",
)
