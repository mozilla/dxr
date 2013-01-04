#!/usr/bin/env python2

from datetime import datetime
import fnmatch
import getopt
import os
import shutil
import sqlite3
import string
import subprocess, select
import sys
import time

import dxr
import dxr.utils
import dxr.plugins
import dxr.languages
import dxr.mime

def main(argv):
  # Help me figure out why Jenkins can't see trilite:
  print 'LD_LIBRARY_PATH:', os.environ.get('LD_LIBRARY_PATH', 'no LD_LIBRARY_PATH')

  # Options to read
  configfile  = None
  nb_jobs     = None # Allow us to overwrite config
  tree        = None
  make_server = False

  # Parse arguments
  try:
    params = ["help", "file=", "tree=", "jobs=", "server"]
    options, args = getopt.getopt(argv, "hf:t:j:s", params)
  except getopt.GetoptError:
    print >> sys.stderr, "Failed to parse options"
    print_usage()
    sys.exit(1)
  for arg, opt in options:
    if arg in ('-f', '--file'):
      if not configfile:
        configfile = opt
      else:
        print >> sys.stderr, "Only one config file can be provided"
        sys.exit(1)
    elif arg in ('-h', '--help'):
      print_help()
      sys.exit(0)
    elif arg in ('-t', '--tree'):
      if tree is not None:
        print >> sys.stderr, "More than one tree option is provided!"
        sys.exit(1)
      tree = opt
    elif arg in ('-j', '--jobs'):
      nb_jobs = opt
    elif arg in ('-s', '--server'):
      make_server = True
    else:
      print >> sys.stderr, "Unknown option '%s'" % arg
      print_usage()
      sys.exit(1)

  # Complain if conflicting --tree and --server arguments
  if tree and make_server:
    print >> sys.stderr, "Can't combine --tree and --server arguments"
    sys.exit(1)

  # Abort if we didn't get a config file
  if not configfile:
    print_usage()
    sys.exit(1)

  # Load configuration file
  # (this will abort on inconsistencies)
  overrides = {}
  if nb_jobs:
    overrides['nb_jobs'] = nb_jobs
  config = dxr.utils.Config(configfile, **overrides)

  # Find trees to make, fail if requested tree isn't available
  if tree:
    trees = [t for t in config.trees if t.name == tree]
    if len(trees) == 0:
      print >> sys.stderr, "Tree '%s' is not defined in config file!" % tree
      sys.exit(1)
  elif not make_server:
    # Build everything if no tree or action is provided
    trees = config.trees
    make_server = True
  else:
    trees = []

  # Create config.target_folder (if not exists)
  ensure_folder(config.target_folder, False)
  ensure_folder(config.temp_folder, True)
  ensure_folder(config.log_folder, True)

  # Make server if requested
  if make_server:
    create_server(config)

  # Build trees requested
  for tree in trees:
    # Note starting time
    started = datetime.now()

    # Create folders (delete if exists)
    ensure_folder(tree.target_folder, True) # <config.target_folder>/<tree.name>
    ensure_folder(tree.object_folder, True) # Object folder (user defined!)
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

def print_help():
  print_usage()
  print """Options:
  -h, --help                     Show help information.
  -f, --file    FILE             Use FILE as config file
  -t, --tree    TREE             Index and Build only section TREE (default is all)
  -s, --server                   Build only the server scripts
  -j, --jobs    JOBS             Use JOBS number of parallel processes (default 1)"""


def print_usage():
  print "Usage: dxr-index.py -f FILE (--server | --tree TREE)"


def ensure_folder(folder, clean = False):
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

    # Now build folder listing and folders for indexed_files
    build_folder(tree, conn, rel_path, indexed_files, folders)

  # Okay, let's commit everything
  conn.commit()

  # Print time
  print "(finished in %s)" % (datetime.now() - started)


def build_folder(tree, conn, folder, indexed_files, indexed_folders):
  """ Build folders and folder listing """
  # Create the sub folder, if it doesn't exist
  path = os.path.join(tree.target_folder, folder)
  if not os.path.isdir(path):
    os.mkdir(path)

  # Okay, now we build folder listing
  # Name is either basename (or if that is "" name of tree)
  name = os.path.basename(folder) or tree.name

  # Generate list of folders (with meta-data)
  folders = []
  for f in indexed_folders:
    # Get folder path on disk
    path = os.path.join(tree.source_folder, folder, f)
    # stat the folder
    stat = os.stat(path)
    modified = datetime.fromtimestamp(stat.st_mtime)
    # Okay, this is what we give the template:
    folders.append(('folder', f, modified))

  # Generate list of files
  files = []
  for f in indexed_files:
    # Get file path on disk
    path = os.path.join(tree.source_folder, folder, f)
    # stat the file
    stat = os.stat(path)
    modified = datetime.fromtimestamp(stat.st_mtime)
    # Format the size
    size = stat.st_size # TODO Make this a bit prettier, ie. 4 decimals
    if size > 2 ** 30:
      size = str(size / 2 ** 30) + 'G'
    elif size > 2 ** 20:
      size = str(size / 2 ** 20) + 'M'
    elif size > 2 ** 10:
      size = str(size / 2 ** 10) + 'K'
    else:
      size = str(size)
    # Now give this stuff to list template
    files.append((dxr.mime.icon(path), f, modified, size))

  # Destination file path
  dst_path = os.path.join(tree.target_folder,
                          folder,
                          tree.config.directory_index)
  # Fetch template from environment
  env = dxr.utils.load_template_env(tree.config)  # don't worry it caches the env
  tmpl = env.get_template('folder.html')
  arguments = {
    # Set common template variables
    'wwwroot':        tree.config.wwwroot,
    'tree':           tree.name,
    'trees':          [t.name for t in tree.config.trees],
    'config':         tree.config.template_parameters,
    'generated_date': tree.config.generated_date,
    # Set folder template variables
    'name':           name,
    'path':           folder,
    'folders':        folders,
    'files':          files
  }
  # Fill-in variables and dump to file with utf-8 encoding
  tmpl.stream(**arguments).dump(dst_path, encoding = 'utf-8')


def create_server(config):
  """ Create server scripts for hosting the DXR indexes """
  print "Generating server scripts"
  # Server folder (located in the target_folder)
  server_folder = os.path.join(config.target_folder, 'server')

  # Delete and copy in the server folder as is
  if os.path.isdir(server_folder):
    shutil.rmtree(server_folder, False)
  shutil.copytree(os.path.join(config.dxrroot, 'server'), server_folder, False)

  # We don't want to load config file on the server, so we just write all the
  # setting into the config.py script, simple as that.
  config_file = os.path.join(server_folder, 'config.py')
  dxr.utils.substitute_in_file(config_file, 
    trees               = repr([t.name for t in config.trees]),
    wwwroot             = repr(config.wwwroot),
    template_parameters = repr(config.template_parameters),
    generated_date      = repr(config.generated_date)
  )

  # Substitution for test-server.py
  test_server = os.path.join(server_folder, 'test-server.py')
  dxr.utils.substitute_in_file(test_server, 
    trees               = repr([t.name for t in config.trees]),
    wwwroot             = repr(config.wwwroot),
    template_parameters = repr(config.template_parameters),
    directory_index     = repr(config.directory_index)
  )

  # Substitution for dot-htaccess
  htaccess = os.path.join(server_folder, 'dot-htaccess')
  dxr.utils.substitute_in_file(htaccess, 
    directory_index     = repr(config.directory_index)
  )

  # Create jinja cache folder in server folder
  os.mkdir(os.path.join(server_folder, 'jinja_dxr_cache'))

  # Copy in template folder
  # We'll use mod_rewrite to map static/ one level up
  shutil.copytree(config.template, os.path.join(server_folder, 'template'))

  # Build index file
  build_index(config)
  # TODO Make open-search.xml things (or make the server so it can do them!)

def build_index(config):
  """ Build index.html for the server """
  # Destination path
  dst_path = os.path.join(config.target_folder, 'server', 'index.html')
  # Fetch template
  env   = dxr.utils.load_template_env(config)
  tmpl  = env.get_template('index.html')
  arguments = {
    # Set common template arguments
    'wwwroot':        config.wwwroot,
    'tree':           config.trees[0].name,
    'trees':          [t.name for t in config.trees],
    'config':         config.template_parameters,
    'generated_date': config.generated_date
  }
  # Fill-in variables and dump to file
  tmpl.stream(**arguments).dump(dst_path, encoding = 'utf-8')


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
    cwd     = tree.source_folder
  )

  # Close log file
  log.close()

  # Abort if build failed!
  if r != 0:
    msg = "Build command for '%s' failed, exited non-zero!"
    print >> sys.stderr, msg % tree.name
    print >> sys.stderr, "    | See log: %s " % log.name
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
      cmd = [os.path.join(tree.config.dxrroot, "dxr-worker.py")] + args
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

if __name__ == '__main__':
  main(sys.argv[1:])

