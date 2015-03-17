"""Machinery for interspersing lines of text with linked and colored regions

The typical entrypoints are es_lines() and html_line().

Within this file, "tag" means a tuple of (file-wide offset, is_start, payload).

"""
import cgi
try:
    from itertools import compress
except ImportError:
    from itertools import izip
    def compress(data, selectors):
        return (d for d, s in izip(data, selectors) if s)
import json
from warnings import warn

from jinja2 import Markup


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
        return {'class': self.payload}

    def closer(self):
        return {'closer': False}


class Ref(TagWriter):
    """Thing to open and close <a> tags"""
    sort_order = 1

    def opener(self):
        menuitems, hover = self.payload
        ret = {'menuitems': menuitems}
        if hover:
            ret['hover'] = hover
        return ret

    def closer(self):
        return {'closer': True}


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

    :arg refs: An iterable (doesn't have to be a list)
    :arg regions: An iterable (doesn't have to be a list)

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


def finished_tags(text, refs, regions):
    """Return an ordered iterable of properly nested tags which fully describe
    the refs and regions and their places in a file's text.

    :arg text: Unicode text of the file to htmlify. ``build_lines`` may not be
        used on binary files.

    """
    # Plugins return unicode offsets, not byte ones.

    # Get start and endpoints of intervals:
    tags = list(tag_boundaries(refs, regions))

    tags.extend(line_boundaries(text))

    # Sorting is actually not a significant use of time in an actual indexing
    # run.
    tags.sort(key=nesting_order)  # balanced_tags undoes this, but we tolerate
                                  # that in html_lines().
    remove_overlapping_refs(tags)
    return balanced_tags(tags)


def es_lines(tags):
    """Yield a list of dicts, one per source code line, that can be indexed
    into the ``tags`` field of the ``line`` doctype in elasticsearch.

    Convert from the per-file offsets of refs() and regions() to per-line ones.
    We include explicit, separate closers in the hashes because, in order to
    divide tags into line-based sets (including cutting some in half if they
    spanned lines), we already had to do all the work of ordering and
    balancing. There's no sense doing that again at request time.

    :arg tags: An iterable of ordered, non-overlapping, non-empty tag
        boundaries with Line endpoints at (and outermost at) the index of the
        end of each line.

    """
    line_offset = 0  # file-wide offset of the beginning of the line
    hashes = []
    for point, is_start, payload in tags:
        if payload is LINE:
            if not is_start:
                yield hashes
                hashes = []
                line_offset = point
        else:
            hash = payload.opener() if is_start else payload.closer()
            hash['pos'] = point - line_offset
            hashes.append(hash)
    # tags always ends with a LINE closer, so we don't need any additional
    # yield here to catch remnants.


def html_line(text, es_tags):
    """Return a line of Markup, interleaved with the refs and regions that
    decorate it.

    :arg es_tags: An ordered iterable of tags from an ES ``lines`` doc,
        representing regions and refs
    :arg text: The unicode text to decorate

    """
    def segments(text, es_tags):
        up_to = 0
        for tag in es_tags:
            pos = tag['pos']
            yield cgi.escape(text[up_to:pos].strip(u'\r\n'))
            up_to = pos
            if 'closer' in tag:  # It's a closer. Most common.
                yield '</a>' if tag['closer'] else '</span>'
            elif 'class' in tag:  # It's a span.
                yield u'<span class="%s">' % cgi.escape(tag['class'], True)
            else:  # It's a menu.
                menu = cgi.escape(json.dumps(tag['menuitems']), True)
                if 'hover' in tag:
                    title = ' title="' + cgi.escape(tag['hover'], True) + '"'
                else:
                    title = ''
                yield u'<a data-menu="%s"%s>' % (menu, title)
        yield text[up_to:]

    return Markup(u''.join(segments(text, es_tags)))
