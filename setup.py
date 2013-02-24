import sys

# Prevent spurious errors during `python setup.py test`, a la
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html:
try:
    import multiprocessing
except ImportError:
    pass

from setuptools import setup, find_packages


setup(
    name='dxr',
    version='0.1',
    description='Source code static analysis and browsing',
    long_description=open('README.mkd').read(),
    author='Erik Rose',
    author_email='erik@mozilla.com',
    license='MIT',
    packages=find_packages(exclude=['ez_setup']),
    package_data={'dxr': ['plugins/clang/*.so']},
    scripts=['bin/dxr-build.py', 'bin/dxr-serve.py'],
    install_requires=['Flask>=0.9', 'Pygments>=1.4', 'Jinja2>=2.6'],
    tests_require=['nose'],
    url='https://github.com/mozilla/dxr',
    include_package_data=True,
    zip_safe=False,  # So we can find dxr-worker.py as a file to run it as a
                     # subprocess
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
