from itertools import islice
from warnings import warn
import xml.parsers.expat as expat

from dxr.indexers import Extent, Position
from dxr.plugins.xbl.refs import PLUGIN_NAME, TypeRef


class XBLAnalyzer(object):
    def __init__(self, path, tree, contents, encoding):
        self.tree = tree
        self.path = path
        self.contents = contents
        self.lines = contents.splitlines(True)
        self.parser = expat.ParserCreate(encoding)
        # Stack of namespaces, issued by the 'id' attr of bindings.
        self.namespace = []
        self.needles = []
        self.refs = []
        # Late bind our custom handlers to the parser
        self.parser.StartElementHandler = self.StartElementHandler
        self.parser.EndElementHandler = self.EndElementHandler
        try:
            self.parser.Parse(self.contents.encode(encoding))
        except expat.ExpatError as err:
            warn('Exception occurred on parsing XBL file {}'.format(self.path.encode('utf-8')))
            warn(err.message)

    def extent_for_name(self, name):
        """Return Extent for the next occurrence of name."""
        # Because the parser does not provide location info on attr positions,
        # we can only search for them from the current position.

        # FIXME: if the name we're looking for appears twice, e.g.
        # <binding id="id">id</binding>, then we will pick up the wrong extent
        # for the "id" name.
        # First check the current line.
        offset = self.lines[self.parser.CurrentLineNumber - 1].find(name, self.parser.CurrentColumnNumber - 1)
        if offset != -1:
            row, col = self.parser.CurrentLineNumber, offset
            found = True
        else:
            found = False
        # Not on the current line, keep going until we find it.
        if not found:
            for number, line in enumerate(islice(self.lines,
                                                 self.parser.CurrentLineNumber,
                                                 len(self.lines))):
                offset = line.find(name)
                if offset != -1:
                    row, col = self.parser.CurrentLineNumber + number + 1, offset
                    found = True
                    break
        if found:
            return Extent(Position(row, col), Position(row, col + len(name)))
        else:
            warn('Could not find {} from line {}'.format(name, self.parser.CurrentLineNumber))

    def yield_ref(self, ref, name):
        """Yield the ref for the next occurrence of given name."""
        start = self.contents.find(name, self.parser.CurrentByteIndex)
        end = start + len(name)
        self.refs.append((start, end, ref))

    def yield_needle(self, name, ident, qualname=None):
        """Construct a needle with given name and mapping for the provided
        ident, optionally with a qualified component.
        """
        # If qualname is not provided, then use name.
        mapping = {'name': ident, 'qualname': qualname or ident}
        extent = self.extent_for_name(ident)
        if extent:
            self.needles.append((PLUGIN_NAME + '_' + name, mapping, extent))

    # Begin definitions of parser event handlers.

    def StartElementHandler(self, name, attrs):
        name = name.lower()
        if name == 'implementation' and 'implements' in attrs:
            for impl in attrs['implements'].split(','):
                impl_name = impl.strip()
                self.yield_needle('type', impl_name)
                self.yield_ref(TypeRef(self.tree, impl_name), impl_name)

        elif name == 'binding':
            # Enter the scope of a binding.
            self.namespace.append(attrs['id'])

        elif name in {'property', 'method', 'field'} and 'name' in attrs:
            def_name = attrs['name']
            # Build the qualified name from the most recent binding id.
            self.yield_needle('prop', def_name, u'{}#{}'.format(self.namespace[-1], def_name))

    def EndElementHandler(self, name):
        name = name.lower()
        if name == 'binding':
            # Left scope of a binding tag, pop the stack.
            self.namespace.pop()
