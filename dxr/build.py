from codecs import getdecoder
import cgi
from datetime import datetime
from fnmatch import fnmatchcase
from itertools import chain, izip
import json
import os
from os import stat
from os.path import dirname
from pkg_resources import require
import shutil
import subprocess
import sys

from concurrent.futures import as_completed, ProcessPoolExecutor

from dxr.config import Config
from dxr.plugins import load_htmlifiers, load_indexers
import dxr.languages
import dxr.mime
from dxr.utils import load_template_env, connect_database, open_log


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
    ensure_folder(config.temp_folder, True)
    ensure_folder(config.log_folder, True)

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

    # Build root-level index.html:
    ensure_folder(os.path.join(config.target_folder, 'trees'))
    _fill_and_write_template(
        jinja_env,
        'index.html',
        os.path.join(config.target_folder, 'trees', 'index.html'),
        {'wwwroot': config.wwwroot,
          'tree': config.trees[0].name,
          'trees': [t.name for t in config.trees],
          'config': config.template_parameters,
          'generated_date': config.generated_date})
    # TODO Make open-search.xml things (or make the server so it can do them!)

    # Build trees requested
    for tree in trees:
        # Note starting time
        start_time = datetime.now()

        # Create folders (delete if exists)
        ensure_folder(tree.target_folder, True) # <config.target_folder>/<tree.name>
        ensure_folder(tree.object_folder,       # Object folder (user defined!)
            tree.source_folder != tree.object_folder) # Only clean if not the srcdir
        ensure_folder(tree.temp_folder,   True) # <config.temp_folder>/<tree.name>
                                                # (or user defined)
        ensure_folder(tree.log_folder,    True) # <config.log_folder>/<tree.name>
                                                # (or user defined)
        # Temporary folders for plugins
        ensure_folder(os.path.join(tree.temp_folder, 'plugins'), True)
        for plugin in tree.enabled_plugins:     # <tree.config>/plugins/<plugin>
            ensure_folder(os.path.join(tree.temp_folder, 'plugins', plugin), True)

        # Connect to database (exits on failure: sqlite_version, tokenizer, etc)
        conn = connect_database(tree)

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

        # Build html
        run_html_workers(tree, conn)

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
            cur.execute("INSERT INTO files (path, icon) VALUES (?, ?)", (path, icon))
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
          'wwwroot':        tree.config.wwwroot,
          'tree':           tree.name,
          'trees':          [t.name for t in tree.config.trees],
          'config':         tree.config.template_parameters,
          'generated_date': tree.config.generated_date,

          # Folder template variables:
          'name':           name,
          'path':           folder,
          'folders':        folders,
          'files':          files})


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
    with open_log(tree, "build.log", verbose) as log:
        # Call the make command
        print "Building the '%s' tree" % tree.name
        r = subprocess.call(
            tree.build_command.replace("$jobs", tree.config.nb_jobs),
            shell   = True,
            stdout  = log,
            stderr  = log,
            env     = environ,
            cwd     = tree.object_folder
        )

    # Abort if build failed!
    if r != 0:
        if verbose:
            msg = "Build command for '%s' failed, exited non-zero!"
        else:
            msg = "Build command for '%s' failed, exited non-zero! Log follows:"
        print >> sys.stderr, msg % tree.name
        if verbose:
            with open(log.name) as log_file:
                print >> sys.stderr, '    | %s ' % '    | '.join(log_file)
        sys.exit(1)

    # Let plugins post process
    for indexer in indexers:
        indexer.post_process(tree, conn)


def finalize_database(conn):
    """Finalize the database."""
    print "Finalize database:"

    print " - Build database statistics for query optimization"
    conn.execute("ANALYZE");

    print " - Running integrity check"
    isOkay = None
    for row in conn.execute("PRAGMA integrity_check"):
        if row[0] == "ok" and isOkay is None:
            isOkay = True
        else:
            if isOkay is not False:
                print >> sys.stderr, "Database, integerity-check failed"
            isOkay = False
            print >> sys.stderr, "  | %s" % row[0]
    if not isOkay:
        sys.exit(1)

    conn.commit()


def _sliced_range_bounds(a, b, slice_size):
    """Divide ``range(a, b)`` into slices of size ``slice_size``, and
    return the min and max values of each slice."""
    this_min = a
    while this_min == a or this_max < b:
        this_max = min(b, this_min + slice_size - 1)
        yield this_min, this_max
        this_min = this_max + 1


def run_html_workers(tree, conn):
    """Farm out the building of HTML to a pool of processes."""
    print "Building HTML for the '%s' tree." % tree.name

    max_file_id = conn.execute("SELECT max(files.id) FROM files").fetchone()[0]

    with ProcessPoolExecutor(max_workers=int(tree.config.nb_jobs)) as pool:
        futures = [pool.submit(_build_html_for_file_ids, tree, start, end) for
                   (start, end) in _sliced_range_bounds(1, max_file_id, 500)]
        for num_done, future in enumerate(as_completed(futures), 1):
            print '%s of %s HTML workers done.' % (num_done, len(futures))
            try:
                start, end = future.result()  # raises exc if failed
            except Exception:
                print 'Worker working on files %s-%s failed.' % (start, end)
                # Abort everything if anything fails:
                raise  # exits with non-zero


def _build_html_for_file_ids(tree, start, end):
    """Write HTML files for file IDs from ``start`` to ``end``. Return
    ``(start, end)``.

    This is the top-level function of an HTML worker process. Log progress to a
    file named "build-html-<start>-<end>.log".

    """
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
        for num_files, (path, icon, text) in enumerate(
                conn.execute("""
                             SELECT path, icon, trg_index.text
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
    return start, end


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
    tmpl = env.get_template('file.html')
    arguments = {
        # Set common template variables
        'wwwroot':        tree.config.wwwroot,
        'tree':           tree.name,
        'trees':          [t.name for t in tree.config.trees],
        'config':         tree.config.template_parameters,
        'generated_date': tree.config.generated_date,
        # Set file template variables
        'icon':           icon,
        'path':           path,
        'name':           os.path.basename(path),
        'lines':          build_lines(tree, conn, path, text, htmlifiers),
        'sections':       build_sections(tree, conn, path, text, htmlifiers)
    }
    # Fill-in variables and dump to file with utf-8 encoding
    tmpl.stream(**arguments).dump(dst_path, encoding='utf-8')


def build_lines(tree, conn, path, text, htmlifiers):
    """ Build lines for template """
    # Empty files, have no lines
    if len(text) == 0:
        return []

    # Get a decoder
    decoder = getdecoder("utf-8")
    # Let's defined a simple way to fetch and decode a slice of source
    def src(start, end = None):
        if isinstance(start, tuple):
            start, end = start[:2]
        return decoder(text[start:end], errors = 'replace')[0]
    # We shall decode on-the-fly because we need ascii offsets to do the rendering
    # of regions correctly. But before we stuff anything into the template engine
    # we must ensure that it's correct utf-8 encoded string
    # Yes, we just have to hope that plugin designer don't give us a region that
    # splits a unicode character in two. But what else can we do?
    # (Unless we want to make plugins deal with this mess)

    # Build a line map over the source (without exploding it all over the place!)
    line_map = [0]
    offset = text.find("\n", 0) + 1
    while offset > 0:
        line_map.append(offset)
        offset = text.find("\n", offset) + 1
    # If we don't have a line ending at the end improvise one
    if not text.endswith("\n"):
        line_map.append(len(text))

    # So, we have a minor issue with writing out the main body. Some of our
    # information is (line, col) information and others is file offset. Also,
    # we don't necessarily have the information in sorted order.

    regions = chain(*(htmlifier.regions()     for htmlifier in htmlifiers))
    refs    = chain(*(htmlifier.refs()        for htmlifier in htmlifiers))
    notes   = chain(*(htmlifier.annotations() for htmlifier in htmlifiers))

    # Quickly sort the line annotations in reverse order
    # so we can view it as a stack we just pop annotations off as we generate lines
    notes   = sorted(notes, reverse = True)

    # start and end, may be either a number (extent) or a tuple of (line, col)
    # we shall normalize this, and sort according to extent
    # This is the fastest way to apply everything...
    def normalize(region):
        start, end, data = region
        if end < start:
            # Regions like this happens when you implement your own operator, ie. &=
            # apparently the cxx-lang plugin doesn't provide and end for these
            # operators. Why don't know, also I don't know if it can supply this...
            # It's a ref regions...
            # TODO Make a NaziHtmlifierConsumer to complain about stuff like this
            return (start, start + 1, data)
        if isinstance(start, tuple):
            line1, col1 = start
            line2, col2 = end
            start = line_map[line1 - 1] + col1 - 1
            end   = line_map[line2 - 1] + col2 - 1
            return start, end, data
        return region
    # Add sanitizer to remove regions that have None as offsets
    # They are just stupid and shouldn't be there in the first place!
    sane    = lambda (start, end, data): start is not None and end is not None
    regions = (normalize(region) for region in regions if sane(region))
    refs    = (normalize(region) for region in refs    if sane(region))
    # That's it we've normalized this mess, so let's just sort it too
    order   = lambda (start, end, data): (- start, end, data)
    regions = sorted(regions, key = order)
    refs    = sorted(refs,    key = order)
    # Notice that we negate start, larges start first and ties resolved with
    # smallest end. This way be can pop values of the regions in the order
    # they occur...

    # Now we create two stacks to keep track of open regions
    regions_stack = []
    refs_stack    = []

    # Open/close refs, quite simple
    def open_ref(ref):
        start, end, menu = ref
        # JSON dump the menu and escape it for quotes, etc
        menu = cgi.escape(json.dumps(menu), True)
        return "<a data-menu=\"%s\">" % menu
    def close_ref(ref):
        return "</a>"

    # Functions for opening the stack of syntax regions
    # this essential amounts to a span with a set of classes
    def open_regions():
        if len(regions_stack) > 0:
            classes = (data for start, end, data in regions_stack)
            return "<span class=\"%s\">" % " ".join(classes)
        return ""
    def close_regions():
        if len(regions_stack) > 0:
            return "</span>"
        return ""

    lines          = []
    offset         = 0
    line_number    = 0
    while offset < len(text):
        # Start a new line
        line_number += 1
        line = ""
        # Open all refs on the stack
        for ref in refs_stack:
            line += open_ref(ref)
        # We open regions after refs, because they can be opened and closed
        # without any effect, ie. inserting <b></b> has no effect...
        line += open_regions()

        # Append to line while we're still one it
        while offset < line_map[line_number]:
            # Find next offset as smallest candidate offset
            # Notice that we never go longer than to end of line
            next = line_map[line_number]
            # Next offset can be the next start of something
            if len(regions) > 0:
                next = min(next, regions[-1][0])
            if len(refs) > 0:
                next = min(next, refs[-1][0])
            # Next offset can be the end of something we've opened
            # notice, stack structure and sorting ensure that we only need test top
            if len(regions_stack) > 0:
                next = min(next, regions_stack[-1][1])
            if len(refs_stack) > 0:
                next = min(next, refs_stack[-1][1])

            # Output the source text from last offset to next
            if next < line_map[line_number]:
                line += cgi.escape(src(offset, next))
            else:
                # Throw away newline if at end of line
                line += cgi.escape(src(offset, next - 1))
            offset = next

            # Close regions, modify stack and open them again
            # this makes sense even if there's not change to the stack
            # as we can't have syntax tags crossing refs tags
            line += close_regions()
            while len(regions_stack) > 0 and regions_stack[-1][1] <= next:
                regions_stack.pop()
            while len(regions) > 0 and regions[-1][0] <= next:
                region = regions.pop()
                # Search for the right place in the stack to insert this
                # The stack is ordered s.t. we have longest end at the bottom
                # (with respect to pop())
                for i in xrange(0, len(regions_stack) + 1):
                    if len(regions_stack) == i or regions_stack[i][1] < region[1]:
                        break
                regions_stack.insert(i, region)
            # Open regions, if not at end of line
            if next < line_map[line_number]:
                line += open_regions()

            # Close and pop refs that end here
            while len(refs_stack) > 0 and refs_stack[-1][1] <= next:
                line += close_ref(refs_stack.pop())
            # Close remaining if at end of line
            if next < line_map[line_number]:
                for ref in reversed(refs_stack):
                    line += close_ref(ref)
            # Open and pop/push refs that start here
            while len(refs) > 0 and refs[-1][0] <= next:
                ref = refs.pop()
                # If the ref doesn't end before the top of the stack, we have
                # overlapping regions, this isn't good, so we discard this ref
                if len(refs_stack) > 0 and refs_stack[-1][1] < ref[1]:
                    stack_src = text[refs_stack[-1][0]:refs_stack[-1][1]]
                    print >> sys.stderr, "Error: Ref region overlap"
                    print >> sys.stderr, "   > '%s' %r" % (text[ref[0]:ref[1]], ref)
                    print >> sys.stderr, "   > '%s' %r" % (stack_src, refs_stack[-1])
                    print >> sys.stderr, "   > IN %s" % path
                    continue  # Okay so skip it
                # Open ref, if not at end of line
                if next < line_map[line_number]:
                    line += open_ref(ref)
                refs_stack.append(ref)

        # Okay let's pop line annotations of the notes stack
        current_notes = []
        while len(notes) > 0 and notes[-1][0] == line_number:
            current_notes.append(notes.pop()[1])

        lines.append((line_number, line, current_notes))
    # Return all lines of the file, as we're done
    return lines


def build_sections(tree, conn, path, text, htmlifiers):
    """ Build navigation sections for template """
    # Chain links from different htmlifiers
    links = chain(*(htmlifier.links() for htmlifier in htmlifiers))
    # Sort by importance (resolve tries by section name)
    links = sorted(links, key = lambda section: (section[0], section[1]))
    # Return list of section and items (without importance)
    return [(section, list(items)) for importance, section, items in links]
