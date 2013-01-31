from datetime import datetime
import fnmatch
import os
from os import stat
from os.path import dirname
from pkg_resources import require
import shutil
import subprocess
import sys

import dxr.utils
import dxr.plugins
import dxr.languages
import dxr.mime


def build(config_path, nb_jobs=None, tree=None):
    """Build a DXR instance.

    :arg config_path: The path to a config file
    :arg nb_jobs: The number of parallel jobs to pass into ``make``. Overrides
        any such value specified in the config file.
    :arg tree: A single tree to build. Useful in cases where the config file
        specifies multiple trees.

    """
    # Load configuration file
    # (this will abort on inconsistencies)
    overrides = {}
    if nb_jobs:
        overrides['nb_jobs'] = nb_jobs
    config = dxr.utils.Config(config_path, **overrides)

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

    # We don't want to load config file on the server, so we just write all the
    # setting into the config.py script, simple as that.
    _fill_and_write_template(
        config,
        'config.py',
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
        config,
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
        started = datetime.now()

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
        conn = dxr.utils.connect_database(tree)

        # Create database tables
        create_tables(tree, conn)

        # Index all source files (for full text search)
        # Also build all folder listing while we're at it
        index_files(tree, conn)

        # Build tree
        build_tree(tree, conn)

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
        delta = datetime.now() - started
        print "(finished building '%s' in %s)" % (tree.name, delta)

    # Print a neat summary


def ensure_folder(folder, clean=False):
    """ Ensures the existence of a folder, if clean is true also ensures that it's empty"""
    if clean and os.path.isdir(folder):
        shutil.rmtree(folder, False)
    if not os.path.isdir(folder):
        os.mkdir(folder)


def create_tables(tree, conn):
    print "Creating tables"
    conn.execute("CREATE VIRTUAL TABLE trg_index USING trilite")
    conn.executescript(dxr.languages.language_schema.get_create_sql())


def index_files(tree, conn):
    """ Index all files from the source directory """
    print "Indexing files from the '%s' tree" % tree.name
    started = datetime.now()
    cur = conn.cursor()
    # Walk the directory tree top-down, this allows us to modify folders to
    # exclude folders matching an ignore_pattern
    for root, folders, files in os.walk(tree.source_folder, True):
        # Find relative path
        rel_path = os.path.relpath(root, tree.source_folder)
        if rel_path == '.':
            rel_path = ""

        # List of file we indexed (ie. add to folder listing)
        indexed_files = []
        for f in files:
            # Ignore file if it matches an ignore pattern
            if any((fnmatch.fnmatchcase(f, e) for e in tree.ignore_patterns)):
                continue # Ignore the file

            # file_path and path
            file_path = os.path.join(root, f)
            path = os.path.join(rel_path, f)

            # Ignore file if its path (relative to the root) matches an ignore path
            if any((fnmatch.fnmatchcase("/" + path.replace(os.sep, "/"), e) for e in tree.ignore_paths)):
                continue # Ignore the file

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

        # Exclude folders that match an ignore pattern
        # (The top-down walk allows us to do this)
        for folder in folders:
            if any((fnmatch.fnmatchcase(folder, e) for e in tree.ignore_patterns)):
                folders.remove(folder)
            else:
                folder_relpath = "/" + os.path.join(rel_path, folder).replace(os.sep, "/") + "/"
                if any((fnmatch.fnmatchcase(folder_relpath, e) for e in tree.ignore_paths)):
                    folders.remove(folder)

        # Now build folder listing and folders for indexed_files
        build_folder(tree, conn, rel_path, indexed_files, folders)

    # Okay, let's commit everything
    conn.commit()

    # Print time
    print "(finished in %s)" % (datetime.now() - started)


def build_folder(tree, conn, folder, indexed_files, indexed_folders):
    """Build folders and folder listings."""
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
                            _join_url(tree.name, folder, f))
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
                                    _join_url(tree.name, folder, f)))

    # Lay down the HTML:
    dst_path = os.path.join(tree.target_folder,
                                                    folder,
                                                    tree.config.directory_index)
    _fill_and_write_template(
        tree.config,
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


def _fill_and_write_template(config, template_name, out_path, vars):
    """Get the template `template_name` from the template folder, substitute in
    `vars`, and write the result to `out_path`."""
    env = dxr.utils.load_template_env(config)
    template = env.get_template(template_name)
    template.stream(**vars).dump(out_path, encoding='utf-8')


def build_tree(tree, conn):
    """ Build the tree, pre_process, build and post_process """
    # Load indexers
    indexers = dxr.plugins.load_indexers(tree)

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
    log = dxr.utils.open_log(tree, "build.log")

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

    # Close log file
    log.close()

    # Abort if build failed!
    if r != 0:
        msg = "Build command for '%s' failed, exited non-zero! Log follows:"
        print >> sys.stderr, msg % tree.name
        with open(log.name) as log_file:
            print >> sys.stderr, '    | %s ' % '    | '.join(log_file)
        sys.exit(1)

    # Let plugins post process
    for indexer in indexers:
        indexer.post_process(tree, conn)


def finalize_database(conn):
    """ Finalize the database """
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


def run_html_workers(tree, conn):
    """ Build HTML for a tree """
    print "Building HTML for the '%s' tree" % tree.name

    # Let's find the number of rows, this is the maximum rowid, assume we didn't
    # delete files, this assumption should hold, but even if we delete files, it's
    # fairly like that this partition the work reasonably evenly.
    sql = "SELECT files.ID FROM files ORDER BY files.ID DESC LIMIT 1"
    row = conn.execute(sql).fetchone()
    file_count = row[0]

    # Make some slices
    slices = []
    # Don't make slices bigger than 500
    step = min(500, int(file_count) / int(tree.config.nb_jobs))
    start = None    # None, is not --start argument
    for end in xrange(step, file_count, step):
        slices.append((start, end))
        start = end + 1
    slices.append((start, None))  # None, means omit --end argument

    # Map from pid to workers
    workers = {}
    next_id = 1   # unique ids for workers, to associate log files

    # Get the correct path to dxr-worker.py, whether dxr is installed or linked
    # as a development egg:
    dxr_worker_path = os.path.join(require('dxr')[0].egg_info,
                                   'scripts',
                                   'dxr-worker.py')

    # While there's slices and workers, we can manage them
    while len(slices) > 0 or len(workers) > 0:

        # Create workers while we have slots available
        while len(workers) < int(tree.config.nb_jobs) and len(slices) > 0:
            # Get slice of work
            start, end = slices.pop()
            # Setup arguments
            args = ['--file', tree.config.configfile, '--tree', tree.name]
            if start is not None:
                args += ['--start', str(start)]
            if end is not None:
                args += ['--end', str(end)]
            # Open log file
            log = dxr.utils.open_log(tree, "dxr-worker-%s.log" % next_id)
            # Create a worker
            print " - Starting worker %i" % next_id
            cmd = [dxr_worker_path] + args
            # Write command to log
            log.write(" ".join(cmd) + "\n")
            log.flush()
            worker = subprocess.Popen(
                cmd,
                stdout = log,
                stderr = log
            )
            # Add worker
            workers[worker.pid] = (worker, log, datetime.now(), next_id)
            next_id += 1

        # Wait for a subprocess to terminate
        pid, exit = os.waitpid(0, 0)
        # Find worker that terminated
        worker, log, started, wid = workers[pid]
        print " - Worker %i finished in %s" % (wid, datetime.now() - started)
        # Remove from workers
        del workers[pid]
        # Close log file
        log.close()
        # Crash and error if we have problems
        if exit != 0:
            print >> sys.stderr, "dxr-worker.py subprocess failed!"
            print >> sys.stderr, "    | Log from %s:" % log.name
            # Print log for easy debugging
            with open(log.name, 'r') as log:
                for line in log:
                    print >> sys.stderr, "    | " + line.strip('\n')
            # Kill co-workers
            for worker, log, started, wid in workers.values():
                worker.kill()
                log.close()
            # Exit, we're done here
            sys.exit(1)
