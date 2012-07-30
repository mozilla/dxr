#!/usr/bin/env python2

import dxr
import dxr.htmlbuilders
import dxr.languages
import os, sys
import shutil
import sqlite3
import string
import subprocess
import time, datetime
import fnmatch
import getopt

def main(argv):
  # Options to read
  configfile  = None
  nb_jobs     = None # Allow us to overwrite config
  tree        = None
  make_server = False

  # Parse arguments
  try:
    params = ["help", "file=", "tree=", "jobs="]
    options, args = getopt.getopt(argv, "hf:t:j:", params)
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
      nb_jobs = int(opt)
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
  config = dxr.utils.Config(configfile, nb_jobs = str(nb_jobs))

  # Find trees to make, fail if requested tree isn't available
  if tree
    trees = [t for t in config.trees if t.name = tree]
    if len(trees) == 0:
      print >> sys.stderr, "Tree '%s' is not defined in config file!" % tree
      sys.exit(1)
  elif not make_server:
    # Build everything if no tree or action is provided
    trees = config.trees
    make_server = True

  # Create config.target_folder (if not exists)
  ensure_folder(config.target_folder, False)

  #TODO Start time to save time for each step for summary!

  # Make server if requested
  if make_server:
    create_server()

  # Build trees requested
  for tree in trees:
    # Create folders (delete if exists)
    ensure_folder(tree.target_folder, True) # <config.target_folder>/<tree.name>
    ensure_folder(tree.object_folder, True) # Object folder (user defined!)
    ensure_folder(tree.temp_folder,   True) # <config.temp_folder>/<tree.name>
                                            # (or user defined)
    files_folder    = os.path.join(tree.target_folder, 'files')
    folders_folder  = os.path.join(tree.target_folder, 'folders')
    raw_folder      = os.path.join(tree.target_folder, 'raw')
    ensure_folder(files_folder,     True)   # file listings
    ensure_folder(folders_folder,   True)   # folder listings
    ensure_folder(raw_folder,       True)   # Raw content, ie. images etc.

    # Temporary folders for plugins
    for plugin in tree.enabled_plugins:     # <tree.config>/plugins/<plugin>
      ensure_folder(os.path.join(tree.temp_folder, 'plugins', plugin), True)

    # Connect to database (exits on failure: sqlite_version, tokenizer, etc)
    dxr.utils.connect_database(tree)

    # Create database tables
    create_tables(tree, conn)

    # Index all source files (for full text search)
    # Also build all folder listing while we're at it
    index_files(tree, conn)

    # Build tree
    build_tree(tree, conn)

    # Optimize, analyze and check database integrity
    conn.execute("INSERT INTO fts(fts) VALUES('optimize')")
    conn.execute("ANALYSE");

    isOkay = None
    for row in conn.execute("PRAGMA integrity_check"):
      if row[0] == "ok" and isOkay is None:
        isOkay = True
      else:
        isOkay = False
        print >> sys.stderr, "Database, integerity-check: %s" % row[0]
    if not isOkay:
      print >> sys.stderr, "Database integrity-check failed!"
      sys.exit(1)

    # Check integrity of fts table, should throw exception on failure
    conn.execute("INSERT INTO fts(fts) VALUES('integrity-check')")

    # Commit database
    conn.commit()

    # Build html
    run_html_workers(tree, conn)

    # Close connection
    conn.commit()
    conn.close()


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
  conn.execute("CREATE VIRTUAL TABLE fts USING fts4 (basename, content, tokenize=dxrCodeTokenizer)")
  conn.execute(dxr.languages.language_schema.get_create_sql())


def index_files(tree, conn):
  """ Index all files from the source directory """
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

      # Try to decode the file as text
      try:
        with open(file_path, "r") as source_file:
          data = source_file.read()
        data.decode('utf-8')
      except UnicodeDecodeError:
        # TODO Check if it's a jpg, gif, png, ico or other web supported format
        # (ONLY web supported format, we don't bother with conversion)
        # generate web page for it, and copy it into the raw folder...
        continue
      except:
        traceback.print_exc()
        print >> sys.stderr, "Failed to open %s" % file_path
        sys.exit(1)

      # Insert this file
      cur.execute("INSERT INTO files (path) VALUES (?)", (path,))
      # Index this file
      sql = "INSERT INTO fts (rowid, content) VALUES (?, ?)"
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


def build_folder(tree, conn, folder, indexed_files, indexed_folders):
  """ Build folders and folder listing """
  # Create the sub folder in each of the 3 locations required
  os.mkdir(os.path.join(tree.target_folder, 'files',    folder))
  os.mkdir(os.path.join(tree.target_folder, 'folders',  folder))
  os.mkdir(os.path.join(tree.target_folder, 'raw',      folder))

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
    modified = datetime.datetime.fromtimestamp(stat.st_mtime)
    # Okay, this is what we give the template:
    folders.append(('folder', f, modified))

  # Generate list of files
  files = []
  for f in indexed_files:
    # Get file path on disk
    path = os.path.join(tree.source_folder, folder, f)
    # stat the file
    stat = os.stat(path)
    modified = datetime.datetime.fromtimestamp(stat.st_mtime)
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
    # TODO Customize icon base on file type or extension
    files.append(('page_white', f, modified, size))

  # Destination file path
  dst_path = os.path.join(tree.target_folder, 'folders', folder, 'index.html')
  # Fetch template from environment
  env = dxr.utils.load_template_env(tree.config)  # don't worry it caches the env
  tmpl = env.get_template('folder.html')
  arguments = {
    # Set common template variables
    'wwwroot':    tree.config.wwwroot,
    'tree':       tree.name,
    'trees':      [t.name for t in tree.config.trees],
    'config':     tree.config.template_parameters,
    # Set folder template variables
    'name':       name,
    'folders':    folders,
    'files':      files
  }
  # Fill-in variables and dump to file with utf-8 encoding
  tmpl.stream(**arguments).dump(dst_path, encoding = 'utf-8')


def create_server(config):
  """ Create server scripts for hosting the DXR indexes """
  # Server folder (located in the target_folder)
  server_folder = os.path.join(config.target_folder, 'server')

  # Delete and copy in the server folder as is
  if os.path.isdir(server_folder):
    os.rmtree(server_folder, False)
  shutil.copytree(os.path.join(config.dxrroot, 'server'), server_folder, False)

  # We don't want to load config file on the server, so we just write all the
  # setting into the config.py script, simple as that.
  config_file = os.path.join(server_folder, 'config.py')
  with open(config_file, 'r') as f:
    data = f.read()
  data = string.Template(data).safe_substitute(
    trees               = repr([t.name for t in config.tree]),
    wwwroot             = repr(config.wwwroot),
    template_parameters = repr(config.template_parameters)
  )
  with open(config_file, 'w') as f:
    f.write(data)

  # Create jinja cache folder in server folder
  os.mkdir(os.path.join(server_folder, 'jinja_dxr_cache'))

  # Copy in template folder
  # We'll use mod_rewrite to map static/ one level up
  shutil.copytree(config.template, os.path.join(server_folder, 'template'))

  # Copy the dxr tokenizer to server_folder
  shutil.copytree(
    os.path.join(config.dxrroot, 'sqlite-tokenizer'),
    os.path.join(server_folder, 'sqlite-tokenizer')
  )

  # Build index file
  build_index(config)
  # TODO Make open-search.xml things (or make the server so it can do them!)
  # TODO Make .htaccess, s.t. this will actually work

def build_index(config):
  """ Build index.html for the server """
  # Destination path
  dst_path = os.path.join(config.target_folder, 'server', 'index.html')
  # Fetch template
  env   = dxr.utils.load_template_env(config)
  tmpl  = env.get_template('index.html')
  arguments = {
    # Set common template arguments
    'wwwroot':    config.wwwroot,
    'tree':       config.trees[0].name,
    'trees':      [t.name for t in config.trees],
    'config':     config.template_parameters
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
    indexer.pre_process(tree, conn, environ)

  # Open log files
  msglog = open(os.path.join(tree.temp_folder, "build-messages.log"), 'w')
  errlog = open(os.path.join(tree.temp_folder, "build-errors.log"), 'w')

  # Call the make command
  r = subprocess.call(
    tree.build_command.replace("$jobs", config.nb_jobs),
    shell   = True,
    stdout  = msglog,
    stderr  = errlog,
    env     = environ,
    cwd     = tree.source_folder
  )

  # Close log files
  msglog.close()
  errlog.close()

  # Abort if build failed!
  if r != 0:
    print >> sys.stderr, "Build command for '%s' failed, exited non-zero!" % tree.name
    sys.exit(1)

  # Let plugins post process
  for indexer in indexers:
    indexer.post_process(tree, conn)


def run_html_workers(tree, conn):
  """ Build HTML for a tree """
  # Let's find the number of rows, this is the maximum rowid, assume we didn't
  # delete files, this assumption should hold, but even if we delete files, it's
  # fairly like that this partition the work reasonably evenly.
  sql = "SELECT files.ID FROM files ORDER BY files.ID DESC LIMIT 1"
  row = conn.execute(sql).fetchone()
  file_count = row[0]

  # Make some slices
  slices = []
  # Don't make slices bigger than 500
  step = min(500, file_count)
  start = None    # None, is not --start argument
  for end in xrange(step, file_count, step):
    slices.append((start, end))
    start = end + 1
  slices.append((start, None))  # None, means omit --end argument

  # Okay, let's make a list of workers
  workers = []
  next_id = 0   # unique ids for workers, to associate log files
  # While there's slices and workers, we can manage them
  while len(slices) > 0 or len(workers) > 0:
    # Handle errors for workers that are done
    for worker, msgs, errs in workers:
      if worker.poll() is None:
        continue
      # Close log files
      msgs.close()
      errs.close()
      # Crash and error if we have problems
      if worker.returncode != 0:
        print >> sys.stderr, "dxr-htmlbuilder.py subprocess failed!"
        print >> sys.stderr, "    | See %s for messages" % msgs.name
        print >> sys.stderr, "    | See %s for errors" % errs.name
        # Kill co-workers
        for worker, msgs, errs in workers:
          if worker[0].pull() is None:
            worker[0].kill()
            msgs.close()
            errs.close()
        # Exit, we're done here
        sys.exit(1)
    
    # Remove workers that are complete
    workers = [w for w in workers if w[0].poll() is not None]

    # Create workers while we have slots available
    while len(workers) < tree.config.nb_jobs and len(slices) > 0:
      # Get slice of work
      start, end = slices.pop()
      # Setup arguments
      args = ['--file', tree.config.configfile, '--tree', tree.name]
      if start is not None:
        args += ['--start', str(start)]
      if end is not None:
        args += ['--end', str(end)]
      # Open log files
      msgs_filename = "html-worker-%s-messages.log" % next_id
      errs_filename = "html-worker-%s-errors.log" % next_id
      msgs = open(os.path.join(tree.temp_folder, msgs_filename), 'w')
      errs = open(os.path.join(tree.temp_folder, errs_filename), 'w')
      # Create a worker
      worker = subprocess.Popen(
        [os.path.join(tree.config.dxrroot, "dxr-htmlbuilder.py")] + args,
        stdout = msgs,
        stderr = errs
      )
      # Add workers to list of workers
      workers.append((worker, msgs, errs))

    # Wait for a subprocess to terminate (any subprocess is fine!)
    os.wait()

if __name__ == '__main__':
  main(sys.argv[1:])

