#!/usr/bin/env python3
"""BigFoot - Personal Progress Tracker"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="bigfoot",
    version="0.1.0",
    author="tksimson",
    description="A lightweight Python CLI tool that motivates developers to code daily",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "bigfoot=bigfoot.main:cli",
        ],
    },
    url="https://github.com/tksimson/BigFoot",
    project_urls={
        "Bug Reports": "https://github.com/tksimson/BigFoot/issues",
        "Source": "https://github.com/tksimson/BigFoot",
    },
)
