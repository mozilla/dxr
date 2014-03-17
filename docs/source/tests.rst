Automated Testing of DXR
========================

*This document describes the automated testing framework for DXR.*

Writing Tests for DXR
---------------------

DXR supports two kinds of tests:

1. A lightweight sort with a single file worth of C++ code. This kind
   stores the C++ source as a Python string within a subclass of
   ``SingleFileTestCase``. At test time, it creates a DXR instance on
   disk in a temp folder, builds it, and makes assertions about it. If
   the ``should_delete_instance`` class variable is truthy, it then
   deletes the instance. If you want to examine the instance manually
   for troubleshooting, set this to ``False``.

2. A heavier sort of test which consists of a full DXR instance on disk.
   ``test_ignores`` is an example. Within these instances are one or
   more Python files containing subclasses of ``DxrInstanceTestCase``
   which express the actual tests. These instances can be built like any
   other using ``dxr-build.py``, in case you want to do manual
   exploration.

Running the Tests
-----------------

To run all the tests run this from the root of the DXR repository:

::

    make test

To run just the tests in ``tests/test_functions.py``, do this:

::

    # Make sure $LD_LIBRARY_PATH points to the trilite folder. Then...
    nosetests tests/test_functions.py

To run just the tests from a single class, do this:

::

    # Make sure $LD_LIBRARY_PATH points to the trilite folder. Then...
    nosetests tests/test_functions.py:ReferenceTests

To run a single test, do this:

::

    # Make sure $LD_LIBRARY_PATH points to the trilite folder. Then...
    nosetests tests/test_functions.py:ReferenceTests.test_functions

If you have trouble, make sure you didn't mistranscribe any colons or
periods.
