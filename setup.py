from setuptools import setup, find_packages
import os

def read(fname):
	return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
	name="crossgen",
	version="0.0.2",
	description="derp crossword helper tool",
	long_description=read('README.md'),
	author="ahiijny",
	author_email="ahiijny@gmail.com",
	license="MIT",
	packages=find_packages(),
	install_requires = [
		'networkx'
	],
	entry_points = {
		"console_scripts" : [
			"crossgen = crossgen.__main__:main",
		],
	},
)
