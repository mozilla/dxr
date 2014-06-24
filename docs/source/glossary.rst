========
Glossary
========

.. glossary::

    filtered term
        A query term consisting of an explicit filter name and an argument,
        like ``regexp:hi|hello`` or ``callers:frob``

    index
        A folder containing one or more source trees indexed for search and
        prepared to serve as HTML. Indices are created by the
        :program:`dxr-index.py` command.

    instance
        See :term:`index`.

    term
        A space-delimited part of a query

    text term
        A query term without an explicit filter name, interpreted as raw text
        for a substring search