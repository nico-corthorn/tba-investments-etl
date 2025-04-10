from setuptools import setup, find_packages
import os

def read_requirements(filename):
    with open(filename) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def get_version():
    version_file = os.path.join(os.path.dirname(__file__), 'tbainvestetl', 'version.py')
    with open(version_file) as f:
        version_globals = {}
        exec(f.read(), version_globals)
        return version_globals['__version__']

setup(
    name="tbainvestetl",
    version=get_version(),
    packages=find_packages(include=['tbainvestetl*']),
    package_data={
        'tbainvestetl': ['**/*'],
        '': ['lambda_requirements.txt'],
    },
    include_package_data=True,
    install_requires=read_requirements('lambda_requirements.txt'),
)