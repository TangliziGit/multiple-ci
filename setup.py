from setuptools import find_packages, setup

setup(
    name='multiple-ci',
    version='0.0.1',
    install_requires=['pika', 'PyYAML', 'redis', 'Click', 'tornado', 'elasticsearch>=8.6', 'requests'],
    packages=find_packages('lib'),
    package_dir={'': 'lib'},
    entry_points={
        'console_scripts': [
            'mci-scanner=multiple_ci.cli.scanner:main',
            'mci-scheduler=multiple_ci.cli.scheduler:main',
            'mci-analyzer=multiple_ci.cli.analyzer:main',
            'mci-notifier=multiple_ci.cli.notifier:main',
        ],
    },
)