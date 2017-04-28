from cStringIO import StringIO
from datetime import datetime
from functools import partial
from itertools import chain, izip
from logging import StreamHandler
import os
from os.path import join, basename, split, dirname
from sys import stderr
from mimetypes import guess_type

from flask import (Blueprint, Flask, current_app, send_file, request, redirect,
                   jsonify, render_template, url_for)
from funcy import merge
from pyelasticsearch import ElasticSearch
from werkzeug.exceptions import NotFound

from dxr.es import (filtered_query, frozen_config, frozen_configs,
                    es_alias_or_not_found)
from dxr.exceptions import BadTerm
from dxr.filters import FILE, LINE
from dxr.lines import html_line, tags_per_line, finished_tags, Ref, Region
from dxr.mime import icon, is_binary_image, is_textual_image, decode_data
from dxr.plugins import plugins_named
from dxr.query import Query, filter_menu_items
from dxr.utils import (non_negative_int, decode_es_datetime, DXR_BLUEPRINT,
                       format_number, append_by_line, build_offset_map,
                       split_content_lines)
from dxr.vcs import file_contents_at_rev

# Look in the 'dxr' package for static files, etc.:
dxr_blueprint = Blueprint(DXR_BLUEPRINT,
                          'dxr',
                          template_folder='templates',
                          # static_folder seems to register a "static" route
                          # with the blueprint so the url_prefix (set later)
                          # takes effect for static files when found through
                          # url_for('static', ...).
                          static_folder='static')


class HashedStatics(object):
    """A Flask extension which adds hashes to static asset URLs, as determined
    by a static_manifest file just outside the static folder"""

    def __init__(self, app=None):
        self.app = None
        self.manifests = {}
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        app.url_defaults(self._hashed_url)

    def _manifest_near(self, static_folder):
        """Cache and return a manifest for a specific static folder.

        The manifest must be in a file called "static_manifest" just outside
        the static folder.

        """
        manifest = self.manifests.get(static_folder)
        if manifest is None:
            try:
                with open(join(dirname(static_folder),
                               'static_manifest')) as file:
                    manifest = self.manifests[static_folder] = \
                        dict(line.split() for line in file)
            except IOError:
                # Probably no such file
                manifest = self.manifests[static_folder] = {}
        return manifest

    def _hashed_url(self, route, values):
        """Map an unhashed URL to a hashed one.

        If no mapping is found in the manifest, leave it alone, which will
        result in a 404.

        """
        if route == 'static' or route.endswith('.static'):
            filename = values.get('filename')
            if filename:
                blueprint = request.blueprint
                static_folder = (self.app.blueprints[blueprint].static_folder
                                 if blueprint else self.app.static_folder)
                manifest = self._manifest_near(static_folder)
                values['filename'] = manifest.get(filename, filename)


def make_app(config):
    """Return a DXR application which uses ``config`` as its configuration.

    Also set up the static and template folder.

    """
    app = Flask('dxr')
    app.dxr_config = config
    app.register_blueprint(dxr_blueprint, url_prefix=config.www_root)
    HashedStatics(app=app)

    # The url_prefix we pass when registering the blueprint is not stored
    # anywhere. This saves gymnastics in our custom URL builders to get it back:
    app.dxr_www_root = config.www_root

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

    # Make a Query:
    query = Query(partial(current_app.es.search,
                          index=frozen['es_alias']),
                  query_text,
                  plugins_named(frozen['enabled_plugins']))

    # Fire off one of the two search routines:
    searcher = _search_json if _request_wants_json() else _search_html
    return searcher(query, tree, query_text, offset, limit, config)


def _search_json(query, tree, query_text, offset, limit, config):
    """Try a "direct search" (for exact identifier matches, etc.). If we have a direct hit,
    then return {redirect: hit location}. If that doesn't work, fall back to a normal
    search, and if that yields a single result and redirect is true then return
    {redirect: hit location}, otherwise return the results as JSON.

    'redirect=true' along with 'redirect_type={direct, single}' control the behavior
    of jumping to results:
        * 'redirect_type=direct' indicates a direct_result result and comes with
          a bubble giving the option to switch to all results instead.
        * 'redirect_type=single' indicates a unique search result and comes with
          a bubble indicating as much.
    We only redirect to a direct/unique result if the original query contained a
    'redirect=true' parameter, which the user can elicit by hitting enter on the query
    input."""

    # If we're asked to redirect and have a direct hit, then return the url to that.
    if request.values.get('redirect') == 'true':
        result = query.direct_result()
        if result:
            path, line = result
            # TODO: Does this escape query_text properly?
            params = {
                'tree': tree,
                'path': path,
                'q': query_text,
                'redirect_type': 'direct'
            }
            return jsonify({'redirect': url_for('.browse', _anchor=line, **params)})
    try:
        count_and_results = query.results(offset, limit)
        # If we're asked to redirect and there's a single result, redirect to the result.
        if (request.values.get('redirect') == 'true' and
            count_and_results['result_count'] == 1):
            _, path, line = next(count_and_results['results'])
            line = line[0][0] if line else None
            params = {
                'tree': tree,
                'path': path,
                'q': query_text,
                'redirect_type': 'single'
            }
            return jsonify({'redirect': url_for('.browse', _anchor=line, **params)})
        # Convert to dicts for ease of manipulation in JS:
        results = [{'icon': icon,
                    'path': file_path,
                    'lines': [{'line_number': nb, 'line': l} for nb, l in lines]}
                   for icon, file_path, lines in count_and_results['results']]
    except BadTerm as exc:
        return jsonify({'error_html': exc.reason, 'error_level': 'warning'}), 400

    return jsonify({
        'www_root': config.www_root,
        'tree': tree,
        'results': results,
        'result_count': count_and_results['result_count'],
        'result_count_formatted': format_number(count_and_results['result_count']),
        'tree_tuples': _tree_tuples('.search', q=query_text)})


def _search_html(query, tree, query_text, offset, limit, config):
    """Return the rendered template for search.html.

    """
    frozen = frozen_config(tree)

    # Try a normal search:
    template_vars = {
            'filters': filter_menu_items(
                plugins_named(frozen['enabled_plugins'])),
            'generated_date': frozen['generated_date'],
            'google_analytics_key': config.google_analytics_key,
            'query': query_text,
            'search_url': url_for('.search',
                                  tree=tree,
                                  q=query_text,
                                  redirect='false'),
            'top_of_tree': url_for('.browse', tree=tree),
            'tree': tree,
            'tree_tuples': _tree_tuples('.search', q=query_text),
            'www_root': config.www_root}

    return render_template('search.html', **template_vars)


def _tree_tuples(endpoint, **kwargs):
    """Return a list of rendering info for Switch Tree menu items."""
    return [(f['name'],
             url_for(endpoint,
                     tree=f['name'],
                     **kwargs),
             f['description'],
             [(lang, color) for p in plugins_named(f['enabled_plugins'])
              for lang, color in sorted(p.badge_colors.iteritems())])
            for f in frozen_configs()]


@dxr_blueprint.route('/<tree>/raw/<path:path>')
def raw(tree, path):
    """Send raw data at path from tree, for binary things like images."""
    if not is_binary_image(path) and not is_textual_image(path):
        raise NotFound

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


@dxr_blueprint.route('/<tree>/raw-rev/<revision>/<path:path>')
def raw_rev(tree, revision, path):
    """Send raw data at path from tree at the given revision, for binary things
    like images."""
    if not is_binary_image(path) and not is_textual_image(path):
        raise NotFound

    config = current_app.dxr_config
    tree_config = config.trees[tree]
    data = file_contents_at_rev(tree_config.source_folder, path, revision)
    if data is None:
        raise NotFound
    data_file = StringIO(data)
    return send_file(data_file, mimetype=guess_type(path)[0])


@dxr_blueprint.route('/<tree>/lines/')
def lines(tree):
    """Return lines start:end of path in tree, where start, end, path are URL params.
    """
    req = request.values
    path = req.get('path', '')
    from_line = max(0, int(req.get('start', '')))
    to_line = int(req.get('end', ''))
    ctx_found = []
    possible_hits = current_app.es.search(
            {
                'filter': {
                    'and': [
                        {'term': {'path': path}},
                        {'range': {'number': {'gte': from_line, 'lte': to_line}}}
                        ]
                    },
                '_source': {'include': ['content']},
                'sort': ['number']
            },
            size=max(0, to_line - from_line + 1), # keep it non-negative
            doc_type=LINE,
            index=es_alias_or_not_found(tree))
    if 'hits' in possible_hits and len(possible_hits['hits']['hits']) > 0:
        for hit in possible_hits['hits']['hits']:
            ctx_found.append({'line_number': hit['sort'][0],
                              'line': hit['_source']['content'][0]})

    return jsonify({'lines': ctx_found, 'path': path})


@dxr_blueprint.route('/<tree>/source/')
@dxr_blueprint.route('/<tree>/source/<path:path>')
def browse(tree, path=''):
    """Show a directory listing or a single file from one of the trees.

    Raise NotFound if path does not exist as either a folder or file.

    """
    config = current_app.dxr_config
    try:
        # Strip any trailing slash because we do not store it in ES.
        return _browse_folder(tree, path.rstrip('/'), config)
    except NotFound:
        frozen = frozen_config(tree)
        # Grab the FILE doc, just for the sidebar nav links and the symlink target:
        files = filtered_query(
            frozen['es_alias'],
            FILE,
            filter={'path': path},
            size=1,
            include=['link', 'links', 'is_binary'])
        if not files:
            raise NotFound
        file_doc = files[0]
        if 'link' in file_doc:
            # Then this path is a symlink, so redirect to the real thing.
            return redirect(url_for('.browse', tree=tree, path=file_doc['link'][0]))

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

        return _browse_file(tree, path, lines, file_doc, config,
                            file_doc.get('is_binary', [False])[0],
                            frozen['generated_date'])


def concat_plugin_headers(plugin_list):
    """Return a list of the concatenation of all browse_headers in the
    FolderToIndexes of given plugin list.

    """
    return list(chain.from_iterable(p.folder_to_index.browse_headers
                                    for p in plugin_list if p.folder_to_index))


def _browse_folder(tree, path, config):
    """Return a rendered folder listing for folder ``path``.

    Search for FILEs having folder == path. If any matches, render the folder
    listing. Otherwise, raise NotFound.

    """
    def item_or_list(item):
        """If item is a list, return its first element.

        Otherwise, just return it.

        """
        # TODO @pelmers: remove this function when format bumps to 20
        if isinstance(item, list):
            return item[0]
        return item

    frozen = frozen_config(tree)

    plugin_headers = concat_plugin_headers(plugins_named(frozen['enabled_plugins']))
    files_and_folders = filtered_query(
        frozen['es_alias'],
        FILE,
        filter={'folder': path},
        sort=[{'is_folder': 'desc'}, 'name'],
        size=1000000,
        include=['name', 'modified', 'size', 'link', 'path', 'is_binary',
                 'is_folder'] + plugin_headers)

    if not files_and_folders:
        raise NotFound

    return render_template(
        'folder.html',
        # Common template variables:
        www_root=config.www_root,
        tree=tree,
        tree_tuples=_tree_tuples('.parallel', path=path),
        generated_date=frozen['generated_date'],
        google_analytics_key=config.google_analytics_key,
        paths_and_names=_linked_pathname(path, tree),
        plugin_headers=plugin_headers,
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
             decode_es_datetime(item_or_list(f['modified'])) if 'modified' in f else None,
             f.get('size'),
             [f.get(h, [''])[0] for h in plugin_headers],
             url_for('.browse', tree=tree, path=f.get('link', f['path'])[0]))
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
    links = dictify_links(chain.from_iterable(linkses))
    return links, refses, regionses, annotations_by_line


def _build_common_file_template(tree, path, is_binary, date, config):
    """Return a dictionary of the common required file template parameters.
    """
    return {
        # Common template variables:
        'www_root': config.www_root,
        'tree': tree,
        'tree_tuples': _tree_tuples('.parallel', path=path),
        'generated_date': date,
        'google_analytics_key': config.google_analytics_key,
        'filters': filter_menu_items(
            plugins_named(frozen_config(tree)['enabled_plugins'])),
        # File template variables
        'paths_and_names': _linked_pathname(path, tree),
        'icon_url': url_for('.static',
                            filename='icons/mimetypes/%s.png' % icon(path, is_binary)),
        'path': path,
        'name': basename(path)
    }


def _browse_file(tree, path, line_docs, file_doc, config, is_binary,
                 date=None, contents=None, image_rev=None):
    """Return a rendered page displaying a source file.

    :arg string tree: name of tree on which file is found
    :arg string path: relative path from tree root of file
    :arg list line_docs: LINE documents as defined in the mapping of core.py,
        where the `content` field is dereferenced
    :arg file_doc: the FILE document as defined in core.py
    :arg config: TreeConfig object of this tree
    :arg is_binary: Whether file is binary or not
    :arg date: a formatted string representing the generated date, default to now
    :arg string contents: the contents of the source file, defaults to joining
        the `content` field of all line_docs
    :arg image_rev: revision number of a textual or binary image, for images
        displayed at a certain rev
    """
    def process_link_templates(sections):
        """Look for {{line}} in the links of given sections, and duplicate them onto
        a 'template' field.
        """
        for section in sections:
            for link in section['items']:
                if '{{line}}' in link['href']:
                    link['template'] = link['href']
                    link['href'] = link['href'].replace('{{line}}', '')

    def sidebar_links(sections):
        """Return data structure to build nav sidebar from. ::

            [('Section Name', [{'icon': ..., 'title': ..., 'href': ...}])]

        """
        process_link_templates(sections)
        # Sort by order, resolving ties by section name:
        return sorted(sections, key=lambda section: (section['order'],
                                                     section['heading']))

    if not date:
        # Then assume that the file is generated now. Remark: we can't use this
        # as the default param because that is only evaluated once, so the same
        # time would always be used.
        date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

    common = _build_common_file_template(tree, path, is_binary, date, config)
    links = file_doc.get('links', [])
    if is_binary_image(path):
        return render_template(
            'image_file.html',
            **merge(common, {
                'sections': sidebar_links(links),
                'revision': image_rev}))
    elif is_binary:
        return render_template(
            'text_file.html',
            **merge(common, {
                'lines': [],
                'is_binary': True,
                'sections': sidebar_links(links)}))
    else:
        # We concretize the lines into a list because we iterate over it multiple times
        lines = [doc['content'] for doc in line_docs]
        if not contents:
            # If contents are not provided, we can reconstruct them by
            # stitching the lines together.
            contents = ''.join(lines)
        offsets = build_offset_map(lines)
        tree_config = config.trees[tree]
        if is_textual_image(path) and image_rev:
            # Add a link to view textual images on revs:
            links.extend(dictify_links([
                (4,
                 'Image',
                 [('svgview', 'View', url_for('.raw_rev',
                                              tree=tree_config.name,
                                              path=path,
                                              revision=image_rev))])]))
        # Construct skimmer objects for all enabled plugins that define a
        # file_to_skim class.
        skimmers = [plugin.file_to_skim(path,
                                        contents,
                                        plugin.name,
                                        tree_config,
                                        file_doc,
                                        line_docs)
                    for plugin in tree_config.enabled_plugins
                    if plugin.file_to_skim]
        skim_links, refses, regionses, annotationses = skim_file(skimmers, len(line_docs))
        index_refs = (Ref.es_to_triple(ref, tree_config) for ref in
                      chain.from_iterable(doc.get('refs', [])
                                          for doc in line_docs))
        index_regions = (Region.es_to_triple(region) for region in
                         chain.from_iterable(doc.get('regions', [])
                                             for doc in line_docs))
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
                'sections': sidebar_links(links + skim_links),
                'query': request.args.get('q', ''),
                'bubble': request.args.get('redirect_type')}))


@dxr_blueprint.route('/<tree>/rev/<revision>/<path:path>')
def rev(tree, revision, path):
    """Display a page showing the file at path at specified revision by
    obtaining the contents from version control.
    """
    config = current_app.dxr_config
    tree_config = config.trees[tree]
    contents = file_contents_at_rev(tree_config.source_folder, path, revision)
    if contents is not None:
        image_rev = None
        if is_binary_image(path):
            is_text = False
            contents = ''
            image_rev = revision
        else:
            is_text, contents = decode_data(contents, tree_config.source_encoding)
            if not is_text:
                contents = ''
            elif is_textual_image(path):
                image_rev = revision

        # We do some wrapping to mimic the JSON returned by an ES lines query.
        return _browse_file(tree,
                            path,
                            [{'content': line} for line in split_content_lines(contents)],
                            {},
                            config,
                            not is_text,
                            contents=contents,
                            image_rev=image_rev)
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
    class_name = icon(file_doc['name'], file_doc.get('is_binary', [False])[0])
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


def dictify_links(links):
    """Return a chain of order, heading, items links as a list of dicts."""
    return [{'order': order,
             'heading': heading,
             'items': [{'icon': icon,
                        'title': title,
                        'href': href}
                       for icon, title, href in items]}
            for order, heading, items in links]
