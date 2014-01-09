from codecs import getdecoder
import cgi
from datetime import datetime
from fnmatch import fnmatchcase
from heapq import merge
from itertools import chain, groupby, izip_longest
import json
from operator import itemgetter
import os
from os import stat
from os.path import dirname
import shutil
import subprocess
import sys
from sys import exc_info
from traceback import format_exc
from warnings import warn

from concurrent.futures import as_completed, ProcessPoolExecutor
from jinja2 import Markup

from dxr.config import Config
from dxr.plugins import load_htmlifiers, load_indexers
import dxr.languages
import dxr.mime
from dxr.utils import load_template_env, connect_database, open_log

try:
    from itertools import compress
except ImportError:
    from itertools import izip
    def compress(data, selectors):
        return (d for d, s in izip(data, selectors) if s)


def linked_pathname(path, tree_name):
    """Return a list of (server-relative URL, subtree name) tuples that can be
    used to display linked path components in the headers of file or folder
    pages.

    :arg path: The path that will be split

    """
    # Hold the root of the tree:
    components = [('/%s/source' % tree_name, tree_name)]

    # Populate each subtree:
    dirs = path.split(os.sep)  # TODO: Trips on \/ in path.

    # A special case when we're dealing with the root tree. Without
    # this, it repeats:
    if not path:
        return components

    for idx in range(1, len(dirs)+1):
        subtree_path = os.path.join('/', tree_name, 'source', *dirs[:idx])
        subtree_name = os.path.split(subtree_path)[1] or tree_name
        components.append((subtree_path, subtree_name))

    return components


def build_instance(config_path, nb_jobs=None, tree=None, verbose=False):
    """Build a DXR instance.

    :arg config_path: The path to a config file
    :arg nb_jobs: The number of parallel jobs to pass into ``make``. Defaults
        to whatever the config file says.
    :arg tree: A single tree to build. Defaults to all the trees in the config
        file.

    """
    # Load configuration file
    # (this will abort on inconsistencies)
    overrides = {}
    if nb_jobs:
        # TODO: Remove this brain-dead cast when we get the types right in the
        # Config object:
        overrides['nb_jobs'] = str(nb_jobs)
    config = Config(config_path, **overrides)

    skip_indexing = 'index' in config.skip_stages

    # Find trees to make, fail if requested tree isn't available
    if tree:
        trees = [t for t in config.trees if t.name == tree]
        if len(trees) == 0:
            print >> sys.stderr, "Tree '%s' is not defined in config file!" % tree
            sys.exit(1)
    else:
        # Build everything if no tree is provided
        trees = config.trees

    # Create config.target_folder (if not exists)
    print "Generating target folder"
    ensure_folder(config.target_folder, False)
    ensure_folder(config.temp_folder, not skip_indexing)
    ensure_folder(config.log_folder, not skip_indexing)

    jinja_env = load_template_env(config.temp_folder, config.template_folder)

    # We don't want to load config file on the server, so we just write all the
    # setting into the config.py script, simple as that.
    _fill_and_write_template(
        jinja_env,
        'config.py.jinja',
        os.path.join(config.target_folder, 'config.py'),
        dict(trees=repr([t.name for t in config.trees]),
             wwwroot=repr(config.wwwroot),
             template_parameters=repr(config.template_parameters),
             generated_date=repr(config.generated_date),
             directory_index=repr(config.directory_index)))

    # Create jinja cache folder in target folder
    ensure_folder(os.path.join(config.target_folder, 'jinja_dxr_cache'))

    # TODO Make open-search.xml things (or make the server so it can do them!)

    # Build trees requested
    ensure_folder(os.path.join(config.target_folder, 'trees'))
    for tree in trees:
        # Note starting time
        start_time = datetime.now()

        # Create folders (delete if exists)
        ensure_folder(tree.target_folder, not skip_indexing) # <config.target_folder>/<tree.name>
        ensure_folder(tree.object_folder,                    # Object folder (user defined!)
            tree.source_folder != tree.object_folder)        # Only clean if not the srcdir
        ensure_folder(tree.temp_folder,   not skip_indexing) # <config.temp_folder>/<tree.name>
                                                             # (or user defined)
        ensure_folder(tree.log_folder,    not skip_indexing) # <config.log_folder>/<tree.name>
                                                             # (or user defined)
        # Temporary folders for plugins
        ensure_folder(os.path.join(tree.temp_folder, 'plugins'), not skip_indexing)
        for plugin in tree.enabled_plugins:     # <tree.config>/plugins/<plugin>
            ensure_folder(os.path.join(tree.temp_folder, 'plugins', plugin), not skip_indexing)

        # Connect to database (exits on failure: sqlite_version, tokenizer, etc)
        conn = connect_database(tree)

        if skip_indexing:
            print " - Skipping indexing (due to 'index' in 'skip_stages')"
        else:
            # Create database tables
            create_tables(tree, conn)

            # Index all source files (for full text search)
            # Also build all folder listing while we're at it
            index_files(tree, conn)

            # Build tree
            build_tree(tree, conn, verbose)

            # Optimize and run integrity check on database
            finalize_database(conn)

            # Commit database
            conn.commit()

        if 'html' in config.skip_stages:
            print " - Skipping htmlifying (due to 'html' in 'skip_stages')"
        else:
            print "Building HTML for the '%s' tree." % tree.name

            max_file_id = conn.execute("SELECT max(files.id) FROM files").fetchone()[0]
            if config.disable_workers:
                print " - Worker pool disabled (due to 'disable_workers')"
                _build_html_for_file_ids(tree, 0, max_file_id)
            else:
                run_html_workers(tree, config, max_file_id)

        # Close connection
        conn.commit()
        conn.close()

        # Save the tree finish time
        delta = datetime.now() - start_time
        print "(finished building '%s' in %s)" % (tree.name, delta)

    # Print a neat summary


def ensure_folder(folder, clean=False):
    """Ensure the existence of a folder.

    :arg clean: Whether to ensure that the folder is empty

    """
    if clean and os.path.isdir(folder):
        shutil.rmtree(folder, False)
    if not os.path.isdir(folder):
        os.mkdir(folder)


def create_tables(tree, conn):
    print "Creating tables"
    conn.execute("CREATE VIRTUAL TABLE trg_index USING trilite")
    conn.executescript(dxr.languages.language_schema.get_create_sql())


def _unignored_folders(folders, source_path, ignore_patterns, ignore_paths):
    """Yield the folders from ``folders`` which are not ignored by the given
    patterns and paths.

    :arg source_path: Relative path to the source directory
    :arg ignore_patterns: Non-path-based globs to be ignored
    :arg ignore_paths: Path-based globs to be ignored

    """
    for folder in folders:
        if not any(fnmatchcase(folder, p) for p in ignore_patterns):
            folder_path = '/' + os.path.join(source_path, folder).replace(os.sep, '/') + '/'
            if not any(fnmatchcase(folder_path, p) for p in ignore_paths):
                yield folder


def index_files(tree, conn):
    """Build the ``files`` table, the trigram index, and the HTML folder listings."""
    print "Indexing files from the '%s' tree" % tree.name
    start_time = datetime.now()
    cur = conn.cursor()
    # Walk the directory tree top-down, this allows us to modify folders to
    # exclude folders matching an ignore_pattern
    for root, folders, files in os.walk(tree.source_folder, topdown=True):
        # Find relative path
        rel_path = os.path.relpath(root, tree.source_folder)
        if rel_path == '.':
            rel_path = ""

        # List of file we indexed (ie. add to folder listing)
        indexed_files = []
        for f in files:
            # Ignore file if it matches an ignore pattern
            if any(fnmatchcase(f, e) for e in tree.ignore_patterns):
                continue  # Ignore the file.

            # file_path and path
            file_path = os.path.join(root, f)
            path = os.path.join(rel_path, f)

            # Ignore file if its path (relative to the root) matches an ignore path
            if any(fnmatchcase("/" + path.replace(os.sep, "/"), e) for e in tree.ignore_paths):
                continue  # Ignore the file.

            # the file
            with open(file_path, "r") as source_file:
                data = source_file.read()

            # Discard non-text files
            if not dxr.mime.is_text(file_path, data):
                continue

            # Find an icon (ideally dxr.mime should use magic numbers, etc.)
            # that's why it makes sense to save this result in the database
            icon = dxr.mime.icon(path)

            # Insert this file
            cur.execute("INSERT INTO files (path, icon, encoding) VALUES (?, ?, ?)",
                        (path, icon, tree.source_encoding))
            # Index this file
            sql = "INSERT INTO trg_index (id, text) VALUES (?, ?)"
            cur.execute(sql, (cur.lastrowid, data))

            # Okay to this file was indexed
            indexed_files.append(f)

        # Exclude folders that match an ignore pattern.
        # os.walk listens to any changes we make in `folders`.
        folders[:] = _unignored_folders(
            folders, rel_path, tree.ignore_patterns, tree.ignore_paths)

        indexed_files.sort()
        folders.sort()
        # Now build folder listing and folders for indexed_files
        build_folder(tree, conn, rel_path, indexed_files, folders)

    # Okay, let's commit everything
    conn.commit()

    # Print time
    print "(finished in %s)" % (datetime.now() - start_time)


def build_folder(tree, conn, folder, indexed_files, indexed_folders):
    """Build an HTML index file for a single folder."""
    # Create the subfolder if it doesn't exist:
    ensure_folder(os.path.join(tree.target_folder, folder))

    # Build the folder listing:
    # Name is either basename (or if that is "" name of tree)
    name = os.path.basename(folder) or tree.name

    # Generate list of folders and their mod dates:
    folders = [('folder',
                f,
                datetime.fromtimestamp(stat(os.path.join(tree.source_folder,
                                                         folder,
                                                         f)).st_mtime),
                # TODO: DRY with Flask route. Use url_for:
                _join_url(tree.name, 'source', folder, f))
               for f in indexed_folders]

    # Generate list of files:
    files = []
    for f in indexed_files:
        # Get file path on disk
        path = os.path.join(tree.source_folder, folder, f)
        file_info = stat(path)
        files.append((dxr.mime.icon(path),
                      f,
                      datetime.fromtimestamp(file_info.st_mtime),
                      file_info.st_size,
                      _join_url(tree.name, 'source', folder, f)))

    # Lay down the HTML:
    jinja_env = load_template_env(tree.config.temp_folder,
                                  tree.config.template_folder)
    dst_path = os.path.join(tree.target_folder,
                            folder,
                            tree.config.directory_index)

    _fill_and_write_template(
        jinja_env,
        'folder.html',
        dst_path,
        {# Common template variables:
         'wwwroot': tree.config.wwwroot,
         'tree': tree.name,
         'trees': [t.name for t in tree.config.trees],
         'config': tree.config.template_parameters,
         'generated_date': tree.config.generated_date,
         'paths_and_names': linked_pathname(folder, tree.name),

         # Folder template variables:
         'name': name,
         'path': folder,
         'folders': folders,
         'files': files})


def _join_url(*args):
    """Join URL path segments with "/", skipping empty segments."""
    return '/'.join(a for a in args if a)


def _fill_and_write_template(jinja_env, template_name, out_path, vars):
    """Get the template `template_name` from the template folder, substitute in
    `vars`, and write the result to `out_path`."""
    template = jinja_env.get_template(template_name)
    template.stream(**vars).dump(out_path, encoding='utf-8')


def build_tree(tree, conn, verbose):
    """Build the tree, pre_process, build and post_process."""
    # Load indexers
    indexers = load_indexers(tree)

    # Get system environment variables
    environ = {}
    for key, val in os.environ.items():
        environ[key] = val

    # Let plugins preprocess
    # modify environ, change makefile, hack things whatever!
    for indexer in indexers:
        indexer.pre_process(tree, environ)

    # Add source and build directories to the command
    environ["source_folder"] = tree.source_folder
    environ["build_folder"] = tree.object_folder

    # Open log file
    with open_log(tree, 'build.log', verbose) as log:
        # Call the make command
        print "Building the '%s' tree" % tree.name
        r = subprocess.call(
            tree.build_command.replace('$jobs', tree.config.nb_jobs),
            shell   = True,
            stdout  = log,
            stderr  = log,
            env     = environ,
            cwd     = tree.object_folder
        )

    # Abort if build failed!
    if r != 0:
        print >> sys.stderr, ("Build command for '%s' failed, exited non-zero."
                              % tree.name)
        if not verbose:
            print >> sys.stderr, 'Log follows:'
            with open(log.name) as log_file:
                print >> sys.stderr, '    | %s ' % '    | '.join(log_file)
        sys.exit(1)

    # Let plugins post process
    for indexer in indexers:
        indexer.post_process(tree, conn)


def finalize_database(conn):
    """Finalize the database."""
    print "Finalize database:"

    print " - Building database statistics for query optimization"
    conn.execute("ANALYZE");

    print " - Running integrity check"
    isOkay = None
    for row in conn.execute("PRAGMA integrity_check"):
        if row[0] == "ok" and isOkay is None:
            isOkay = True
        else:
            if isOkay is not False:
                print >> sys.stderr, "Database integerity check failed"
            isOkay = False
            print >> sys.stderr, "  | %s" % row[0]
    if not isOkay:
        sys.exit(1)

    conn.commit()


def build_sections(tree, conn, path, text, htmlifiers):
    """ Build navigation sections for template """
    # Chain links from different htmlifiers
    links = chain(*(htmlifier.links() for htmlifier in htmlifiers))
    # Sort by importance (resolve tries by section name)
    links = sorted(links, key = lambda section: (section[0], section[1]))
    # Return list of section and items (without importance)
    return [(section, list(items)) for importance, section, items in links]


def _sliced_range_bounds(a, b, slice_size):
    """Divide ``range(a, b)`` into slices of size ``slice_size``, and
    return the min and max values of each slice."""
    this_min = a
    while this_min == a or this_max < b:
        this_max = min(b, this_min + slice_size - 1)
        yield this_min, this_max
        this_min = this_max + 1


def run_html_workers(tree, config, max_file_id):
    """Farm out the building of HTML to a pool of processes."""

    print ' - Initializing worker pool'

    with ProcessPoolExecutor(max_workers=int(tree.config.nb_jobs)) as pool:
        print ' - Enqueuing jobs'
        futures = [pool.submit(_build_html_for_file_ids, tree, start, end) for
                   (start, end) in _sliced_range_bounds(1, max_file_id, 500)]
        print ' - Waiting for workers to complete'
        for num_done, future in enumerate(as_completed(futures), 1):
            print '%s of %s HTML workers done.' % (num_done, len(futures))
            result = future.result()
            if result:
                formatted_tb, type, value, id, path = result
                print 'A worker failed while htmlifying %s, id=%s:' % (path, id)
                print formatted_tb
                # Abort everything if anything fails:
                raise type, value  # exits with non-zero


def _build_html_for_file_ids(tree, start, end):
    """Write HTML files for file IDs from ``start`` to ``end``. Return None if
    all goes well, a tuple of (stringified exception, exc type, exc value, file
    ID, file path) if something goes wrong while htmlifying a file.

    This is the top-level function of an HTML worker process. Log progress to a
    file named "build-html-<start>-<end>.log".

    """
    path = '(no file yet)'
    id = -1
    try:
        # We might as well have this write its log directly rather than returning
        # them to the master process, since it's already writing the built HTML
        # directly, since that probably yields better parallelism.

        conn = connect_database(tree)
        # TODO: Replace this ad hoc logging with the logging module (or something
        # more humane) so we can get some automatic timestamps. If we get
        # timestamps spit out in the parent process, we don't need any of the
        # timing or counting code here.
        with open_log(tree, 'build-html-%s-%s.log' % (start, end)) as log:
            # Load htmlifier plugins:
            plugins = load_htmlifiers(tree)
            for plugin in plugins:
                plugin.load(tree, conn)

            start_time = datetime.now()

            # Fetch and htmlify each document:
            for num_files, (id, path, icon, text) in enumerate(
                    conn.execute("""
                                 SELECT files.id, path, icon, trg_index.text
                                 FROM trg_index, files
                                 WHERE trg_index.id = files.id
                                 AND trg_index.id >= ?
                                 AND trg_index.id <= ?
                                 """,
                                 [start, end]),
                    1):
                dst_path = os.path.join(tree.target_folder, path + '.html')
                log.write('Starting %s.\n' % path)
                htmlify(tree, conn, icon, path, text, dst_path, plugins)

            conn.commit()
            conn.close()

            # Write time information:
            time = datetime.now() - start_time
            log.write('Finished %s files in %s.\n' % (num_files, time))
    except Exception as exc:
        type, value, traceback = exc_info()
        return format_exc(), type, value, id, path


def htmlify(tree, conn, icon, path, text, dst_path, plugins):
    """ Build HTML for path, text save it to dst_path """
    # Create htmlifiers for this source
    htmlifiers = []
    for plugin in plugins:
        htmlifier = plugin.htmlify(path, text)
        if htmlifier:
            htmlifiers.append(htmlifier)
    # Load template
    env = load_template_env(tree.config.temp_folder,
                            tree.config.template_folder)

    arguments = {
        # Set common template variables
        'wwwroot': tree.config.wwwroot,
        'tree': tree.name,
        'trees': [t.name for t in tree.config.trees],
        'config': tree.config.template_parameters,
        'generated_date': tree.config.generated_date,

        # Set file template variables
        'paths_and_names': linked_pathname(path, tree.name),
        'icon': icon,
        'path': path,
        'name': os.path.basename(path),

        # Someday, it would be great to stream this and not concretize the
        # whole thing in RAM. The template will have to quit looping through
        # the whole thing 3 times.
        'lines': list(lines_and_annotations(build_lines(text, htmlifiers,
                                                        tree.source_encoding),
                                            htmlifiers)),

        'sections': build_sections(tree, conn, path, text, htmlifiers)
    }

    _fill_and_write_template(env, 'file.html', dst_path, arguments)


class Line(object):
    """Representation of a line's beginning and ending as the contents of a tag

    Exists to motivate the balancing machinery to close all the tags at the end
    of every line (and reopen any afterward that span lines).

    """
    sort_order = 0  # Sort Lines outermost.
    def __repr__(self):
        return 'Line()'

LINE = Line()


class TagWriter(object):
    """A thing that hangs onto a tag's payload (like the class of a span) and
    knows how to write its opening and closing tags"""

    def __init__(self, payload):
        self.payload = payload

    # __repr__ comes in handy for debugging.
    def __repr__(self):
        return '%s("%s")' % (self.__class__.__name__, self.payload)


class Region(TagWriter):
    """Thing to open and close <span> tags"""
    sort_order = 2  # Sort Regions innermost, as it doesn't matter if we split
                    # them.

    def opener(self):
        return u'<span class="%s">' % cgi.escape(self.payload, True)

    def closer(self):
        return u'</span>'


class Ref(TagWriter):
    """Thing to open and close <a> tags"""
    sort_order = 1

    def opener(self):
        menu, qualname, value = self.payload
        menu = cgi.escape(json.dumps(menu), True)
        css_class = ''
        if qualname:
            css_class = ' class=\"tok' + str(hash(qualname)) +'\"'
        title = ''
        if value:
            title = ' title="' + cgi.escape(value, True) + '"'
        return u'<a data-menu="%s"%s%s>' % (menu, css_class, title)

    def closer(self):
        return u'</a>'


def html_lines(tags, slicer):
    """Render tags to HTML, and interleave them with the text they decorate.

    :arg tags: An iterable of ordered, non-overlapping, non-empty tag
        boundaries with Line endpoints at (and outermost at) the index of the
        end of each line.
    :arg slicer: A callable taking the args (start, end), returning a Unicode
        slice of the source code we're decorating. ``start`` and ``end`` are
        Python-style slice args.

    """
    up_to = 0
    segments = []

    for point, is_start, payload in tags:
        segments.append(cgi.escape(slicer(up_to, point).strip(u'\r\n')))
        up_to = point
        if payload is LINE:
            if not is_start and segments:
                yield Markup(u''.join(segments))
                segments = []

        else:
            segments.append(payload.opener() if is_start else payload.closer())


def balanced_tags(tags):
    """Come up with a balanced series of tags which express the semantics of
    the given sorted interleaved ones.

    Return an iterable of (point, is_start, Region/Reg/Line) without any
    (pointless) zero-width tag spans. The output isn't necessarily optimal, but
    it's fast and not embarrassingly wasteful of space.

    """
    return without_empty_tags(balanced_tags_with_empties(tags))


def without_empty_tags(tags):
    """Filter zero-width tagged spans out of a sorted, balanced tag stream.

    Maintain tag order. Line break tags are considered self-closing.

    """
    buffer = []  # tags
    depth = 0

    for tag in tags:
        point, is_start, payload = tag

        if is_start:
            buffer.append(tag)
            depth += 1
        else:
            top_point, _, top_payload = buffer[-1]
            if top_payload is payload and top_point == point:
                # It's a closer, and it matches the last thing in buffer and, it
                # and that open tag form a zero-width span. Cancel the last thing
                # in buffer.
                buffer.pop()
            else:
                # It's an end tag that actually encloses some stuff.
                buffer.append(tag)
            depth -= 1

            # If we have a balanced set of non-zero-width tags, emit them:
            if not depth:
                for b in buffer:
                    yield b
                del buffer[:]


def balanced_tags_with_empties(tags):
    """Come up with a balanced series of tags which express the semantics of
    the given sorted interleaved ones.

    Return an iterable of (point, is_start, Region/Reg/Line), possibly
    including some zero-width tag spans. Each line is enclosed within Line tags.

    :arg tags: An iterable of (offset, is_start, payload) tuples, with one
        closer for each opener but possibly interleaved. There is one tag for
        each line break, with a payload of LINE and an is_start of False. Tags
        are ordered with closers first, then line breaks, then openers.

    """
    def close(to=None):
        """Return an iterable of closers for open tags up to (but not
        including) the one with the payload ``to``."""
        # Loop until empty (if we're not going "to" anything in particular) or
        # until the corresponding opener is at the top of the stack. We check
        # that "to is None" just to surface any stack-tracking bugs that would
        # otherwise cause opens to empty too soon.
        while opens if to is None else opens[-1] is not to:
            intermediate_payload = opens.pop()
            yield point, False, intermediate_payload
            closes.append(intermediate_payload)

    def reopen():
        """Yield open tags for all temporarily closed ones."""
        while closes:
            intermediate_payload = closes.pop()
            yield point, True, intermediate_payload
            opens.append(intermediate_payload)

    opens = []  # payloads of tags which are currently open
    closes = []  # payloads of tags which we've had to temporarily close so we could close an overlapping tag
    point = 0

    yield 0, True, LINE
    for point, is_start, payload in tags:
        if is_start:
            yield point, is_start, payload
            opens.append(payload)
        elif payload is LINE:
            # Close all open tags before a line break (since each line is
            # wrapped in its own <code> tag pair), and reopen them afterward.
            for t in close():  # I really miss "yield from".
                yield t

            # Since preserving self-closing linebreaks would throw off
            # without_empty_tags(), we convert to explicit closers here. We
            # surround each line with them because empty balanced ones would
            # get filtered out.
            yield point, False, LINE
            yield point, True, LINE

            for t in reopen():
                yield t
        else:
            # Temporarily close whatever's been opened between the start tag of
            # the thing we're trying to close and here:
            for t in close(to=payload):
                yield t

            # Close the current tag:
            yield point, False, payload
            opens.pop()

            # Reopen the temporarily closed ones:
            for t in reopen():
                yield t
    yield point, False, LINE


def tag_boundaries(htmlifiers):
    """Return a sequence of (offset, is_start, Region/Ref/Line) tuples.

    Basically, split the atomic tags that come out of plugins into separate
    start and end points, which can then be thrown together in a bag and sorted
    as the first step in the tag-balancing process.

    Like in Python slice notation, the offset of a tag refers to the index of
    the source code char it comes before.

    """
    for h in htmlifiers:
        for intervals, cls in [(h.regions(), Region), (h.refs(), Ref)]:
            for start, end, data in intervals:
                tag = cls(data)
                # Filter out zero-length spans which don't do any good and
                # which can cause starts to sort after ends, crashing the tag
                # balancer. Incidentally filter out spans where start tags come
                # after end tags, though that should never happen.
                #
                # Also filter out None starts and ends. I don't know where they
                # come from. That shouldn't happen and should be fixed in the
                # plugins.
                if start is not None and end is not None and start < end:
                    yield start, True, tag
                    yield end, False, tag


def line_boundaries(text):
    """Return a tag for the end of each line in a string.

    :arg text: A UTF-8-encoded string

    Endpoints and start points are coincident: right after a (universal)
    newline.

    """
    up_to = 0
    for line in text.splitlines(True):
        up_to += len(line)
        yield up_to, False, LINE


def non_overlapping_refs(tags):
    """Yield a False for each Ref in ``tags`` that overlaps a subsequent one,
    a True for the rest.

    Assumes the incoming tags, while not necessarily well balanced, have the
    start tag come before the end tag, if both are present. (Lines are weird.)

    """
    blacklist = set()
    open_ref = None
    for point, is_start, payload in tags:
        if isinstance(payload, Ref):
            if payload in blacklist:  # It's the evil close tag of a misnested tag.
                blacklist.remove(payload)
                yield False
            elif open_ref is None:  # and is_start: (should always be true if input is sane)
                assert is_start
                open_ref = payload
                yield True
            elif open_ref is payload:  # it's the closer
                open_ref = None
                yield True
            else:  # It's an evil open tag of a misnested tag.
                warn('htmlifier plugins requested overlapping <a> tags. Fix the plugins.')
                blacklist.add(payload)
                yield False
        else:
            yield True


def remove_overlapping_refs(tags):
    """For any series of <a> tags that overlap each other, filter out all but
    the first.

    There's no decent way to represent that sort of thing in the UI, so we
    don't support it.

    :arg tags: A list of (point, is_start, payload) tuples, sorted by point.
        The tags do not need to be properly balanced.

    """
    # Reuse the list so we don't use any more memory.
    i = None
    for i, tag in enumerate(compress(tags, non_overlapping_refs(tags))):
        tags[i] = tag
    if i is not None:
        del tags[i + 1:]


def nesting_order((point, is_start, payload)):
    """Return a sorting key that places coincident Line boundaries outermost,
    then Ref boundaries, and finally Region boundaries.

    The Line bit saves some empty-tag elimination. The Ref bit saves splitting
    an <a> tag (and the attendant weird UI) for the following case::

        Ref    ____________  # The Ref should go on the outside.
        Region _____

    Other scenarios::

        Reg _______________        # Would be nice if Reg ended before Ref
        Ref      ________________  # started. We'll see about this later.

        Reg _____________________  # Works either way
        Ref _______

        Reg _____________________
        Ref               _______  # This should be fine.

        Reg         _____________  # This should be fine as well.
        Ref ____________

        Reg _____
        Ref _____  # This is fine either way.

    Also, endpoints sort before coincident start points to save work for the
    tag balancer.

    """
    return point, is_start, (payload.sort_order if is_start else
                             -payload.sort_order)


def build_lines(text, htmlifiers, encoding='utf-8'):
    """Yield lines of Markup, with decorations from the htmlifier plugins
    applied.

    :arg text: UTF-8-encoded string. (In practice, this is not true if the
        input file wasn't UTF-8. We should make it true.)

    """
    decoder = getdecoder(encoding)
    def decoded_slice(start, end):
        return decoder(text[start:end], errors='replace')[0]

    # For now, we make the same assumption the old build_lines() implementation
    # did, just so we can ship: plugins return byte offsets, not Unicode char
    # offsets. However, I think only the clang plugin returns byte offsets. I
    # bet Pygments returns char ones. We should homogenize one way or the
    # other.
    tags = list(tag_boundaries(htmlifiers))  # start and endpoints of intervals
    tags.extend(line_boundaries(text))
    tags.sort(key=nesting_order)  # Balanced_tags undoes this, but we tolerate
                                  # that in html_lines().
    remove_overlapping_refs(tags)
    return html_lines(balanced_tags(tags), decoded_slice)


def lines_and_annotations(lines, htmlifiers):
    """Collect all the annotations for each line into a list, and yield a tuple
    of (line of HTML, annotations list) for each line.

    :arg lines: An iterable of Markup objects, each representing a line of
        HTMLified source code

    """
    def non_sparse_annotations(annotations):
        """De-sparsify the annotations iterable so we can just zip it together
        with the HTML lines.

        Return an iterable of annotations iterables, one for each line.

        """
        next_unannotated_line = 0
        for line, annotations in groupby(annotations, itemgetter(0)):
            for next_unannotated_line in xrange(next_unannotated_line,
                                                line - 1):
                yield []
            yield [data for line_num, data in annotations]
            next_unannotated_line = line
    return izip_longest(lines,
                        non_sparse_annotations(merge(*[h.annotations() for h in
                                                       htmlifiers])),
                        fillvalue=[])
