#!/usr/bin/env python3
"""
Android Auto Flash Tool - Setup Script
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="android-auto-flash",
    version="0.1.0",
    description="Android 全自动刷机工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/android-auto-flash",
    packages=find_packages(exclude=["tests", "tests.*", "docs", "examples"]),
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "loguru>=0.6.0",
        "pyyaml>=6.0",
        "uiautomator2>=2.16.0",
    ],
    extras_require={
        "dev": [
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
            "pylint>=2.13.0",
            "isort>=5.10.0",
            "pytest>=7.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "android-flash=main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
