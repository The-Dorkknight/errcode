# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="errcode",
    version="0.3.3",   # displayed as 0.3.1-wip while the project is a work in progress
    author="Matthew Armstrong",
    author_email="The-Dorkknight@users.noreply.github.com",
    description="Drop-in error-code plugin: 3-digit codes, ranked reports packed as digits, QR output and decoders",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/The-Dorkknight/errcode",
    license="PolyForm-Noncommercial-1.0.0",
    package_dir={"": "src"},
    packages=find_packages("src"),
    include_package_data=False,
    python_requires=">=3.8",
    install_requires=[],                       # the core needs nothing beyond the standard library
    extras_require={"qr": ["segno>=1.5"]},     # optional QR images
    entry_points={"console_scripts": ["errcode=errcode.cli:main"]},
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
)
