.. note::

     Most development is now taking place on the ``es`` branch. ``master`` is in maintenance mode for the moment.

===
DXR
===

DXR is a code search and navigation tool aimed at making sense of large
projects like Firefox. It supports full-text and regex searches as well as
structural queries like "Find all the callers of this function." Behind the
scenes, it uses trigram indices, the re2 library, and static analysis data
collected by instrumented compilers to make searches faster and more accurate
than is possible with simple tools like grep.

.. image:: docs/source/screenshot.png

* Example: http://dxr.mozilla.org/
* Documentation: https://dxr.readthedocs.org/en/es/
