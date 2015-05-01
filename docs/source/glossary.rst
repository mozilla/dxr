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

    format version
        A string (though usually looking like an int) signifying the index
        format. It is used to control deployments: :program:`dxr deploy` never
        switches to a new version of the web-serving code until all indices
        have been brought up to the format version it requires. The format
        version is declared in :file:`dxr/format`.

    index
        The collected data used to answer queries about a tree and render the
        web-based UI. These are stored in elasticsearch and created by
        :program:`dxr index`.

    mapping
        An elasticsearch schema, declaring the type and indexing strategy for
        each field

    term
        A space-delimited part of a query

    text term
        A query term without an explicit filter name, interpreted as raw text
        for a substring search
