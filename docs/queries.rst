Query Syntax
============

Entering plain text searches the code and pathnames. Each word is taken as a separate substring to match, and the substrings are and-ed together on a per-line basis.

To exclude lines matching a word, precede the word with "-".

Filters
=======

Other, more specific search filters are also available:

``path:``
    Pathname with shell-style globbing
``fn:`` (or ``fun:`` or ``func:`` or ``function:``?)
    Definitions or declarations of a function with the given prefix
``fn-ref:``
    Uses of a given function
``re:`` or ``regex:`` or ``regexp:``
    Regular expression
``member:``
    Find member functions of a class (or struct?).
``id:``
    Identifier of any kind (maybe not necessary if we do search ranking better)
``ref:``
    A reference to any kind of identifier
``caller:`` or ``callers:``
    Functions that call a given function
``called-by:``
    Functions called by a given function
``type:``
    The definition or declaration of a given type
``type-ref:``
    Uses of a given type
``var:``
    Definitions or declarations of a variable
``var-ref:``
    Uses of a given variable
``namespace:``
    Definition or declaration of a namespace
``namespace-ref:``
    Uses of a namespace
``namespace-alias: namespace-alias-ref:``
    Should these merge into the above?
``macro:``
    Definition or declaration of a macro
``macro-ref:``
    Use of a macro
``subclass:`` or ``sub:``
    Subclass of a class
``superclass:`` or ``super:``
    Superclass of a class
``warning:``
    Compiler warnings?
``warning-opt:``
    More compiler warnings?

Again, query terms are and-ed together and matched against individual lines of the codebase, like grep's single-line mode. This query, for example, finds all the lines from ``.h`` files containing the words "big", "angry", and either "hamster" or "hippo". ::

    path:*.h big angry re:hamster|hippo

You can negate a filter by preceding it with "-"::

    -path:*.cpp -path:*.c fn:foo

Obsolete
--------

* ``ext:`` goes away. It's covered by ``file:*.c``
* ``*-decl:`` goes away until somebody asks for it. It's merged into ``*``.

To Be Determined
----------------

* spelling of the "fully-qualified" operator
* a way to express case-sensitivity

Quoting and Escaping
====================

To do phrase matching or include spaces in a term, use single or double quotes. Doubles can contain singles, and vice versa. You can also backslash-escape them. ::

    "big, bad wolf"
    'That "wolf" is a hamster.'
    'Don\'t call my wolf a "hamster".'
    re:"big old|great big"
    -"not this phrase"

You can use a literal quote without enclosing it in other quotes, as long as it isn't a leading one::

    path:/users/erik's/*.py

What of backslashes in unquoted strings and preceding things other than quotes?

* In a quoted string, a backslash before a quote of the same type is an escaper. Otherwise, it's a literal backslash. ::

    "one long string"
    "literal \backslashes"

* \\ in a quoted string is a literal backslash, so you can represent \":

    "\\\" is backslash-quote"

* Later, we may let backslashes in unquoted strings escape spaces:

    one\ long\ string

These rules are akin to common shell syntax and designed so you don't need to plan ahead (or backtrack) when typing a query.
