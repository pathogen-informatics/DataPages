from setuptools import setup, find_packages

setup(
    name='datapages',
    version='0.0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'boltons',
        'Jinja2',
        'Markdown',
        'pandas',
        'PyMySQL',
        'PyYAML',
        'requests'

    ],
    entry_points='''
        [console_scripts]
        datapages_update_projects=datapages.update_projects:main
    ''',
)
