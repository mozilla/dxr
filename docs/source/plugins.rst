===============
Writing Plugins
===============

.. note::

    DXR is in the middle of a plugin system redesign that will move much of
    DXR's core functionality to plugins, eliminate singletons and custom
    loading tricks, and increase the capabilities of the plugin API. This
    chapter documents the old system.


Structure and API
=================

A plugin is a folder located in the :file:`plugins/` folder. A plugin's name
should not contain dashes or other characters not allowed in Python module
names. Notice that the plugin folder will be added to the search path for
modules, so plugin names shouldn't conflict with other modules. A plugin may
import submodules from within its own plugin folder if it contains an
:file:`__init__.py` file.

A plugin folder must contain these 3 files:

:file:`makefile`
    Build steps for this plugin. This is be a GNU makefile with targets
    ``build``, ``check``, and ``clean``. These build dependencies, verify the
    build, and clean up after it, respectively. Effects of this makefile
    should, insofar as possible, remain within the plugin's subdirectory. If
    your makefile does anything, be sure to add a reference to it in the
    top-level makefile so it gets called.

:file:`indexer.py`
    Routines that generate DB entries to support search

    This is a Python module with two functions—``pre_process(tree, environ)``
    and ``post_process(tree, conn)``—where parameters ``tree`` and ``conn`` are
    a config for the tree and a database connection, respectively. The
    ``environ`` parameter is a dictionary of environment variables and may be
    modified prior to build using by the ``pre_process`` function.

    Both functions will be called only once per tree and are allowed to use a
    number of subprocess as specified by ``tree.config.nb_jobs``. If a plugin
    wants to store information from pre- or post processing, it can do so in
    its own temporary directory: each plugin is allowed to use the temporary
    folder ``<tree.temp_folder>/plugins/<plugin-name>``. (The temporary folder
    will remain until htmlification is finished.)

:file:`htmlifier.py`
    Routines that emit metadata for building HTML

    This is a Python module with two functions: ``load(tree, conn)`` and
    ``htmlify(path, text)``. This module will be used by multiple processes
    concurrently, but ``load`` will be invoked in only one, allowing the module
    to load resources into global scope for caching or other purposes.

    Once ``load(tree, conn)`` has been invoked with the tree config object and
    database connnection, the ``htmlify(conn, path, text)`` function may be
    invoked multiple times. The ``path`` parameter is the path of the file in
    the tree; the ``text`` parameter is the file content as a string.

    The ``htmlify`` function return either ``None`` or an object with methods
    ``refs()``, ``regions()``, ``annotations()`` and ``links()``, which behave
    as follows:

    ``refs()``
        Yields tuples of ``(start, end, menu)``

    ``regions()``
        Yields tuples of ``(start, end, class)``

    ``annotations()``
        Yields tuples of ``(line, attributes)``, where ``attributes`` is a
        dictionary defined by plugins. It must be sensible to assign the
        key-value pairs as HTML attributes on a ``div`` tag, and ``class`` must
        contain ``note note-<type>`` where ``type`` can be used templates to
        differentiate annotations.

    ``links()``
        Yields tuples of ``(importance, section, items)``, where ``items`` is a
        generator of tuples of ``(icon, title, href)``. ``importance`` is an
        integer used to sort sidebar sections.

    Note that the htmlifier module may not write to the database. It also
    strongly recommended that the htmlifier module doesn't write to the plugins
    temporary folder. It is a **strict requirement** that the htmlifier module
    may be loaded and used by multiple processes at the same time. For this
    reason, the htmlifier is not allowed to have worker processes of its own.


Crash Early, Crash Often
========================

Since DXR's indexer generally runs without manual supervision, it's best to err
on the side of crashing rather than risk incorrectness. Any error that could
make a plugin emit inaccurate output should be fatal. This keeps DXR's
structural queries trustworthy.


Configuration
=============

Configuration keys prefixed with ``plugin_`` in either a tree section or the
DXR section of the configuration will be read and stored on the ``tree`` and
``config`` objects, respectively. Please note that these values will not have
any default values, nor will they be present unless defined in the config file.

It's the plugins' responsibility to validate these values. Plugins should
prefix all config keys as ``plugin_<plugin-name>_<key>``. It's also recommended
that plugins document their keys in the plugin section of
:doc:`configuration`.
