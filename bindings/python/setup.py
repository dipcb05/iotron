from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).resolve().parents[2]

setup(
    name="iotron",
    version="0.2.0",
    description="IoTron Python compatibility binding",
    packages=find_packages(where=str(ROOT)),
    package_dir={"": str(ROOT)},
)

