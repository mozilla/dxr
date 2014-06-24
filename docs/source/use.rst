===
Use
===

Querying
========

DXR queries are almost entirely text-based. In addition to being fast to input
for experienced users, having an all-text representation invites handy tricks
like `Firefox keyword bookmarks`_.

.. _`Firefox keyword bookmarks`: http://kb.mozillazine.org/Using_keyword_searches

A DXR query is a series of space-delimited :term:`terms<term>`:

* :term:`Filtered terms<filtered term>` are structured as ``<filter name>:<argument>``:

  * ``callers:frobulate``
  * ``var:num_caribou``

  Everything but plain text search is done using filtered terms.

* :term:`Text terms<text term>` are just bare text and do simple substring matching:

  * ``hello``
  * ``three independent words``

The way terms are combined is somewhat odd and will change in a future version.
For now, the behavior is as follows: terms are ANDed together on a per-file
basis and then ORed together on a per-line basis. For example, if you searched
for ``hairy gerbils``, the results would be files containing both the words
"hairy" and "gerbils", but the lines shown would be ones containing either
"hairy" *or* "gerbils". The upside is that this makes multi-line comments and
strings easy to find.

Quoting
-------

Single and double quotes can be used in filter arguments and in text terms to
help express literal spaces and other oddities. Singles can contain doubles,
doubles can contain singles, and each kind can contain itself if
backslash-escaped:

* A phrase with a space: ``"Hello, world"``
* Quotes in a plain text search, taken as literals since they're not leading:
  ``id="whatShouldIDoContent"``
* Double quotes inside single quotes, as a filter argument:
  ``regexp:'"wh(at|y)'``
* Backslash escaping: ``"I don't \"believe\" in fairies."``


Highlighting
============

Source code views support highlighting lines, runs of lines, and even multiple
runs of lines at once.

There are four ways to highlight. Each updates the hash portion of the URL so
the highlighted regions are maintained when a page is bookmarked or shared via
chat, bug reports, etc.

single click
    Single-click a line to select it. Click it again to deselect it.
    Single-clicking a line will also deselect all other lines.

single click then shift-click
    After selecting a single line, hold Shift, and click a line above or below
    it to highlight the entire range between.

control- or command-click
    Hold Control or Command (depending on your OS) while clicking a line to add
    it to the set of already highlighted lines. Do it again to deselect it.

control- or command-click, then shift-click
    After selecting one or more lines, use Control- or Command-Click to
    highlight the first in a new range of lines. Then, Shift-click, and the
    second range will be added to the existing highlighted set.
