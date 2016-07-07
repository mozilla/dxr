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
            self.parser.Parse(self.contents)
        except expat.ExpatError as err:
            warn('Exception occurred on parsing XBL file {}'.format(self.path))
            warn(err.message)

    def extent_for_name(self, name):
        """Return Extent for the next occurrence of name."""
        # Because the parser does not provide location info on attr positions,
        # we can only search for them from the current position.
        # First check the current line.
        offset = self.lines[self.parser.CurrentLineNumber - 1].find(name, self.parser.currentColumnNumber - 1)
        if offset != -1:
            row, col = self.parser.CurrentLineNumber, offset
            found = True
        else:
            found = False
        # Not on the current line, keep going until we find it.
        if not found:
            for number, line in enumerate(self.lines[self.parser.CurrentLineNumber:]):
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
        if 'implementation' == name:
            for impl in attrs['implements'].split(','):
                impl_name = impl.strip()
                self.yield_needle('type', impl_name)
                self.yield_ref(TypeRef(self.tree, impl_name), impl_name)

        elif 'binding' in name:
            # Enter the scope of a binding.
            self.namespace.append(attrs['id'])

        elif 'property' in name or 'method' in name or 'field' in name:
            def_name = attrs['name']
            # Build the qualified name from the most recent binding id.
            self.yield_needle('prop', def_name, '{}#{}'.format(self.namespace[-1], def_name))

    def EndElementHandler(self, name):
        if 'binding' in name:
            # Left scope of a binding tag, pop the stack.
            self.namespace.pop()
