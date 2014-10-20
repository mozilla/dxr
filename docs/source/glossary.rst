========
Glossary
========

.. glossary::

    analyzer
        An elasticsearch indexing strategy. The design of these should be
        determined by how you plan to query the fields that use them.

    filtered term
        A query term consisting of an explicit filter name and an argument,
        like ``regexp:hi|hello`` or ``callers:frob``

    index
        A folder containing one or more source trees indexed for search and
        prepared to serve as HTML. Indices are created by the
        :program:`dxr-build.py` command.

    instance
        See :term:`index`.
    
    mapping
        An elasticsearch schema, declaring the type and indexing strategy for
        each field

    term
        A space-delimited part of a query

    text term
        A query term without an explicit filter name, interpreted as raw text
        for a substring search
