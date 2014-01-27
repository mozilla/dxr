import sys

# Prevent spurious errors during `python setup.py test`, a la
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html:
try:
    import concurrent.futures
except ImportError:
    pass

from setuptools import setup, find_packages

install_requires = [
    'Flask>=0.9',
    'futures>=2.1.1',
    'Jinja2>=2.6',
    'Pygments>=1.6',
]
if sys.version_info[:2] < (2, 7):
    install_requires.append('argparse>=1.2.1')

setup(
    name='dxr',
    version='0.1',
    description='Source code static analysis and browsing',
    long_description=open('README.mkd').read(),
    author='Erik Rose',
    author_email='erik@mozilla.com',
    license='MIT',
    packages=find_packages(exclude=['ez_setup']),
    entry_points={
        'console_scripts': [
            'dxr-build = dxr.cmdline:build_main',
            'dxr-serve = dxr.cmdline:serve_main'
        ]
    },
    install_requires=install_requires,
    tests_require=['nose'],
    test_suite='nose.collector',
    url='https://github.com/mozilla/dxr',
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Topic :: Software Development'
        ],
    keywords=['lxr', 'static analysis', 'source code']
)
