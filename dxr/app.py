from cStringIO import StringIO
from datetime import datetime
from functools import partial
from itertools import chain, izip
from logging import StreamHandler
import os
from os import chdir
from os.path import join, basename, split, dirname, relpath
from sys import stderr
from time import time
from mimetypes import guess_type
from urllib import quote_plus

from flask import (Blueprint, Flask, send_from_directory, current_app,
                   send_file, request, redirect, jsonify, render_template,
                   url_for)
from funcy import merge, imap
from pyelasticsearch import ElasticSearch
from werkzeug.exceptions import NotFound

from dxr.config import Config
from dxr.es import (filtered_query, frozen_config, frozen_configs,
                    es_alias_or_not_found)
from dxr.exceptions import BadTerm
from dxr.filters import FILE, LINE
from dxr.lines import (html_line, tags_per_line, triples_from_es_refs,
                       triples_from_es_regions, finished_tags)
from dxr.mime import icon, is_image, is_text
from dxr.plugins import plugins_named, all_plugins
from dxr.query import Query, filter_menu_items
from dxr.utils import (non_negative_int, decode_es_datetime, DXR_BLUEPRINT,
                       format_number, append_update, append_by_line, cumulative_sum)
from dxr.vcs import file_contents_at_rev

# Look in the 'dxr' package for static files, etc.:
dxr_blueprint = Blueprint(DXR_BLUEPRINT,
                          'dxr',
                          template_folder='static/templates',
                          # static_folder seems to register a "static" route
                          # with the blueprint so the url_prefix (set later)
                          # takes effect for static files when found through
                          # url_for('static', ...).
                          static_folder='static')


def make_app(config):
    """Return a DXR application which uses ``config`` as its configuration.

    Also set up the static and template folder.

    """
    app = Flask('dxr')
    app.dxr_config = config
    app.register_blueprint(dxr_blueprint, url_prefix=config.www_root)

    # Log to Apache's error log in production:
    app.logger.addHandler(StreamHandler(stderr))

    # Make an ES connection pool shared among all threads:
    app.es = ElasticSearch(config.es_hosts)

    return app


@dxr_blueprint.route('/')
def index():
    return redirect(url_for('.browse',
                            tree=current_app.dxr_config.default_tree))


@dxr_blueprint.route('/<tree>/search')
def search(tree):
    """Normalize params, and dispatch between JSON- and HTML-returning
    searches, based on Accept header.

    """
    # Normalize querystring params:
    config = current_app.dxr_config
    frozen = frozen_config(tree)
    req = request.values
    query_text = req.get('q', '')
    offset = non_negative_int(req.get('offset'), 0)
    limit = min(non_negative_int(req.get('limit'), 100), 1000)
    is_case_sensitive = req.get('case') == 'true'

    # Make a Query:
    query = Query(partial(current_app.es.search,
                          index=frozen['es_alias']),
                  query_text,
                  plugins_named(frozen['enabled_plugins']),
                  is_case_sensitive=is_case_sensitive)

    # Fire off one of the two search routines:
    searcher = _search_json if _request_wants_json() else _search_html
    return searcher(query, tree, query_text, is_case_sensitive, offset, limit, config)


def _search_json(query, tree, query_text, is_case_sensitive, offset, limit, config):
    """Do a normal search, and return the results as JSON."""
    try:
        count_and_results = query.results(offset, limit)
        # Convert to dicts for ease of manipulation in JS:
        results = [{'icon': icon,
                    'path': path,
                    'lines': [{'line_number': nb, 'line': l} for nb, l in lines],
                    'is_binary': is_binary}
                   for icon, path, lines, is_binary in count_and_results['results']]
    except BadTerm as exc:
        return jsonify({'error_html': exc.reason, 'error_level': 'warning'}), 400

    return jsonify({
        'www_root': config.www_root,
        'tree': tree,
        'results': results,
        'result_count': count_and_results['result_count'],
        'result_count_formatted': format_number(count_and_results['result_count']),
        'tree_tuples': _tree_tuples(query_text, is_case_sensitive)})


def _search_html(query, tree, query_text, is_case_sensitive, offset, limit, config):
    """Search a few different ways, and return the results as HTML.

    Try a "direct search" (for exact identifier matches, etc.). If that
    doesn't work, fall back to a normal search.

    """
    should_redirect = request.values.get('redirect') == 'true'

    # Try for a direct result:
    if should_redirect:  # always true in practice?
        result = query.direct_result()
        if result:
            path, line = result
            # TODO: Does this escape query_text properly?
            return redirect(
                '%s/%s/source/%s?from=%s%s#%i' %
                (config.www_root,
                 tree,
                 path,
                 query_text,
                 '&case=true' if is_case_sensitive else '',
                 line))

    frozen = frozen_config(tree)

    # Try a normal search:
    template_vars = {
            'filters': filter_menu_items(
                plugins_named(frozen['enabled_plugins'])),
            'generated_date': frozen['generated_date'],
            'google_analytics_key': config.google_analytics_key,
            'is_case_sensitive': is_case_sensitive,
            'query': query_text,
            'search_url': url_for('.search',
                                  tree=tree,
                                  q=query_text,
                                  redirect='false'),
            'top_of_tree': url_for('.browse', tree=tree),
            'tree': tree,
            'tree_tuples': _tree_tuples(query_text, is_case_sensitive),
            'www_root': config.www_root}

    return render_template('search.html', **template_vars)


def _tree_tuples(query_text, is_case_sensitive):
    """Return a list of rendering info for Switch Tree menu items."""
    return [(f['name'],
             url_for('.search',
                     tree=f['name'],
                     q=query_text,
                     **({'case': 'true'} if is_case_sensitive else {})),
             f['description'])
            for f in frozen_configs()]


@dxr_blueprint.route('/<tree>/raw/<path:path>')
def raw(tree, path):
    """Send raw data at path from tree, for binary things like images."""
    query = {
        'filter': {
            'term': {
                'path': path
            }
        }
    }
    results = current_app.es.search(
            query,
            index=es_alias_or_not_found(tree),
            doc_type=FILE,
            size=1)
    try:
        # we explicitly get index 0 because there should be exactly 1 result
        data = results['hits']['hits'][0]['_source']['raw_data'][0]
    except IndexError: # couldn't find the image
        raise NotFound
    data_file = StringIO(data.decode('base64'))
    return send_file(data_file, mimetype=guess_type(path)[0])


@dxr_blueprint.route('/<tree>/source/')
@dxr_blueprint.route('/<tree>/source/<path:path>')
def browse(tree, path=''):
    """Show a directory listing or a single file from one of the trees.

    Raise NotFound if path does not exist as either a folder or file.

    """
    config = current_app.dxr_config
    try:
        return _browse_folder(tree, path, config)
    except NotFound:
        frozen = frozen_config(tree)
        # Grab the FILE doc, just for the sidebar nav links:
        files = filtered_query(
            frozen['es_alias'],
            FILE,
            filter={'path': path},
            size=1,
            include=['links'])
        if not files:
            raise NotFound

        lines = filtered_query(
            frozen['es_alias'],
            LINE,
            filter={'path': path},
            sort=['number'],
            size=1000000,
            include=['content', 'refs', 'regions', 'annotations'])
        # Deref the content field in each document. We can do this because we
        # do not store empty lines in ES.
        for doc in lines:
            doc['content'] = doc['content'][0]

        return _browse_file(tree, path, lines, files[0], config, frozen['generated_date'])


def _browse_folder(tree, path, config):
    """Return a rendered folder listing for folder ``path``.

    Search for FILEs having folder == path. If any matches, render the folder
    listing. Otherwise, raise NotFound.

    """
    frozen = frozen_config(tree)

    files_and_folders = filtered_query(
        frozen['es_alias'],
        FILE,
        filter={'folder': path},
        sort=[{'is_folder': 'desc'}, 'name'],
        size=10000,
        exclude=['raw_data'])
    if not files_and_folders:
        raise NotFound

    return render_template(
        'folder.html',
        # Common template variables:
        www_root=config.www_root,
        tree=tree,
        tree_tuples=[
            (t['name'],
             url_for('.parallel', tree=t['name'], path=path),
             t['description'])
            for t in frozen_configs()],
        generated_date=frozen['generated_date'],
        google_analytics_key=config.google_analytics_key,
        paths_and_names=_linked_pathname(path, tree),
        filters=filter_menu_items(
            plugins_named(frozen['enabled_plugins'])),
        # Autofocus only at the root of each tree:
        should_autofocus_query=path == '',

        # Folder template variables:
        name=basename(path) or tree,
        path=path,
        files_and_folders=[
            (_icon_class_name(f),
             f['name'],
             decode_es_datetime(f['modified']) if 'modified' in f else None,
             f.get('size'),
             url_for('.browse', tree=tree, path=f['path'][0]),
             f.get('is_binary', [False])[0])
            for f in files_and_folders])


def skim_file(skimmers, num_lines):
    """Skim contents with all the skimmers, returning the things we need to
    make a template. Compare to dxr.build.index_file

    :arg skimmers: iterable of FileToSkim objects
    :arg num_lines: the number of lines in the file being skimmed
    """
    linkses, refses, regionses = [], [], []
    annotations_by_line = [[] for _ in xrange(num_lines)]
    for skimmer in skimmers:
        if skimmer.is_interesting():
            linkses.append(skimmer.links())
            refses.append(skimmer.refs())
            regionses.append(skimmer.regions())
            append_by_line(annotations_by_line, skimmer.annotations_by_line())
    links = [{'order': order,
              'heading': heading,
              'items': [{'icon': icon,
                         'title': title,
                         'href': href}
                        for icon, title, href in items]}
             for order, heading, items in
             chain.from_iterable(linkses)]
    return links, refses, regionses, annotations_by_line


def _build_common_file_template(tree, path, date, config):
    """Return a dictionary of the common required file template parameters.
    """
    return {
        # Common template variables:
        'www_root': config.www_root,
        'tree': tree,
        'tree_tuples':
            [(t['name'],
              url_for('.parallel', tree=t['name'], path=path),
              t['description'])
            for t in frozen_configs()],
        'generated_date': date,
        'google_analytics_key': config.google_analytics_key,
        'filters': filter_menu_items(
            plugins_named(frozen_config(tree)['enabled_plugins'])),
        # File template variables
        'paths_and_names': _linked_pathname(path, tree),
        'icon': icon(path),
        'path': path,
        'name': basename(path)
    }


def _browse_file(tree, path, line_docs, file_doc, config, date=None, contents=None):
    """Return a rendered page displaying a source file.

    :arg string tree: name of tree on which file is found
    :arg string path: relative path from tree root of file
    :arg list line_docs: LINE documents as defined in the mapping of core.py,
        where the `content` field is dereferenced
    :arg file_doc: the FILE document as defined in core.py
    :arg config: TreeConfig object of this tree
    :arg date: a formatted string representing the generated date, default to now
    :arg string contents: the contents of the source file, defaults to joining
        the `content` field of all line_docs
    """
    def sidebar_links(sections):
        """Return data structure to build nav sidebar from. ::

            [('Section Name', [{'icon': ..., 'title': ..., 'href': ...}])]

        """
        # Sort by order, resolving ties by section name:
        return sorted(sections, key=lambda section: (section['order'],
                                                     section['heading']))

    if not date:
        # Then assume that the file is generated now. Remark: we can't use this
        # as the default param because that is only evaluated once, so the same
        # time would always be used.
        date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

    common = _build_common_file_template(tree, path, date, config)
    links = file_doc.get('links', [])
    if is_image(path):
        return render_template(
            'image_file.html',
            **common)
    else:  # We don't allow browsing binary files, so this must be a text file.
        # We concretize the lines into a list because we iterate over it multiple times
        lines = [doc['content'] for doc in line_docs]
        if not contents:
            # If contents are not provided, we can reconstruct them by
            # stitching the lines together.
            contents = ''.join(lines)
        offsets = cumulative_sum(imap(len, lines))
        # Construct skimmer objects for all enabled plugins that define a
        # file_to_skim class.
        skimmers = [plugin.file_to_skim(path,
                                        contents,
                                        name,
                                        config.trees[tree],
                                        file_doc,
                                        line_docs)
                    for name, plugin in all_plugins().iteritems()
                    if plugin in config.trees[tree].enabled_plugins
                    and plugin.file_to_skim]
        skim_links, refses, regionses, annotationses = skim_file(skimmers, len(line_docs))
        index_refs = triples_from_es_refs(doc.get('refs', []) for doc in line_docs)
        index_regions = triples_from_es_regions(doc.get('regions', []) for doc in line_docs)
        tags = finished_tags(lines,
                             chain(chain.from_iterable(refses), index_refs),
                             chain(chain.from_iterable(regionses), index_regions))
        return render_template(
            'text_file.html',
            **merge(common, {
                # Someday, it would be great to stream this and not concretize
                # the whole thing in RAM. The template will have to quit
                # looping through the whole thing 3 times.
                'lines': [(html_line(doc['content'], tags_in_line, offset),
                           doc.get('annotations', []) + skim_annotations)
                          for doc, tags_in_line, offset, skim_annotations
                              in izip(line_docs, tags_per_line(tags), offsets, annotationses)],
                'is_text': True,
                'sections': sidebar_links(links + skim_links)}))

@dxr_blueprint.route('/<tree>/rev/<revision>/<path:path>')
def rev(tree, revision, path):
    """Display a page showing the file at path at specified revision by
    obtaining the contents from version control.
    """
    config = current_app.dxr_config
    tree_config = config.trees[tree]
    abs_path = join(tree_config.source_folder, path)
    contents = file_contents_at_rev(abs_path, revision)
    if contents is not None and is_text(contents):
        contents = contents.decode(tree_config.source_encoding)
        # We do some wrapping to mimic the JSON returned by an ES lines query.
        return _browse_file(tree,
                            path,
                            [{'content': line} for line in contents.splitlines(True)],
                            {},
                            config,
                            contents=contents)
    else:
        raise NotFound

def _linked_pathname(path, tree_name):
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


@dxr_blueprint.route('/<tree>/')
@dxr_blueprint.route('/<tree>')
def tree_root(tree):
    """Redirect requests for the tree root instead of giving 404s."""
    # Don't do a redirect and then 404; that's tacky:
    es_alias_or_not_found(tree)
    return redirect(tree + '/source/')


@dxr_blueprint.route('/<tree>/parallel/')
@dxr_blueprint.route('/<tree>/parallel/<path:path>')
def parallel(tree, path=''):
    """If a file or dir parallel to the given path exists in the given tree,
    redirect to it. Otherwise, redirect to the root of the given tree.

    Deferring this test lets us avoid doing 50 queries when drawing the Switch
    Tree menu when 50 trees are indexed: we check only when somebody actually
    chooses something.

    """
    config = current_app.dxr_config
    files = filtered_query(
        es_alias_or_not_found(tree),
        FILE,
        filter={'path': path.rstrip('/')},
        size=1,
        include=[])  # We don't really need anything.
    return redirect(('{root}/{tree}/source/{path}' if files else
                     '{root}/{tree}/source/').format(root=config.www_root,
                                                     tree=tree,
                                                     path=path))


def _icon_class_name(file_doc):
    """Return a string for the CSS class of the icon for file document."""
    if file_doc['is_folder']:
        return 'folder'
    class_name = icon(file_doc['name'])
    # for small images, we can turn the image into icon via javascript
    # if bigger than the cutoff, we mark it as too big and don't do this
    if file_doc['size'] > current_app.dxr_config.max_thumbnail_size:
        class_name += " too_fat"
    return class_name


def _request_wants_json():
    """Return whether the current request prefers JSON.

    Why check if json has a higher quality than HTML and not just go with the
    best match? Because some browsers accept on */* and we don't want to
    deliver JSON to an ordinary browser.

    """
    # From http://flask.pocoo.org/snippets/45/
    best = request.accept_mimetypes.best_match(['application/json',
                                                'text/html'])
    return (best == 'application/json' and
            request.accept_mimetypes[best] >
                    request.accept_mimetypes['text/html'])
