import cgi
from datetime import datetime
from errno import ENOENT
from fnmatch import fnmatchcase
import json
from operator import attrgetter
import os
from os import stat, mkdir
from os.path import dirname, islink, relpath, join, split
import shutil
import subprocess
import sys
from sys import exc_info
from traceback import format_exc
from warnings import warn
from uuid import uuid1

from concurrent.futures import as_completed, ProcessPoolExecutor
from funcy import merge, chunks, first, suppress
import jinja2
from jinja2 import Markup
from ordereddict import OrderedDict
from pyelasticsearch import ElasticSearch, ElasticHttpNotFoundError

import dxr
from dxr.config import Config, FORMAT
from dxr.mime import is_text, icon
from dxr.plugins import LINE as LINE_DOCTYPE, FILE as FILE_DOCTYPE
from dxr.query import filter_menu_items
from dxr.utils import (open_log, browse_url, deep_update, append_update,
                       append_update_by_line, append_by_line, TEMPLATE_DIR)

try:
    from itertools import compress
except ImportError:
    from itertools import izip
    def compress(data, selectors):
        return (d for d, s in izip(data, selectors) if s)


class BuildError(Exception):
    """Catch-all error for expected kinds of failures during indexing"""
    # This could be refined better, have params added, etc., but it beats
    # calling sys.exit, which is what was happening before.


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
        subtree_path = join('/', tree_name, 'source', *dirs[:idx])
        subtree_name = split(subtree_path)[1] or tree_name
        components.append((subtree_path, subtree_name))

    return components


def build_instance(config_path, nb_jobs=None, tree=None, verbose=False):
    """Build a DXR instance, point the ES aliases to the new indices, and
    delete the old ones.

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
        overrides['nb_jobs'] = nb_jobs
    config = Config(config_path, **overrides)

    # Find trees to make, fail if requested tree isn't available
    if tree:
        trees = [t for t in config.trees if t.name == tree]
        if not trees:
            print >> sys.stderr, "Tree '%s' is not defined in config file!" % tree
            raise BuildError
    else:
        # Build everything if no tree is provided
        trees = config.trees

    es = ElasticSearch(config.es_hosts)

    print " - Generating target folder."
    create_skeleton(config)

    # Index the trees, collecting (tree name, alias, index name):
    indices = [(tree.name,
                config.es_alias.format(format=FORMAT, tree=tree.name),
                index_tree(tree, es, verbose=verbose)) for tree in trees]

    # Lay down config file:
    _fill_and_write_template(
        load_template_env(),
        'config.py.jinja',
        join(config.target_folder, 'config.py'),
        dict(trees=repr(OrderedDict((t.name, t.description)
                                    for t in sorted(config.trees,
                                                    key=attrgetter('name')))),
             wwwroot=repr(config.wwwroot),
             generated_date=repr(config.generated_date),
             default_tree=repr(config.default_tree),
             es_hosts=repr(config.es_hosts),
             es_aliases=repr(dict((name, alias) for
                                  name, alias, index in indices))))

    # Make new indices live:
    for _, alias, index in indices:
        swap_alias(alias, index, es)

    # Deploy script should immediately move new FS dirs into place. There's a
    # little race here; it will go away once we dispense with FS artifacts.


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
    """Index a single tree into ES and the FS, and return the name of the new
    ES index.

    """
    def new_pool():
        return ProcessPoolExecutor(max_workers=tree.config.nb_jobs)

    def farm_out(method_name):
        """Farm out a call to all tree indexers across a process pool.

        Return the tree indexers, including anything mutations the method call
        might have made.

        Show progress while doing it.

        """
        futures = [pool.submit(save_scribbles, ti, method_name) for ti in
                   tree_indexers]
        return [future.result() for future in
                show_progress(futures, message='Running %s.' % method_name)]

    print "Processing tree '%s'." % tree.name

    # Note starting time
    start_time = datetime.now()

    skip_indexing = 'index' in tree.config.skip_stages

    # Create folders (delete if exists)
    ensure_folder(tree.target_folder, not skip_indexing) # <config.target_folder>/<tree.name>
    ensure_folder(tree.object_folder,                    # Object folder (user defined!)
        tree.source_folder != tree.object_folder)        # Only clean if not the srcdir
    ensure_folder(tree.temp_folder, not skip_indexing)   # <config.temp_folder>/<tree.name>
                                                         # (or user defined)
    ensure_folder(tree.log_folder, not skip_indexing)    # <config.log_folder>/<tree.name>
                                                         # (or user defined)
    # Temporary folders for plugins
    ensure_folder(join(tree.temp_folder, 'plugins'), not skip_indexing)
    for plugin in tree.enabled_plugins:     # <tree.config>/plugins/<plugin>
        ensure_folder(join(tree.temp_folder, 'plugins', plugin), not skip_indexing)

    tree_indexers = [p.tree_to_index(tree) for p in
                     tree.enabled_plugins.itervalues() if p.tree_to_index]

    if skip_indexing:
        print " - Skipping indexing (due to 'index' in 'skip_stages')"
    else:
        # Make a new index with a semi-random name, having the tree name
        # and format version in it. TODO: The prefix should come out of
        # the tree config, falling back to the global config:
        # dxr_hot_prod_{tree}_{whatever}.
        index = tree.config.es_index.format(format=FORMAT,
                                            tree=tree.name,
                                            unique=uuid1())
        try:
            es.create_index(
                index,
                settings={
                    'settings': {
                        'index': {
                            'number_of_shards': 1,  # Fewer should be faster, assuming enough RAM.
                            'number_of_replicas': 1  # fairly arbitrary
                        },
                        # Default analyzers and mappings are in the core plugin.
                        'analysis': reduce(deep_update, (p.analyzers for p in
                                           tree.enabled_plugins.values()), {}),

                        # DXR indices are immutable once built. Turn the
                        # refresh interval down to keep the segment count low
                        # while indexing. It will make for less merging later.
                        # We could also simply call "optimize" after we're
                        # done indexing, but it is unthrottled; we'd have to
                        # use shard allocation to do the indexing on one box
                        # and then move it elsewhere for actual use.
                        'refresh_interval': '1m'
                    },
                    'mappings': reduce(deep_update, (p.mappings for p in
                                       tree.enabled_plugins.values()), {})
                })


            # Run pre-build hooks:
            with new_pool() as pool:
                tree_indexers = farm_out('pre_build')
                # Tear down pool to let the build process use more RAM.

            # Set up env vars, and build:
            build_tree(tree, tree_indexers, verbose)

            # Post-build, and index files:
            with new_pool() as pool:
                tree_indexers = farm_out('post_build')
                index_files(tree, tree_indexers, index, pool, es)

            # Don't wait for the (long) refresh interval:
            es.refresh(index=index)
        except Exception:
            # If anything went wrong, delete the index, because we're not
            # going to have a way of returning its name if we raise an
            # exception.
            with suppress(ElasticHttpNotFoundError):
                es.delete_index(index)
            raise

    print " - Finished processing '%s' in %s." % (tree.name,
                                                      datetime.now() - start_time)

    return index

    # For each tree, flop the ES alias for this format version (pulled from the config) to the new index, and delete the old one first.

    # This is temporarily asymmetrical: it flops the index but leave it to the
    # caller to flop the static HTML. This asymmetry will go away when the
    # static HTML does.


def show_progress(futures, message='Doing stuff.'):
    """Show progress and yield results as futures complete."""
    print message
    num_jobs = len(futures)
    for num_done, future in enumerate(as_completed(futures), 1):
        print num_done, 'of', num_jobs, 'jobs done.'
        yield future


def save_scribbles(obj, method):
    """Call obj.method(), then return obj and the result so the master process
    can see anything method() scribbled on it.

    This is meant to run in a remote process.

    """
    getattr(obj, method)()
    return obj


def create_skeleton(config):
    """Make the non-tree-specific FS artifacts needed to do the build."""

    skip_indexing = 'index' in config.skip_stages

    # Create config.target_folder (if not exists)
    ensure_folder(config.target_folder, False)
    ensure_folder(config.temp_folder, not skip_indexing)
    ensure_folder(config.log_folder, not skip_indexing)

    # Create jinja cache folder in target folder
    ensure_folder(join(config.target_folder, 'jinja_dxr_cache'))

    # TODO: Make open-search.xml once we go to request-time rendering.

    ensure_folder(join(config.target_folder, 'trees'))


def ensure_folder(folder, clean=False):
    """Ensure the existence of a folder.

    :arg clean: Whether to ensure that the folder is empty

    """
    if clean and os.path.isdir(folder):
        shutil.rmtree(folder, False)
    if not os.path.isdir(folder):
        mkdir(folder)


def _unignored_folders(folders, source_path, ignore_patterns, ignore_paths):
    """Yield the folders from ``folders`` which are not ignored by the given
    patterns and paths.

    :arg source_path: Relative path to the source directory
    :arg ignore_patterns: Non-path-based globs to be ignored
    :arg ignore_paths: Path-based globs to be ignored

    """
    for folder in folders:
        if not any(fnmatchcase(folder, p) for p in ignore_patterns):
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


def unignored(folder, ignore_paths, ignore_patterns, want_folders=False):
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
                if any(fnmatchcase(f, e) for e in ignore_patterns):
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
            folders, rel_path, ignore_patterns, ignore_paths)
        if want_folders:
            for f in folders:
                yield join(root, f)


def index_file(tree, tree_indexers, path, es, index, jinja_env):
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

    num_lines = len(contents.splitlines())
    needles = {}
    links, refs, regions = [], [], []
    needles_by_line = [{} for _ in xrange(num_lines)]
    annotations_by_line = [[] for _ in xrange(num_lines)]

    for tree_indexer in tree_indexers:
        file_to_index = tree_indexer.file_to_index(rel_path, contents)
        if file_to_index.is_interesting():
            # Per-file stuff:
            append_update(needles, file_to_index.needles())
            links.extend(file_to_index.links())
            refs.extend(file_to_index.refs())
            regions.extend(file_to_index.regions())

            # Per-line stuff:
            if is_text:
                append_update_by_line(needles_by_line,
                                      file_to_index.needles_by_line())
                append_by_line(annotations_by_line,
                               file_to_index.annotations_by_line())


    # Index a doc of type 'file' so we can build folder listings.
    # At the moment, we send to ES in the same worker that does the indexing.
    # We could interpose an external queueing system, but I'm willing to
    # potentially sacrifice a little speed here for the easy management of
    # self-throttling.
    # TODO: Merge with the bulk_index below when pyelasticsearch supports
    # multi-doctype bulk indexing.
    file_info = stat(path)
    folder_name, file_name = split(rel_path)

    if is_text:  # conditional until we figure out how to display binary files
        es.index(index,
                 FILE_DOCTYPE,
                 # Hard-code the keys that are hard-coded in the browse()
                 # controller. Merge with the pluggable ones from needles:
                 dict(folder=folder_name,
                      name=file_name,
                      size=file_info.st_size,
                      modified=datetime.fromtimestamp(file_info.st_mtime),
                      is_folder=False,
                      **needles))

    # Index all the lines, attaching the file-wide needles to each line as well:
    if is_text and needles_by_line:  # If it's an empty file (no lines), don't
                                     # bother ES. It hates empty dicts.
        es.bulk_index(index,
                      LINE_DOCTYPE,
                      (merge(n, needles) for n in needles_by_line),
                      id_field=None)

    # Render some HTML:
    # TODO: Make this no longer conditional on is_text, and come up with a nice
    # way to show binary files, especially images.
    if is_text and 'html' not in tree.config.skip_stages:
        _fill_and_write_template(
            jinja_env,
            'file.html',
            join(tree.target_folder, rel_path + '.html'),
            {# Common template variables:
             'wwwroot': tree.config.wwwroot,
             'tree': tree.name,
             'tree_tuples': [(t.name,
                              browse_url(t.name, tree.config.wwwroot, rel_path),
                              t.description)
                             for t in tree.config.sorted_tree_order],
             'generated_date': tree.config.generated_date,
             'filters': filter_menu_items(),

             # File template variables:
             'paths_and_names': linked_pathname(rel_path, tree.name),
             'icon': icon(rel_path),
             'path': rel_path,
             'name': os.path.basename(rel_path),

             # Someday, it would be great to stream this and not concretize the
             # whole thing in RAM. The template will have to quit looping
             # through the whole thing 3 times.
             'lines': zip(build_lines(contents, refs, regions),
                          annotations_by_line) if is_text else [],

             'is_text': is_text,

             'sections': build_sections(links)})


def index_chunk(tree, tree_indexers, paths, index, swallow_exc=False):
    """Index a pile of files.

    This is the entrypoint for indexer pool workers.

    """
    path = '(no file yet)'
    try:
        es = ElasticSearch(tree.config.es_hosts)
        jinja_env = load_template_env()
        for path in paths:
            index_file(tree, tree_indexers, path, es, index, jinja_env)
    except Exception as exc:
        if swallow_exc:
            type, value, traceback = exc_info()
            return format_exc(), type, value, path
        else:
            raise


def index_files(tree, tree_indexers, index, pool, es):
    """Divide source files into groups, and send them out to be indexed."""

    def path_chunks(tree):
        """Return an iterable of worker-sized iterables of paths."""
        return chunks(500, unignored(tree.source_folder,
                                     tree.ignore_paths,
                                     tree.ignore_patterns))

    # Lay down all the containing folders so we can generate the file HTML in
    # parallel:
#    with es.bulk_indexing(doctype=FILE_DOCTYPE, index=, size=100) as indexer:
    for folder in unignored(
            tree.source_folder,
            tree.ignore_paths,
            tree.ignore_patterns,
            want_folders=True):
        rel_path = relpath(folder, tree.source_folder)
        mkdir(join(tree.target_folder, rel_path))
        superfolder_path, folder_name = split(rel_path)
#        indexer.index({
        es.index(index, FILE_DOCTYPE, {
            'path': rel_path,
            'folder': superfolder_path,
            'name': folder_name,
            'is_folder': True})

    if tree.config.disable_workers:
        for paths in path_chunks(tree):
            result = index_chunk(tree, tree_indexers, paths, index,
                                 swallow_exc=False)
    else:
        futures = [pool.submit(index_chunk, tree, tree_indexers, paths, index,
                               swallow_exc=True) for paths in path_chunks(tree)]
        for future in show_progress(futures, message=' - Indexing files.'):
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

    # Set up build environment variables:
    environ = os.environ.copy()
    for ti in tree_indexers:
        environ.update(ti.environment(environ))

    # Call make or whatever:
    with open_log(tree, 'build.log', verbose) as log:
        print "Building the '%s' tree" % tree.name
        r = subprocess.call(
            tree.build_command.replace('$jobs', str(tree.config.nb_jobs)),
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


def build_sections(links):
    """ Build navigation sections for template """
    # Sort by importance (resolve ties by section name)
    links = sorted(links, key=lambda section: (section[0], section[1]))
    # Return list of section and items (without importance)
    return [(section, list(items)) for importance, section, items in links]


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
        menu, value = self.payload
        menu = cgi.escape(json.dumps(menu), True)
        css_class = ''
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


def tag_boundaries(refs, regions):
    """Return a sequence of (offset, is_start, Region/Ref/Line) tuples.

    Basically, split the atomic tags that come out of plugins into separate
    start and end points, which can then be thrown together in a bag and sorted
    as the first step in the tag-balancing process.

    Like in Python slice notation, the offset of a tag refers to the index of
    the source code char it comes before.

    """
    for intervals, cls in [(regions, Region), (refs, Ref)]:
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
            if (start is not None and start != -1 and
                    end is not None and end != -1 and
                    start < end):
                yield start, True, tag
                yield end, False, tag


def line_boundaries(text):
    """Return a tag for the end of each line in a string.

    :arg text: Unicode

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


def build_lines(text, refs, regions):
    """Yield lines of Markup, with links and syntax coloring applied.

    :arg text: Unicode text of the file to htmlify. ``build_lines`` may not be
        used on binary files.

    """
    # Plugins return unicode offsets, not byte ones.

    # Get start and endpoints of intervals:
    tags = list(tag_boundaries(refs, regions))

    tags.extend(line_boundaries(text))
    tags.sort(key=nesting_order)  # balanced_tags undoes this, but we tolerate
                                  # that in html_lines().
    remove_overlapping_refs(tags)
    return html_lines(balanced_tags(tags), text.__getslice__)


_template_env = None
def load_template_env():
    """Load template environment (lazily)"""
    global _template_env
    if not _template_env:
        # Cache folder for jinja2
        # Create jinja2 environment
        _template_env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(
                        join(dirname(dxr.__file__), TEMPLATE_DIR)),
                auto_reload=False,
                autoescape=lambda template_name: template_name is None or template_name.endswith('.html')
        )
    return _template_env
