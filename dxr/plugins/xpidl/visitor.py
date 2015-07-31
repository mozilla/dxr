from cStringIO import StringIO
from itertools import ifilter

from os.path import relpath, join, basename, dirname, exists
from flask import url_for
from xpidl.header import (idl_basename, header, include, jsvalue_include,
                          infallible_includes, header_end, forward_decl,
                          write_interface, printComments)

from xpidl.xpidl import Attribute

from dxr.indexers import Ref, Extent, Position
from dxr.plugins.xpidl.filters import PLUGIN_NAME
from dxr.utils import search_url


def start_pos(name, location):
    """Return the last byte position on which we can find name in the
    location's line, resolving if necessary."""

    location.resolve()
    # FIXME: this approach gives the wrong answer if the name is repeated in the line;
    #  however it seems to work correctly in most real cases.
    return location._line.rfind(name) - location._colno + location._lexpos


def header_line_numbers(idl, filename):
    """Map each production to its line number in the header.

    See xpidl.header.print_header for more information. This method is essentially a copy,
    with fd.write calls replaced by line increments.
    """

    def number_lines(text):
        return len(text.splitlines())

    production_map = {}
    line = number_lines(header % {'filename': filename,
                                  'basename': idl_basename(filename)}) + 1

    foundinc = False
    for inc in idl.includes():
        if not foundinc:
            foundinc = True
            line += 1
        line += number_lines(include % {'basename': idl_basename(inc.filename)})

    if idl.needsJSTypes():
        line += number_lines(jsvalue_include)

    # Include some extra files if any attributes are infallible.
    for iface in [p for p in idl.productions if p.kind == 'interface']:
        for attr in [m for m in iface.members if isinstance(m, Attribute)]:
            if attr.infallible:
                line += number_lines(infallible_includes)
                break

    line += number_lines(header_end) + 1

    for p in idl.productions:
        production_map[p] = line
        if p.kind == 'cdata':
            line += number_lines(p.data)
        elif p.kind == 'forward':
            line += number_lines(forward_decl % {'name': p.name})
        elif p.kind == 'interface':
            # write_interface inserts a blank line at the start.
            production_map[p] += 1
            # Eh....
            fd = StringIO()
            write_interface(p, fd)
            line += len(fd.readlines())
        elif p.kind == 'typedef':
            fd = StringIO()
            printComments(fd, p.doccomments, '')
            line += len(fd.readlines())
            line += number_lines("typedef %s %s;\n\n" % (p.realtype.nativeType('in'),
                                                         p.name))

    return production_map


class IdlVisitor(object):
    """Traverse an IDL syntax tree and collect refs and needles."""

    def __init__(self, parser, contents, split_contents, rel_path, abs_path, include_folders,
                 header_path, tree_config):
        """
        Parse an IDL file and visit the productions of its AST, storing refs and needles for ES
        in self.refs and self.needles.

        Raise IdlError if the file cannot be parsed.

        :arg parser: IdlParser to use to parse the file
        :arg contents: the contents of the file, as a string
        :arg split_contents: the contents of the file, as a list of strings split by line
        :arg rel_path: relative path to the file from tree root
        :arg abs_path: absolute path to the file
        :arg include_folders: list of folders to use to resolve include directives
        :arg header_path: folder in which the generated header would be placed to make links
        :arg tree_config: A :class:`TreeConfig` object for the current tree
        """

        self.tree = tree_config
        # Hold on to the URL so we do not have to regenerate it everywhere.
        self.header_filename = basename(rel_path.replace('.idl', '.h'))
        header_path = relpath(join(header_path, self.header_filename),
                              self.tree.source_folder)
        self.generated_url = url_for('.browse',
                                     tree=self.tree.name,
                                     path=header_path)
        ast = parser.parse(contents, basename(rel_path))
        # For include statements, look in the same folder, then the other directories.
        # Might raise IdlError
        self.search_paths = [dirname(abs_path)] + include_folders
        ast.resolve(self.search_paths, parser)
        self.line_map = header_line_numbers(ast, self.header_filename)
        self.line_list = split_contents
        # List of (start, end, Ref) where start and end are byte offsets into the file.
        self.refs = []
        self.needles = []

        # Initiate visitations.
        for item in ast.productions:
            try:
                visit_method = getattr(self, 'visit_' + item.kind)
            except AttributeError:
                # TODO: can we do something useful for these?
                # Unhandled: {'builtin', 'cdata', 'native', 'attribute'}
                pass
            else:
                visit_method(item)

    def check_lineno(self, needle, line):
        """Check whether needle string appears on line; if it doesn't then try the one above and
        below.

        Return the line number (0-offset) where the needle appears nearest input line,
        None if needle not found nearby.

        """
        for lineno in [line, line - 1, line + 1]:
            # Make sure we stay in bounds.
            if 0 <= lineno < len(self.line_list):
                if needle in self.line_list[lineno]:
                    return lineno

    def make_extent(self, name, location):
        """Return an Extent for the given name in this Location, None if we cannot construct it."""

        # Remark: sometimes the location's line number is off by one (in either
        # direction), so we check the surroundings to make sure it's there.
        location.resolve()
        start_col = location._line.rfind(name)
        lineno = self.check_lineno(name, location._lineno)
        if lineno:
            return Extent(Position(lineno + 1, start_col),
                          Position(lineno + 1, start_col + len(name)))

    def yield_needle(self, name, mapping, extent):
        self.needles.append((PLUGIN_NAME + '_' + name, mapping, extent))

    def yield_name_needle(self, filter_name, name, location):
        """Yield a needle for an ES field that only has a name property."""

        extent = self.make_extent(name, location)
        if extent:
            self.yield_needle(filter_name, {'name': name}, extent)

    def yield_ref(self, start, end, menus):
        self.refs.append((start, end, Ref(menus)))

    def yield_name_ref(self, name, location, menus):
        """Yield menu refs for a particular name on given location."""

        start = start_pos(name, location)
        self.yield_ref(start, start + len(name), menus)

    def generated_menu(self, production):
        """Return a menu for jumping to corresponding C++ source using the line map."""

        return {
            'html': 'See generated source',
            'title': 'Go to this line in the generated C++ header file',
            'href': self.generated_url + '#%d' % self.line_map[production],
            'icon': 'jump'
        }

    def filtered_search_menu(self, filter_name, name, html='Find declaration',
                             title='Search for declarations.', icon='class'):
        return {
            'html': html,
            'title': title,
            'href': search_url(self.tree, '%s:%s' % (filter_name, name)),
            'icon': icon
        }

    def subclass_search_menu(self, name):
        return self.filtered_search_menu('derived', name, 'Find subclasses',
                                         'Search for children that derive this interface.',
                                         'class')

    def include_menu(self, item_path):
        return {
            'html': 'Jump to file',
            'title': 'Go to the target of the include statement',
            'href': url_for('.browse', tree=self.tree.name,
                            path=relpath(item_path, self.tree.source_folder)),
            'icon': 'jump'
        }

    def visit_interface(self, interface):
        # Yield refs for the members, methods, etc. of an interface (and the interface itself).
        if interface.base:
            # The interface that this one extends.
            self.yield_name_ref(interface.base, interface.location, [
                self.filtered_search_menu('type-decl', interface.base, icon='type'),
                self.subclass_search_menu(interface.base)
            ])
            self.yield_name_needle('derived', interface.base, interface.location)

        self.yield_name_ref(interface.name, interface.location, [
            self.filtered_search_menu('type', interface.name, html='Find definition',
                                      title='Search for definitions', icon='reference'),
            self.subclass_search_menu(interface.name),
            self.generated_menu(interface)
        ])
        self.yield_name_needle('type_decl', interface.name, interface.location)

        for member in interface.members:
            if member.kind == 'const' or member.kind == 'attribute':
                self.yield_name_ref(member.name, member.location, [
                    self.filtered_search_menu('var-decl', member.name, icon='field'),
                    self.filtered_search_menu('var', member.name, html='Find definition',
                                              title='Search for definitions', icon='field'),
                ])
                self.yield_name_needle('var_decl', member.name, member.location)

            elif member.kind == 'method':
                self.yield_name_ref(member.name, member.location, [
                    self.filtered_search_menu('function-decl', member.name, icon='method'),
                    self.filtered_search_menu('function', member.name, 'Find implementations',
                                              'Search for implementations of this method',
                                              'method')
                ])
                self.yield_name_needle('function_decl', member.name, member.location)

    def visit_include(self, item):
        filename = item.filename
        # Remark: it would be nice if the Include class held on to this data after it does the
        # same work.
        # We know that the parser resolved the include in the same way, so we assume we can
        # too and take the first element.
        resolved_path = next(ifilter(exists, (join(path, filename) for path in self.search_paths)))
        self.yield_name_ref(filename, item.location, [self.include_menu(resolved_path)])

    def visit_typedef(self, item):
        self.yield_name_ref(item.name, item.location, [self.generated_menu(item)])

    def visit_forward(self, item):
        self.yield_name_ref(item.name, item.location, [
            self.filtered_search_menu('type-decl', item.name, icon='type'),
            self.subclass_search_menu(item.name),
            self.generated_menu(item)
        ])
