#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='gae-paypal',
    version='0.0.1',
    description='Paypal base models for GAE',
    author='Mitchel Kelonye',
    author_email='kelonyemitchel@gmail.com',
    url='https://github.com/kelonye/gae-paypal',
    packages=['gae_paypal',],
    package_dir = {'gae_paypal': 'lib'},
    license='MIT',
    zip_safe=True
)