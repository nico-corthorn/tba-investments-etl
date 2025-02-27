from setuptools import setup, find_packages

def read_requirements(filename):
    with open(filename) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="tba_invest_etl",
    version="0.0.2",
    packages=find_packages(include=['tba_invest_etl*']),  # Explicitly include all tba_invest_etl subpackages
    package_data={'tba_invest_etl': ['**/*']},  # Include all files in the package
    include_package_data=True,
    install_requires=read_requirements('lambda_requirements.txt'),
)