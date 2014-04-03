DXR Multiline highlighter
==========================

*This document details how to use the code highlighter functionality
found in the File view in DXR*

The code highlighter attempts to emulate multiline highlighting
functionality found in most operating system type file
managers.

There are four major ways to use the highlighter:

#. Single click

#. Single click then ``Shift+click``

#. ``Ctrl+click`` (Windows/Linux), ``Command+click`` (OSX)

#. ``Ctrl/Command+click`` then ``Shift+click``

Each method updates the ``window.location.hash`` portion of the URL in
the user's browser window so that the highlighted lines can be
regenerated when a page is bookmarked or shared for reuse in chat,
bugzilla tickets, github etc.

Single Click
------------

Single click on  line to select it. Click it again to deselect it.
Simple. Single clicking a line will also deselect all other single
lines, or ranges of lines.

Single click then ``Shift+click``
---------------------------------

After selecting a line, hold shift and select a line above or below
the first line to highlight the entire range of lines.

``Ctrl/Commnd+click``
---------------------

Hold Ctrl/Command while selecting a line and the individual line will be added
to any other highlighted lines or ranges of lines. ``Ctrl/Command+click`` a
selected line to deselect it.

``Ctrl/Command+click`` a highlighted line contained within a range of lines and the
range will be split at the line in question.


``Ctrl/Command+click`` then ``Shift+click``
-------------------------------------------

After selecting a line or range of lines, use ``Ctrl/Command+click`` to start
highlight the first line in another range of lines. You can then use
Shift+click and the second range will be highlighted, in addition to
any others.