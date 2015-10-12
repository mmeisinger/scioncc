#!/usr/bin/env python

from setuptools import setup, find_packages

import os
import sys

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

def get_data_dirs(path, patterns):
    data_dirs = [(rt+"/"+dn+"/") for rt, ds, fs in os.walk(path) for dn in ds]
    data_dir_patterns = []
    for pat in patterns:
        data_dir_patterns += [(dn+pat)[len(path)+1:] for dn in data_dirs]
    return data_dir_patterns

# Add /usr/local/include to the path for macs, fixes easy_install for several packages (like gevent and pyyaml)
if sys.platform == 'darwin':
    os.environ['C_INCLUDE_PATH'] = '/usr/local/include'

VERSION = read("VERSION").strip()

# See http://pythonhosted.org/setuptools/setuptools.html
# noinspection PyPackageRequirements
setup(  name='scioncc',
        version=VERSION,
        description='Scientific Observatory Network Capability Container',
        long_description=read('README'),
        url='https://www.github.com/scionrep/scioncc/wiki',
        download_url='https://github.com/scionrep/scioncc/releases',
        license='BSD',
        author='SciON Contributors',
        author_email='michael.meisinger@gmail.com',
        keywords=['scion', 'pyon', 'ion'],
        classifiers=['Programming Language :: Python',
                    'Programming Language :: Python :: 2.7',
                    'License :: OSI Approved :: BSD License',
                    'Operating System :: OS Independent',
                    'Development Status :: 5 - Production/Stable',
                    'Intended Audience :: Developers',
                    'Environment :: Web Environment',
                    'Topic :: Internet',
                    'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
                    'Topic :: Scientific/Engineering',
                    'Topic :: Software Development',
                    'Topic :: Software Development :: Libraries :: Application Frameworks'],
        packages=find_packages('src') + find_packages('.'),
        package_dir={'': 'src',
                     'interface': 'interface',
                     'defs': 'defs'},
        include_package_data=True,
        package_data={
            '': ['*.yml', '*.txt'] + get_data_dirs("defs", ["*.yml", "*.sql", "*.xml"]) + get_data_dirs("src/ion/processes/ui", ["*.css", "*.js"]),
        },
        entry_points={
             'nose.plugins.0.10': [
                 'timer_plugin=pyon.util.testing.timer_plugin:TestTimer',
                 'greenletleak=pyon.util.testing.greenlet_plugin:GreenletLeak',
                 'gevent_profiler=pyon.util.testing.nose_gevent_profiler:TestGeventProfiler',
             ],
            'console_scripts': [
                'pycc=scripts.pycc:entry',
                'control_cc=scripts.control_cc:main',
                'generate_interfaces=scripts.generate_interfaces:main',
                'store_interfaces=scripts.store_interfaces:main',
                'clear_db=pyon.datastore.clear_db_util:main',
                'coverage=scripts.coverage:main',
                ]
            },
        dependency_links=[],
        install_requires=[
            # NOTE: Install order is bottom to top! Lower level dependencies need to be down
            'setuptools',
            'greenlet==0.4.7',
            'gevent==1.0.2',
            'pyyaml==3.10',
            'simplejson==3.6.5',
            'msgpack-python==0.1.13',  # TBD: Check if this specific version is needed
            'pika==0.9.5',             # NEED THIS VERSION. Messaging stack tweaked to this version
            'httplib2==0.9.1',
            'zope.interface==4.1.1',
            'psycopg2==2.5.4',
            'numpy==1.9.2',
            'python-daemon==2.0.5',
            'ipython==0.13.0',
            'readline==6.2.4.1',
            'ndg-xacml==0.5.1',        # For policy rule engine
            'requests==2.5.3',
            'psutil==2.1.3',
            'Flask==0.10.1',
            'flask-socketio==0.4.1',
            'bcrypt==1.0.1',           # For password authentication
            'pyzmq==2.2.0',            # For IPython manhole
            'gevent_zeromq==0.2.5',    # For old pyzmq patching
            'flask-oauthlib==0.9.1',
            'pyproj==1.9.4',           # For geospatial calculations (e.g. bbox midpoint)

            # Pin dependent libraries to be safe
            'requests-oauthlib==0.4.2',
            'cffi==0.9.2',
            'oauthlib==0.7.2',
            'six==1.9.0',

            # Test support
            'nose==1.1.2',
            'mock==0.8',
            'coverage==4.0',           # Code coverage
        ],
        extras_require={
            'utils': [
                'xlrd==0.9.3',         # For Excel file read (dev tools)
                'xlwt==0.7.5',         # For Excel file write (dev tools)
            ],
            'logging': [
                'graypy==0.2.11',      # For production logging
            ],
            'security': [
                'M2Crypto==0.22.3',    # For X.509 certificates (currently unused)
            ],
        }
     )
