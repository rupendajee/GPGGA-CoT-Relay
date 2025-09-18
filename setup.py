from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="gpgga-cot-relay",
    version="1.0.0",
    author="Your Name",
    description="A lightweight and reliable GPGGA to CoT relay for TAK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/gpgga-cot-relay",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pytak>=5.4.0",
        "aiofiles>=23.2.1",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "python-dotenv>=1.0.0",
        "structlog>=24.1.0",
        "prometheus-client>=0.19.0",
    ],
    entry_points={
        "console_scripts": [
            "gpgga-cot-relay=gpgga_cot_relay.__main__:main",
        ],
    },
)
