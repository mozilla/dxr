import sys

# Prevent spurious errors during `python setup.py test`, a la
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html:
try:
    import concurrent.futures
except ImportError:
    pass

from setuptools import setup, find_packages


setup(
    name='dxr',
    version='0.1',
    description='Source code static analysis and browsing',
    long_description=open('README.rst').read(),
    author='Erik Rose',
    author_email='erik@mozilla.com',
    license='MIT',
    packages=find_packages(exclude=['ez_setup']),
    scripts=['bin/dxr-build.py', 'bin/dxr-serve.py'],
    entry_points={'dxr.plugins': ['urllink = dxr.plugins.urllink',
                                  'buglink = dxr.plugins.buglink',
#                                   'clang = dxr.plugins.clang',
                                  'omniglot = dxr.plugins.omniglot',
                                  'pygmentize = dxr.plugins.pygmentize']},
    install_requires=['Flask>=0.9',
                      'futures>=2.1.1,<3.0',
                      'Jinja2>=2.6,<3.0',
                      'more-itertools>=2.2,<3.0',
                      'ordereddict>=1.1,<2.0',
                      'parsimonious==0.5',
                      'pyelasticsearch==0.7.1',
                      'Pygments>=1.6,<2.0',
                      'requests>=1.0,<2.0',
                      'funcy>=1.0,<2.0',
                      'toposort>=1.0,<2.0'],
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
