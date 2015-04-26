===========
Development
===========


Architecture
------------

.. image:: block-diagram.png

DXR divides into 2 halves:

1. The indexer, :program:`dxr index`, is a batch job which analyzes code and
   builds on-disk indices.

   The indexer hosts various plugins which handle everything from syntax
   coloring to static analysis. The clang plugin, for example, which handles
   structural analysis of C++ code, builds the project under clang while
   interposing a custom compiler plugin. The plugin rides sidecar with the
   compiler, dumping out structural data into CSV files, which the DXR plugin
   later uses to fill elasticsearch with the information that supports
   structural queries like ``callers:`` and ``function:``.

   Generally, the indexer is kicked off asynchronously—often even on a separate
   machine—by cron or a build system. It's up to deployers to come up with
   strategies that make sense for them.

2. A Flask web application which lets users query those indices.
   :program:`dxr serve` is a way to run the application for development
   purposes, but a more robust method should be used for :doc:`deployment`.


Setting Up
----------

Here we show the fastest way to get hacking on DXR.

.. include:: download-boot-and-build.rst

Running A Test Index
====================

The folder-based test cases make decent workspaces for development, suitable
for manually trying out your changes. ``test_basic`` is a good one to start
with. To get it running... ::

    cd ~/dxr/tests/test_basic
    dxr index
    dxr serve -a

You can then surf to http://33.33.33.77:8000/ from the host machine and play
around. When you're done, stop the server with :kbd:`Control-C`.


Workflow
--------

The repository on your host machine is mirrored over to the VM via Vagrant's
shared-folder magic. Changes you make outside the VM will be instantly
available within and vice versa, so you can edit using your usual tools on the
host and still use the VM to run DXR.

After making changes to DXR, a build step is sometimes needed to see the
effects of your work:

Changes to C-based compiler plugins:
    ``make`` (at the root of the project)

Changes to HTML templates that are used on the client side:
    ``make templates``. (This is a subset of ``make``, above, and may be
    faster.) Alternatively, leave ``node_modules/.bin/grunt watch`` running,
    and it will take care of recompiling the templates as necessary.

Changes to server-side HTML templates or the format of the elasticsearch index:
    Run ``make`` inside :file:`tests/test_basic`.

Stop :program:`dxr serve`, run the build step, and then fire up the server
again. If you're changing Python code that runs only at request time, you
shouldn't need to do anything; :program:`dxr serve` should notice and
restart itself a few seconds after you save.


Testing
-------

DXR has a fairly mature automated testing framework, and all server-side
patches should come with tests. (Tests for client-side contributions are
welcome as well, but we haven't got the harness set up yet.)


Writing Tests for DXR
=====================

DXR supports two kinds of tests:

1. A lightweight sort with a single file worth of C++ code. This kind
   stores the C++ source as a Python string within a subclass of
   ``SingleFileTestCase``. At test time, it creates a DXR instance on
   disk in a temp folder, builds it, and makes assertions about it. If
   the ``should_delete_instance`` class variable is truthy, it then
   deletes the instance. If you want to examine the instance manually
   for troubleshooting, set this to ``False``.

2. A heavier sort which consists of a full DXR instance on disk.
   ``test_ignores`` is an example. Within these instances are one or
   more Python files containing subclasses of ``DxrInstanceTestCase``
   which express the actual tests. These instances can be built like any
   other using ``dxr index``, in case you want to do manual
   exploration.

Running the Tests
=================

To run all the tests, run this from the root of the DXR repository::

    make test

To run just the tests in ``tests/test_functions.py``... ::

    nosetests tests/test_functions.py

To run just the tests from a single class... ::

    nosetests tests/test_functions.py:ReferenceTests

To run a single test... ::

    nosetests tests/test_functions.py:ReferenceTests.test_functions

If you have trouble, make sure you didn't mistranscribe any colons or
periods.


The Format Version
------------------

In the top level of the :file:`dxr` package lurks a file called
:file:`format`. Its role is to facilitate the automatic deployment of new
versions of DXR using a script like the included :file:`deploy.py`. The format
file contains an integer which represents the instance format expected by the
DXR code. If a change in the code requires something new in the instance,
generally (1) differently structured HTML or (2) a new DB schema, the format
version must be incremented with the code change. In response, the deployment
script will wait until a new instance, of the new format, has been built
before deploying the change.

If you aren't sure whether to bump the format version, you can always build an
instance using the old code, then check out the new code and try to serve the
old instance with it. If it works, you're probably safe not bumping the version.


Coding Conventions
------------------

Follow `PEP 8`_ for Python code, but don't sweat the line length too much.

.. _PEP 8: http://www.python.org/dev/peps/pep-0008/


.. _writing-plugins:

Writing Plugins
---------------

Plugins are the recommended way to add new types of analysis, indexing,
searching, or display to DXR. In fact, even DXR's basic capabilities, such as
text search and syntax coloring, are implemented as plugins. Want to add
support for a new language? A new kind of search to an existing language? A
new kind of contextual menu cross-reference? You're in the right place.

At the top level, a :class:`~dxr.plugins.Plugin` class binds together a
collection of subcomponents which do the actual work:

.. digraph:: plugin

   "Plugin" -> "TreeToIndex" -> "FileToIndex";
   "Plugin" -> "FileToSkim";
   "Plugin" -> "filters";
   "Plugin" -> "mappings";
   "Plugin" -> "analyzers";

Registration
============

A Plugin class is registered, either directly or indirectly, via a `setuptools
entry point
<https://pythonhosted.org/setuptools/setuptools.html#dynamic-discovery-of-
services-and-plugins>`__ called ``dxr.plugins``. For example, here are the
registrations for the built-in plugins, from DXR's own :file:`setup.py`::

    entry_points={'dxr.plugins': ['urllink = dxr.plugins.urllink',
                                  'buglink = dxr.plugins.buglink',
                                  'clang = dxr.plugins.clang',
                                  'omniglot = dxr.plugins.omniglot',
                                  'pygmentize = dxr.plugins.pygmentize']},

The keys in the key/value pairs, like "urllink" and "buglink", are the strings
the deployer can use in the ``enabled_plugins`` config directive. The values,
like "dxr.plugins.urllink", can point to either...

1. A :class:`~dxr.plugins.Plugin` class which itself points to filters,
   skimmers, indexers, and such. This is the explicit approach—more lines of
   code, more opportunities to buck convention—and thus not recommended in
   most cases. The :class:`~dxr.plugins.Plugin` class itself is just a dumb
   bag of attributes whose only purpose is to bind together a collection of
   subcomponents that should be used together.

2. Alternatively, an entry point value can point to a module which contains
   the subcomponents of the plugin, each conforming to a naming convention by
   which it can be automatically found. This method saves boilerplate and
   should be used unless there is a compelling need otherwise. Behind the
   scenes, an actual Plugin object is constructed implicitly: see
   :meth:`~dxr.plugins.Plugin.from_namespace` for details of the naming
   convention.

Here is the Plugin object's API, in case you do decide to construct one
manually:

    .. autoclass:: dxr.plugins.Plugin
       :members:
    
Actual plugin functionality is implemented within tree indexers, file
indexers, filters, and skimmers.

Tree Indexers
=============

.. autoclass:: dxr.indexers.TreeToIndex
   :members:

File Indexers
=============

.. autoclass:: dxr.indexers.FileToIndex
   :members:

FileToIndex also has all the methods of its superclass,
:class:`~dxr.indexers.FileToSkim`.

Looking Inside Elasticsearch
````````````````````````````

While debugging a file indexer, it can help to see what is actually getting
into elasticsearch. For example, if you are debugging
:meth:`~dxr.indexers.FileToIndex.needles_by_line`, you can see all the data
attached to each line of code (up to 1000) with this curl command::

    curl -s -XGET "http://localhost:9200/dxr_10_code/line/_search?pretty&size=1000"

Be sure to replace "dxr_10_code" with the name of your DXR index. You
can see which indexes exist by running... ::

    curl -s -XGET "http://localhost:9200/_status?pretty"

Similarly, when debugging :meth:`~dxr.indexers.FileToIndex.needles`, you can
see all the data attached to files-as-a-whole with... ::

    curl -s -XGET "http://localhost:9200/dxr_10_code/file/_search?pretty&size=1000"

File Skimmers
=============

.. note::

    The code that will call skimmers isn't in place yet.

.. autoclass:: dxr.indexers.FileToSkim
   :members:

Filters
=======

.. autoclass:: dxr.filters.Filter
   :members:

Mappings
========

When you're laying down data to search upon, it's generally not enough just to
write :meth:`~dxr.indexers.FileToIndex.needles` or
:meth:`~dxr.indexers.FileToIndex.needles_by_line` implementations. If you want
to search case-insensitively, for example, you'll need elasticsearch to fold
your data to lowercase. (Don't fall into the trap of doing this in Python; the
Lucene machinery behind ES is better at the complexities of Unicode.) The way
you express these instructions to ES is through mappings and analyzers.

ES :term:`mappings<mapping>` are schemas which specify type of data (string,
int, datetime, etc.) and how to index it. For example, here is an excerpt of
DXR's core mapping, defined in the ``core`` plugin::

    mappings = {
        # Following the typical ES mapping format, `mappings` is a hash keyed
        # by doctype. So far, the choices are ``LINE`` and ``FILE``. 
        LINE: {
            'properties': {
                # Line number gets mapped as an integer. Default indexing is fine
                # for numbers, so we don't say anything explicitly.
                'number': {
                    'type': 'integer'
                },

                # The content of the line itself gets mapped 3 different ways.
                'content': {
                    # First, we store it as a string without actually putting it
                    # into any ordered index structure. This is for retrieval and
                    # display in search results, not for searching on:
                    'type': 'string',
                    'index': 'no',
                
                    # Then, we index it in two different ways: broken into
                    # trigrams (3-letter chunks) and either folded to lowercase or
                    # not. This cleverness takes care of substring matching and
                    # accelerates our regular expression search:
                    'fields': {
                        'trigrams_lower': {
                            'type': 'string',
                            'analyzer': 'trigramalyzer_lower'
                        },
                        'trigrams': {
                            'type': 'string',
                            'analyzer': 'trigramalyzer'
                        }
                    }
                }
            }
        },
        FILE: ...
    }

Mappings follow exactly the same structure as required by `ES's "put mapping"
API
<http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/indices
-put-mapping.html>`__. The `choice of mapping types
<http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/mapping
-types.html>`__ is also outlined in the ES documentation.

.. warning::

    Since a FILE-domain query will be promoted to a LINE query if any other
    query term triggers a line-based query, it's important to keep field names
    and semantics the same between lines and files. In other words, a LINE
    mapping should generally be a superset of a FILE mapping. Otherwise, ES
    will guess mappings for the undeclared fields, and surprising search
    results will likely ensue.

Analyzers
=========

In Mappings, we alluded to custom indexing strategies, like breaking strings
into lowercase trigrams. These strategies are called
:term:`analyzers<analyzer>` and are the final subcomponent of a plugin. ES has
`strong documentation on defining analyzers
<http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/
analysis.html#analysis>`__. Declare your analyzers (and building blocks of
them, like tokenizers) in the same format the ES documentation prescribes. For
example, the analyzers used above are defined in the core plugin as follows::

    analyzers = {
        'analyzer': {
            # A lowercase trigram analyzer:
            'trigramalyzer_lower': {
                'filter': ['lowercase'],
                'tokenizer': 'trigram_tokenizer'
            },
            # And one for case-sensitive things:
            'trigramalyzer': {
                'tokenizer': 'trigram_tokenizer'
            }
        },
        'tokenizer': {
            'trigram_tokenizer': {
                'type': 'nGram',
                'min_gram': 3,
                'max_gram': 3
                # Keeps all kinds of chars by default.
            }
        }
    }

Crash Early, Crash Often
========================

Since DXR's indexer generally runs without manual supervision, it's better to
err on the side of crashing than to risk incorrectness. Any error that could
make a plugin emit inaccurate output should be fatal. This keeps DXR's
structural queries trustworthy.

Configuration
=============

Configuration keys prefixed with ``plugin_`` in either a tree section or the
DXR section of the configuration will be read and stored on the ``tree`` and
``config`` objects, respectively. Please note that these values will not have
any default values, nor will they be present unless defined in the config file.

It's the plugins' responsibility to validate these values. Plugins should
prefix all config keys as ``plugin_<plugin-name>_<key>``. Plugins living in
the DXR codebase must document their keys in the plugin section of
:doc:`configuration`.

Contributing documentation
---------------

We use `Read the Docs`_ for building and hosting the documentation, which uses
`sphinx`_ to generate HTML documentation from reStructuredText markup.

To make changes to documentation:
  * Edit :file:`*.rst` files in :file:`docs/source/` in your local checkout.
    See `reStructuredText primer`_ for syntax aids.
  * Use ``cd ~/dxr/docs && make html`` in the VM to preview the docs.
  * When you're satisfied, submit the pull request as usual.

.. _Read the Docs: https://docs.readthedocs.org/
.. _sphinx: http://sphinx-doc.org/
.. _reStructuredText primer: http://sphinx-doc.org/rest.html


Troubleshooting
---------------

Why is my copy of DXR acting erratic, failing at searches, making requests for JS templates that shouldn't exist, and just generally not appearing to be in sync with my changes?
    Did you run ``python setup.py install`` for DXR at some point? Never, ever
    do that in development; use ``python setup.py develop`` instead. Otherwise,
    you will end up with various files copied into your virtualenv, and your
    edits to the originals will have no effect.

How can I use pdb to debug indexing?
    In the DXR config file for the tree you're building, add ``disable_workers
    = true`` to the ``[DXR]`` section. That will keep DXR from spawning
    multiple worker processes, something pdb doesn't tolerate well.

I pulled a new version of the code that's supposed to have a new plugin (or I added one myself), but it's acting like it doesn't exist.
    Re-run ``python setup.py develop`` to register the new setuptools entry point.
