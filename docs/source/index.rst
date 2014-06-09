Overview
========

DXR is a code search and navigation tool aimed at making sense of large
projects like Firefox. It supports full-text and regex searches as well as
structural queries like "Find all the callers of this function." Behind the
scenes, it uses trigram indices, the re2 library, and static analysis data
collected by instrumented compilers to make searches faster and more accurate
than is possible with simple tools like grep.

Here's `an example of DXR running against the Firefox codebase`_. It looks like
this:

.. image:: screenshot.png

.. _`an example of DXR running against the Firefox codebase`: http://dxr.mozilla.org/


Contents
========

.. toctree::
    :maxdepth: 2
    :numbered:

    community
    getting-started
    configuration
    deployment
    use
    development


Back Matter
===========

.. toctree::
   :hidden:

   glossary
   icons

* :doc:`glossary`
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
* :doc:`icons`
