#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="valideer",
    version="0.1",
    description="Lightweight validation and adaptation library",
    long_description=open("README.rst").read(),
    url="https://github.com/podio/valideer",
    author="George Sakkis",
    author_email="george@podio.com",
    packages=find_packages(),
    install_requires=["decorator"],
    tests_require=["nose", "coverage"],
    platforms=["any"],
    keywords="validation adaptation typechecking jsonschema",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
    ],
)
