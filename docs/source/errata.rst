Errata
======

As with any piece of software, there are and will be noteworthy issues and 
workarounds. Here are some known ones:

Permalinks
----------

#. Requires dxr.config.in tree name to match upstream git/hg remote name

  * For example: git@github.com/mozilla/dxr.git - the remote name would be *dxr* and
    the dxr.config.in tree would have to be labelled [dxr]

Omniglot Plugin
---------------

#. Requires an underlying .hg repository with an *hgrc* [path] be defined

  * Otherwise there will be no rendered HTML output.