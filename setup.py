#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('HISTORY.md') as history_file:
    history = history_file.read()

requirements = [
    "pyvcloud",
    "kopf",
    "kubernetes",
    "PyYAML",
    "environ-config",
    "python-dotenv"
]

setup_requirements = [
    "coloredlogs"
]

test_requirements = [
]

description = "A python based proof of concept of an operator "
description += "to manage VMware Cloud Director ressources"

setup(
    author="Ludovic Rivallain",
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9'
    ],
    description=description,
    long_description_content_type="text/markdown",
    install_requires=requirements,
    license="MIT license",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='kvcd',
    name='kvcd',
    packages=find_packages(include=['kvcd', 'kvcd.*']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/lrivallain/kvcd',
    version='0.1.0',
    zip_safe=False,
)
