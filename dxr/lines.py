"""Machinery for interspersing lines of text with linked and colored regions

The typical entrypoints are es_lines() and html_line().

Within this file, "tag" means a tuple of (file-wide offset, is_start, payload).

"""
import cgi
from itertools import chain
try:
    from itertools import compress
except ImportError:
    from itertools import izip
    def compress(data, selectors):
        return (d for d, s in izip(data, selectors) if s)
import json
from warnings import warn

from jinja2 import Markup

from dxr.plugins import all_plugins
from dxr.utils import without_ending


class Line(object):
    """Representation of a line's beginning and ending as the contents of a tag

    Exists to motivate the balancing machinery to close all the tags at the end
    of every line (and reopen any afterward that span lines).

    """
    sort_order = 0  # Sort Lines outermost.

    def __repr__(self):
        return 'Line()'

LINE = Line()


class RefClassIdTagger(type):
    """Metaclass which automatically generates an ``id`` attr on the class as
    a serializable class identifier.

    Having a dedicated identifier allows Ref subclasses to move or change name
    without breaking index compatibility.

    Expects a ``_plugin`` attr to use as a prefix.

    """
    def __new__(metaclass, name, bases, dict):
        dict['id'] = without_ending('Ref', name)
        return type.__new__(metaclass, name, bases, dict)


class Ref(object):
    """Abstract superclass for a cross-reference attached to a run of text

    Carries enough data to construct a context menu, highlight instances of
    the same symbol, and show something informative on hover.

    """
    sort_order = 1
    __slots__ = ['menu_data', 'hover', 'qualname_hash']
    __metaclass__ = RefClassIdTagger

    def __init__(self, tree, menu_data, hover=None, qualname=None, qualname_hash=None):
        """
        :arg menu_data: Arbitrary JSON-serializable data from which we can
            construct a context menu
        :arg hover: The contents of the <a> tag's title attribute. (The first
            one wins.)
        :arg qualname: A hashable unique identifier for the symbol surrounded
            by this ref, for highlighting
        :arg qualname_hash: The hashed version of ``qualname``, which you can
            pass instead of ``qualname`` if you have access to the
            already-hashed version

        """
        self.tree = tree
        self.menu_data = menu_data
        self.hover = hover
        self.qualname_hash = hash(qualname) if qualname else qualname_hash

    def es(self):
        """Return a serialization of myself to store in elasticsearch."""
        ret = {'plugin': self.plugin,
               'id': self.id,
               # Smash the data into a string, because it will have a
               # different schema from subclass to subclass, and ES will freak
               # out:
               'menu_data': json.dumps(self.menu_data)}
        if self.hover:
            ret['hover'] = self.hover
        if self.qualname_hash is not None:  # could be 0
            ret['qualname_hash'] = self.qualname_hash
        return ret

    @staticmethod
    def es_to_triple(es_data, tree):
        """Convert ES-dwelling ref representation to a (start, end,
        :class:`~dxr.lines.Ref` subclass) triple.

        Return a subclass of Ref, chosen according to the ES data. Into its
        attributes "menu_data", "hover" and "qualname_hash", copy the ES
        properties of the same names, JSON-decoding "menu_data" first.

        :arg es_data: An item from the array under the 'refs' key of an ES LINE
            document
        :arg tree: The :class:`~dxr.config.TreeConfig` representing the tree
            from which the ``es_data`` was pulled

        """
        def ref_class(plugin, id):
            """Return the subclass of Ref identified by a combination of
            plugin and class ID."""
            plugins = all_plugins()
            try:
                return plugins[plugin].refs[id]
            except KeyError:
                warn('Ref subclass from plugin %s with ID %s was referenced '
                     'in the index but not found in the current '
                     'implementation. Ignored.' % (plugin, id))

        payload = es_data['payload']
        cls = ref_class(payload['plugin'], payload['id'])
        return (es_data['start'],
                es_data['end'],
                cls(tree,
                    json.loads(payload['menu_data']),
                    hover=payload.get('hover'),
                    qualname_hash=payload.get('qualname_hash')))

    def menu_items(self):
        """Return an iterable of menu items to be attached to a ref.

        Return an iterable of dicts of this form::

            {
                html: the HTML to be used as the menu item itself
                href: the URL to visit when the menu item is chosen
                title: the tooltip text given on hovering over the menu item
                icon: the icon to show next to the menu item: the name of a PNG
                    from the ``icons`` folder, without the .png extension
            }

        Typically, this pulls data out of ``self.menu_data``.

        """
        raise NotImplementedError

    def opener(self):
        """Emit the opening anchor tag for a cross reference.

        Menu item text, links, and metadata are JSON-encoded and dumped into a
        data attr on the tag. JS finds them there and creates a menu on click.

        """
        if self.hover:
            title = ' title="' + cgi.escape(self.hover, True) + '"'
        else:
            title = ''
        if self.qualname_hash is not None:
            cls = ' data-id="tok%i"' % self.qualname_hash
        else:
            cls = ''

        menu_items = list(self.menu_items())
        return u'<a data-menu="%s"%s%s>' % (
            cgi.escape(json.dumps(menu_items), True),
            title,
            cls)

    def closer(self):
        return u'</a>'


class Region(object):
    """A <span> tag with a CSS class, wrapped around a run of text"""

    # Sort Regions innermost, as it doesn't matter if we split them.
    sort_order = 2
    __slots__ = ['css_class']

    def __init__(self, css_class):
        self.css_class = css_class

    def es(self):
        return self.css_class

    @classmethod
    def es_to_triple(cls, es_region):
        """Convert ES-dwelling region representation to a (start, end,
        :class:`~dxr.lines.Region`) triple."""
        return es_region['start'], es_region['end'], cls(es_region['payload'])

    def opener(self):
        return u'<span class="%s">' % cgi.escape(self.css_class, True)

    def closer(self):
        return u'</span>'

    def __repr__(self):
        """Return a nice representation for debugging."""
        return 'Region("%s")' % self.css_class


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


def tag_boundaries(tags):
    """Return a sequence of (offset, is_start, Region/Ref/Line) tuples.

    Basically, split the atomic tags that come out of plugins into separate
    start and end points, which can then be thrown together in a bag and sorted
    as the first step in the tag-balancing process.

    Like in Python slice notation, the offset of a tag refers to the index of
    the source code char it comes before.

    :arg tags: An iterable of (start, end, Ref) and (start, end, Region) tuples

    """
    for start, end, data in tags:
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
            yield start, True, data
            yield end, False, data


def line_boundaries(lines):
    """Return a tag for the end of each line in a string.

    :arg lines: iterable of the contents of lines in a file, including any
        trailing newline character

    Endpoints and start points are coincident: right after a (universal)
    newline.

    """
    up_to = 0
    for line in lines:
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


def finished_tags(lines, refs, regions):
    """Return an ordered iterable of properly nested tags which fully describe
    the refs and regions and their places in a file's text.

    :arg lines: iterable of lines of text of the file to htmlify.

    Benchmarking reveals that this function is O(number of tags) in practice,
    on inputs on the order of thousands of lines. On my laptop, it takes .02s
    for a 3000-line file with some pygmentize regions and some python refs.

    """
    # Plugins return unicode offsets, not byte ones.

    # balanced_tags undoes the sorting, but we tolerate that in html_lines().
    # Remark: this sort is the memory peak, but it is not a significant use of
    # time in an indexing run.
    tags = sorted(chain(tag_boundaries(chain(refs, regions)),
                        line_boundaries(lines)),
                  key=nesting_order)
    remove_overlapping_refs(tags)
    return balanced_tags(tags)


def tags_per_line(flat_tags):
    """Split tags on LINE tags, yielding the tags of one line at a time
       (no LINE tags are yielded)

    :arg flat_tags: An iterable of ordered, non-overlapping, non-empty tag
        boundaries with Line endpoints at (and outermost at) the index of the
        end of each line.

    """
    tags = []
    for tag in flat_tags:
        point, is_start, payload = tag
        if payload is LINE:
            if not is_start:
                yield tags
                tags = []
        else:
            tags.append(tag)


def es_lines(tags):
    """Yield lists of dicts, one per source code line, that can be indexed
    into the ``refs`` or ``regions`` field of the ``line`` doctype in
    elasticsearch, depending on the payload type.

    :arg tags: An iterable of ordered, non-overlapping, non-empty tag
        boundaries with Line endpoints at (and outermost at) the index of the
        end of each line.

    """
    for line in tags_per_line(tags):
        payloads = {}
        for pos, is_start, payload in line:
            if is_start:
                payloads[payload] = {'start': pos}
            else:
                payloads[payload]['end'] = pos
        # Index objects are refs or regions. Regions' payloads are just
        # strings; refs' payloads are objects. See mappings in plugins/core.py
        yield [{'payload': payload.es(),
                'start': pos['start'],
                'end': pos['end']}
               for payload, pos in payloads.iteritems()]
    # tags always ends with a LINE closer, so we don't need any additional
    # yield here to catch remnants.


def html_line(text, tags, bof_offset):
    """Return a line of Markup, interleaved with the refs and regions that
    decorate it.

    :arg tags: An ordered iterable of tags from output of finished_tags
        representing regions and refs
    :arg text: The unicode text to decorate
    :arg bof_offset: The byte position of the start of the line from the
        beginning of the file.

    """
    def segments(text, tags, bof_offset):
        up_to = 0
        for pos, is_start, payload in tags:
            # Convert from file-based position to line-based position.
            pos -= bof_offset
            yield cgi.escape(text[up_to:pos])
            up_to = pos
            if not is_start:  # It's a closer. Most common.
                yield payload.closer()
            else:
                yield payload.opener()
        yield cgi.escape(text[up_to:])

    return Markup(u''.join(segments(text, tags, bof_offset)))
