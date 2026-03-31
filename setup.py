"""dBase Revival by Jair Lima - Setup"""
from setuptools import setup, find_packages

setup(
    name="dbase-revival",
    version="1.0.0",
    author="Jair Lima",
    description="dBase Revival by Jair Lima - Clone funcional do dBASE classico para terminal",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "dbase=dbase.main:main",
        ],
    },
    install_requires=[
        "windows-curses;platform_system=='Windows'",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Database",
    ],
)
