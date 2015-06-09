from datetime import datetime
from errno import ENOENT
from fnmatch import fnmatchcase
from itertools import chain, izip, repeat
from operator import attrgetter
import os
from os import stat, mkdir, makedirs
from os.path import dirname, islink, relpath, join, split
from shutil import rmtree
import subprocess
import sys
from sys import exc_info
from traceback import format_exc
from uuid import uuid1

from concurrent.futures import as_completed, ProcessPoolExecutor
from click import progressbar
from flask import current_app
from funcy import merge, chunks, first, suppress
import jinja2
from more_itertools import chunked
from ordereddict import OrderedDict
from pyelasticsearch import (ElasticSearch, ElasticHttpNotFoundError,
                             IndexAlreadyExistsError, bulk_chunks, Timeout,
                             ConnectionError)

import dxr
from dxr.app import make_app
from dxr.config import FORMAT
from dxr.es import UNINDEXED_STRING, TREE
from dxr.exceptions import BuildError
from dxr.filters import LINE, FILE
from dxr.lines import es_lines, finished_tags
from dxr.mime import is_text, icon, is_image
from dxr.query import filter_menu_items
from dxr.utils import (open_log, deep_update, append_update,
                       append_update_by_line, append_by_line, bucket)
from dxr.vcs import VcsCache


def full_traceback(callable, *args, **kwargs):
    """Work around the wretched exception reporting of concurrent.futures.

    Futures generally gives no access to the traceback of the task; you get
    only a traceback into the guts of futures, plus the description line of
    the task's traceback. We jam the full traceback of any exception that
    occurs into the message of the exception: disgusting but informative.

    """
    try:
        return callable(*args, **kwargs)
    except Exception:
        raise Exception(format_exc())


def index_and_deploy_tree(tree, verbose=False):
    """Index a tree, and make it accessible.

    :arg tree: The TreeConfig of the tree to build

    """
    config = tree.config
    es = ElasticSearch(config.es_hosts, timeout=config.es_indexing_timeout)
    index_name = index_tree(tree, es, verbose=verbose)
    if 'index' not in tree.config.skip_stages:
        deploy_tree(tree, es, index_name)


def deploy_tree(tree, es, index_name):
    """Point the ES aliases and catalog records to a newly built tree, and
    delete any obsoleted index.

    """
    config = tree.config

    # Make new index live:
    alias = config.es_alias.format(format=FORMAT, tree=tree.name)
    swap_alias(alias, index_name, es)

    # Create catalog index if it doesn't exist.
    try:
        es.create_index(
            config.es_catalog_index,
            settings={
                'settings': {
                    'index': {
                        # Fewer should be faster:
                        'number_of_shards': 1,
                        # This should be cranked up until it's on all nodes,
                        # so it's always a fast read:
                        'number_of_replicas': config.es_catalog_replicas
                    },
                },
                'mappings': {
                    TREE: {
                        '_all': {
                            'enabled': False
                        },
                        'properties': {
                            'name': {
                                'type': 'string',
                                'index': 'not_analyzed'
                            },
                            'format': {
                                'type': 'string',
                                'index': 'not_analyzed'
                            },
                            # In case es_alias changes in the conf file:
                            'es_alias': UNINDEXED_STRING,
                            # Needed so new trees or edited descriptions can show
                            # up without a WSGI restart:
                            'description': UNINDEXED_STRING,
                            # ["clang", "pygmentize"]:
                            'enabled_plugins': UNINDEXED_STRING,
                            'generated_date': UNINDEXED_STRING
                            # We may someday also need to serialize some plugin
                            # configuration here.
                        }
                    }
                }
            })
    except IndexAlreadyExistsError:
        pass

    # Insert or update the doc representing this tree. There'll be a little
    # race between this and the alias swap. We'll live.
    es.index(config.es_catalog_index,
             doc_type=TREE,
             doc=dict(name=tree.name,
                      format=FORMAT,
                      es_alias=alias,
                      description=tree.description,
                      enabled_plugins=[p.name for p in tree.enabled_plugins],
                      generated_date=config.generated_date),
             id='%s/%s' % (FORMAT, tree.name))


def swap_alias(alias, index, es):
    """Point an ES alias to a new index, and delete the old index.

    :arg index: The new index name

    """
    # Get the index the alias currently points to.
    old_index = first(es.aliases(alias))

    # Make the alias point to the new index.
    removal = ([{'remove': {'index': old_index, 'alias': alias}}] if
               old_index else [])
    es.update_aliases(removal + [{'add': {'index': index, 'alias': alias}}])  # atomic

    # Delete the old index.
    if old_index:
        es.delete_index(old_index)


def index_tree(tree, es, verbose=False):
    """Index a single tree into ES and the filesystem, and return the
    name of the new ES index.

    """
    config = tree.config

    def new_pool():
        return ProcessPoolExecutor(max_workers=config.workers)

    def farm_out(method_name):
        """Farm out a call to all tree indexers across a process pool.

        Return the tree indexers, including anything mutations the method call
        might have made.

        Show progress while doing it.

        """
        if not config.workers:
            return [save_scribbles(ti, method_name) for ti in tree_indexers]
        else:
            futures = [pool.submit(full_traceback, save_scribbles, ti, method_name)
                       for ti in tree_indexers]
            return [future.result() for future in
                    show_progress(futures, 'Running %s' % method_name)]

    def delete_index_quietly(es, index):
        """Delete an index, and ignore any error.

        This cannot be done inline in the except clause below, because, even
        if we catch this exception, it spoils the exception info in that
        scope, making the bare ``raise`` raise the not-found error rather than
        whatever went wrong earlier.

        """
        try:
            es.delete_index(index)
        except Exception:
            pass

    print "Starting tree '%s'." % tree.name

    # Note starting time
    start_time = datetime.now()

    skip_indexing = 'index' in config.skip_stages
    skip_build = 'build' in config.skip_stages
    skip_cleanup  = skip_indexing or skip_build

    # Create and/or clear out folders:
    ensure_folder(tree.object_folder, tree.source_folder != tree.object_folder)
    ensure_folder(tree.temp_folder, not skip_cleanup)
    ensure_folder(tree.log_folder, not skip_cleanup)
    ensure_folder(join(tree.temp_folder, 'plugins'), not skip_cleanup)
    for plugin in tree.enabled_plugins:
        ensure_folder(join(tree.temp_folder, 'plugins', plugin.name),
                      not skip_cleanup)

    vcs_cache = VcsCache(tree)
    tree_indexers = [p.tree_to_index(p.name, tree, vcs_cache) for p in
                     tree.enabled_plugins if p.tree_to_index]
    try:
        if not skip_indexing:
            # Make a new index with a semi-random name, having the tree name
            # and format version in it. TODO: The prefix should come out of
            # the tree config, falling back to the global config:
            # dxr_hot_prod_{tree}_{whatever}.
            index = config.es_index.format(format=FORMAT,
                                           tree=tree.name,
                                           unique=uuid1())
            es.create_index(
                index,
                settings={
                    'settings': {
                        'index': {
                            'number_of_shards': 1,  # Fewer should be faster, assuming enough RAM.
                            'number_of_replicas': 0  # for speed
                        },
                        # Default analyzers and mappings are in the core plugin.
                        'analysis': reduce(
                                deep_update,
                                (p.analyzers for p in tree.enabled_plugins),
                                {}),

                        # DXR indices are immutable once built. Turn the
                        # refresh interval down to keep the segment count low
                        # while indexing. It will make for less merging later.
                        # We could also simply call "optimize" after we're
                        # done indexing, but it is unthrottled; we'd have to
                        # use shard allocation to do the indexing on one box
                        # and then move it elsewhere for actual use.
                        'refresh_interval':
                            '%is' % config.es_refresh_interval
                    },
                    'mappings': reduce(deep_update,
                                       (p.mappings for p in
                                            tree.enabled_plugins),
                                       {})
                })
        else:
            index = None
            print "Skipping indexing (due to 'index' in 'skip_stages')"

        # Run pre-build hooks:
        with new_pool() as pool:
            tree_indexers = farm_out('pre_build')
            # Tear down pool to let the build process use more RAM.

        if not skip_build:
            # Set up env vars, and build:
            build_tree(tree, tree_indexers, verbose)
        else:
            print "Skipping rebuild (due to 'build' in 'skip_stages')"

        # Post-build, and index files:
        if not skip_indexing:
            with new_pool() as pool:
                tree_indexers = farm_out('post_build')
                index_files(tree, tree_indexers, index, pool, es)

            # refresh() times out in prod. Wait until it doesn't. That
            # probably means things are ready to rock again.
            with aligned_progressbar(repeat(None), label='Refeshing index') as bar:
                for _ in bar:
                    try:
                        es.refresh(index=index)
                    except (ConnectionError, Timeout) as exc:
                        pass
                    else:
                        break

            es.update_settings(
                index,
                {
                    'settings': {
                        'index': {
                            'number_of_replicas': 1  # fairly arbitrary
                        }
                    }
                })
    except Exception as exc:
        # If anything went wrong, delete the index, because we're not
        # going to have a way of returning its name if we raise an
        # exception.
        if not skip_indexing:
            delete_index_quietly(es, index)
        raise

    print "Finished '%s' in %s." % (tree.name, datetime.now() - start_time)
    if not skip_cleanup:
        # By default, we remove the temp files, because they're huge.
        rmtree(tree.temp_folder)
    return index


def aligned_progressbar(*args, **kwargs):
    """Fall through to click's progress bar, but line up all the bars so they
    aren't askew."""
    return progressbar(
        *args, bar_template='%(label)-18s [%(bar)s] %(info)s', **kwargs)


def show_progress(futures, message):
    """Show progress and yield results as futures complete."""
    with aligned_progressbar(as_completed(futures),
                             length=len(futures),
                             show_eta=False,  # never even close
                             label=message) as bar:
        for future in bar:
            yield future


def save_scribbles(obj, method):
    """Call obj.method(), then return obj and the result so the master process
    can see anything method() scribbled on it.

    This is meant to run in a remote process.

    """
    getattr(obj, method)()
    return obj


def ensure_folder(folder, clean=False):
    """Ensure the existence of a folder.

    :arg clean: Whether to ensure that the folder is empty

    """
    if clean and os.path.isdir(folder):
        rmtree(folder)
    if not os.path.isdir(folder):
        makedirs(folder)


def _unignored_folders(folders, source_path, ignore_filenames, ignore_paths):
    """Yield the folders from ``folders`` which are not ignored by the given
    patterns and paths.

    :arg source_path: Relative path to the source directory
    :arg ignore_filenames: Filename-based globs to be ignored
    :arg ignore_paths: Path-based globs to be ignored

    """
    for folder in folders:
        if not any(fnmatchcase(folder, p) for p in ignore_filenames):
            folder_path = '/' + join(source_path, folder).replace(os.sep, '/') + '/'
            if not any(fnmatchcase(folder_path, p) for p in ignore_paths):
                yield folder


def file_contents(path, encoding_guess):  # TODO: Make accessible to TreeToIndex.post_build.
    """Return the unicode contents of a file if we can figure out a decoding.
    Otherwise, return the contents as a string.

    :arg path: A sufficient path to the file
    :arg encoding_guess: A guess at the encoding of the file, to be applied if
        it seems to be text

    """
    # Read the binary contents of the file.
    # If mime.is_text() says it's text, try to decode it using encoding_guess.
    # If that works, return the resulting unicode.
    # Otherwise, return the binary string.
    with open(path, 'rb') as source_file:
        contents = source_file.read()  # always str
    if is_text(contents):
        try:
            contents = contents.decode(encoding_guess)
        except UnicodeDecodeError:
            pass  # Leave contents as str.
    return contents


def unignored(folder, ignore_paths, ignore_filenames, want_folders=False):
    """Return an iterable of absolute paths to unignored source tree files or
    the folders that contain them.

    Returned files include both binary and text ones.

    :arg want_folders: If falsey, return files. If truthy, return folders
        instead.

    """
    def raise_(exc):
        raise exc

    # TODO: Expose a lot of pieces of this as routines plugins can call.
    for root, folders, files in os.walk(folder, topdown=True, onerror=raise_):
        # Find relative path
        rel_path = relpath(root, folder)
        if rel_path == '.':
            rel_path = ''

        if not want_folders:
            for f in files:
                # Ignore file if it matches an ignore pattern
                if any(fnmatchcase(f, e) for e in ignore_filenames):
                    continue  # Ignore the file.

                path = join(rel_path, f)

                # Ignore file if its path (relative to the root) matches an
                # ignore path.
                if any(fnmatchcase("/" + path.replace(os.sep, "/"), e) for e in ignore_paths):
                    continue  # Ignore the file.

                yield join(root, f)

        # Exclude folders that match an ignore pattern.
        # os.walk listens to any changes we make in `folders`.
        folders[:] = _unignored_folders(
            folders, rel_path, ignore_filenames, ignore_paths)
        if want_folders:
            for f in folders:
                yield join(root, f)


def index_file(tree, tree_indexers, path, es, index):
    """Index a single file into ES, and build a static HTML representation of it.

    For the moment, we execute plugins in series, figuring that we have plenty
    of files to keep our processors busy in most trees that take very long. I'm
    a little afraid of the cost of passing potentially large TreesToIndex to
    worker processes. That goes at 52MB/s on my OS X laptop, measuring by the
    size of the pickled object and including the pickling and unpickling time.

    :arg path: Absolute path to the file to index
    :arg index: The ES index name

    """
    try:
        contents = file_contents(path, tree.source_encoding)
    except IOError as exc:
        if exc.errno == ENOENT and islink(path):
            # It's just a bad symlink (or a symlink that was swiped out
            # from under us--whatever)
            return
        else:
            raise

    rel_path = relpath(path, tree.source_folder)
    is_text = isinstance(contents, unicode)
    if is_text:
        lines = contents.splitlines(True)
        num_lines = len(lines)
        needles_by_line = [{} for _ in xrange(num_lines)]
        annotations_by_line = [[] for _ in xrange(num_lines)]
        refses, regionses = [], []
    needles = {}
    linkses = []

    for tree_indexer in tree_indexers:
        file_to_index = tree_indexer.file_to_index(rel_path, contents)
        if file_to_index.is_interesting():
            # Per-file stuff:
            append_update(needles, file_to_index.needles())
            linkses.append(file_to_index.links())

            # Per-line stuff:
            if is_text:
                refses.append(file_to_index.refs())
                regionses.append(file_to_index.regions())
                append_update_by_line(needles_by_line,
                                      file_to_index.needles_by_line())
                append_by_line(annotations_by_line,
                               file_to_index.annotations_by_line())

    def docs():
        """Yield documents for bulk indexing."""
        # Index a doc of type 'file' so we can build folder listings.
        # At the moment, we send to ES in the same worker that does the
        # indexing. We could interpose an external queueing system, but I'm
        # willing to potentially sacrifice a little speed here for the easy
        # management of self-throttling.
        file_info = stat(path)
        folder_name, file_name = split(rel_path)
        # Hard-code the keys that are hard-coded in the browse()
        # controller. Merge with the pluggable ones from needles:
        doc = dict(# Some non-array fields:
                    folder=folder_name,
                    name=file_name,
                    size=file_info.st_size,
                    modified=datetime.fromtimestamp(file_info.st_mtime),
                    is_folder=False,

                    # And these, which all get mashed into arrays:
                    **needles)
        links = [{'order': order,
                    'heading': heading,
                    'items': [{'icon': icon,
                                'title': title,
                                'href': href}
                            for icon, title, href in items]}
                    for order, heading, items in
                    chain.from_iterable(linkses)]
        if links:
            doc['links'] = links
        yield es.index_op(doc, doc_type=FILE)

        # Index all the lines. If it's an empty file (no lines), don't bother
        # ES. It hates empty dicts.
        if is_text and needles_by_line:
            for total, annotations_for_this_line, tags in izip(
                    needles_by_line,
                    annotations_by_line,
                    es_lines(finished_tags(lines,
                                           chain.from_iterable(refses),
                                           chain.from_iterable(regionses)))):
                # Duplicate the file-wide needles into this line:
                total.update(needles)

                # We bucket tags into refs and regions for ES because later at
                # request time we want to be able to merge them individually
                # with those from skimmers.
                refs_and_regions = bucket(tags, lambda index_obj: "regions" if
                                          isinstance(index_obj['payload'], basestring) else
                                          "refs")
                if 'refs' in refs_and_regions:
                    total['refs'] = refs_and_regions['refs']
                if 'regions' in refs_and_regions:
                    total['regions'] = refs_and_regions['regions']
                if annotations_for_this_line:
                    total['annotations'] = annotations_for_this_line
                yield es.index_op(total)

    # Indexing a 277K-line file all in one request makes ES time out (>60s),
    # so we chunk it up. 300 docs is optimal according to the benchmarks in
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1122685. So large docs like
    # images don't make our chunk sizes ridiculous, there's a size ceiling as
    # well: 10000 is based on the 300 and an average of 31 chars per line.
    for chunk in bulk_chunks(docs(), docs_per_chunk=300, bytes_per_chunk=10000):
        es.bulk(chunk, index=index, doc_type=LINE)


def index_chunk(tree,
                tree_indexers,
                paths,
                index,
                swallow_exc=False,
                worker_number=None):
    """Index a pile of files.

    This is the entrypoint for indexer pool workers.

    :arg worker_number: A unique number assigned to this worker so it knows
        what to call its log file

    """
    path = '(no file yet)'
    try:
        # So we can use Flask's url_from():
        with make_app(tree.config).test_request_context():
            es = current_app.es
            try:
                # Don't log if single-process:
                log = (worker_number and
                       open_log(tree.log_folder,
                                'index-chunk-%s.log' % worker_number))
                for path in paths:
                    log and log.write('Starting %s.\n' % path)
                    index_file(tree, tree_indexers, path, es, index)
                log and log.write('Finished chunk.\n')
            finally:
                log and log.close()
    except Exception as exc:
        if swallow_exc:
            type, value, traceback = exc_info()
            return format_exc(), type, value, path
        else:
            raise


def index_folders(tree, index, es):
    """Index the folder hierarchy into ES."""
    with aligned_progressbar(unignored(tree.source_folder,
                                       tree.ignore_paths,
                                       tree.ignore_filenames,
                                       want_folders=True),
                     show_eta=False,  # never even close
                     label='Indexing folders') as folders:
        for folder in folders:
            rel_path = relpath(folder, tree.source_folder)
            superfolder_path, folder_name = split(rel_path)
            es.index(index, FILE, {
                'path': [rel_path],  # array for consistency with non-folder file docs
                'folder': superfolder_path,
                'name': folder_name,
                'is_folder': True})


def index_files(tree, tree_indexers, index, pool, es):
    """Divide source files into groups, and send them out to be indexed."""

    def path_chunks(tree):
        """Return an iterable of worker-sized iterables of paths."""
        return chunks(500, unignored(tree.source_folder,
                                     tree.ignore_paths,
                                     tree.ignore_filenames))

    index_folders(tree, index, es)

    if not tree.config.workers:
        for paths in path_chunks(tree):
            index_chunk(tree,
                        tree_indexers,
                        paths,
                        index,
                        swallow_exc=False)
    else:
        futures = [pool.submit(index_chunk,
                               tree,
                               tree_indexers,
                               paths,
                               index,
                               worker_number=worker_number,
                               swallow_exc=True)
                   for worker_number, paths in enumerate(path_chunks(tree), 1)]
        for future in show_progress(futures, 'Indexing files'):
            result = future.result()
            if result:
                formatted_tb, type, value, path = result
                print 'A worker failed while indexing %s:' % path
                print formatted_tb
                # Abort everything if anything fails:
                raise type, value  # exits with non-zero


def _fill_and_write_template(jinja_env, template_name, out_path, vars):
    """Get the template `template_name` from the template folder, substitute in
    `vars`, and write the result to `out_path`."""
    template = jinja_env.get_template(template_name)
    template.stream(**vars).dump(out_path, encoding='utf-8')


def build_tree(tree, tree_indexers, verbose):
    """Set up env vars, and run the build command."""

    if not tree.build_command:
        return

    # Set up build environment variables:
    environ = os.environ.copy()
    for ti in tree_indexers:
        environ.update(ti.environment(environ))

    # Call make or whatever:
    with open_log(tree.log_folder, 'build.log', verbose) as log:
        print 'Building tree'
        workers = max(tree.config.workers, 1)
        r = subprocess.call(
            tree.build_command.replace('$jobs', str(workers))
                              .format(workers=workers),
            shell   = True,
            stdout  = log,
            stderr  = log,
            env     = environ,
            cwd     = tree.object_folder
        )

    # Abort if build failed:
    if r != 0:
        print >> sys.stderr, ("Build command for '%s' failed, exited non-zero."
                              % tree.name)
        if not verbose:
            print >> sys.stderr, 'Log follows:'
            with open(log.name) as log_file:
                print >> sys.stderr, '    | %s ' % '    | '.join(log_file)
        raise BuildError
