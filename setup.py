from setuptools import setup, find_packages
import os

def read(fname):
	return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
	name="crossgen",
	version="0.0.5dev",
	description="crossword generation tool",
	long_description=read('README.md'),
	author="ahiijny",
	author_email="ahiijny@gmail.com",
	license="GPLv3",
	packages=find_packages(),
	python_requires=">=3",
	install_requires = [
		'networkx',
		'PyQt5',
		'PyQtWebEngine'
	],
	entry_points = {
		"console_scripts" : [
			"crossgenc = crossgen.__main__:main",
		],
		"gui_scripts" : [
			"crossgen = crossgen.gui.__main__:main"
		]		
	},
)
