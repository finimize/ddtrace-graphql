from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

with open(path.join(here, "VERSION"), encoding="utf-8") as f:
    version = f.read()


setup(
    name="ddtrace-graphql",  # Required
    version=version,  # Required
    description="Python library for tracing graphql calls with Datadog",
    long_description=long_description,  # Optional
    url="https://github.com/beezz/ddtrace-graphql",  # Optional
    author="Michal Kuffa",  # Optional
    author_email="michal@bynder.com",  # Optional
    classifiers=[  # Optional
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Debuggers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.7",
    keywords="tracing datadog graphql graphene",
    packages=find_packages(exclude=["tests"]),  # Required
    install_requires=["ddtrace>=1.5.5", "graphql-core", "wrapt"],
    extras_require={"test": ["tox", "pytest", "pytest-cov"]},
)
