import ast
import os
import re
from contextlib import contextmanager
from dxr.utils import split_content_lines

# The actual check that Python uses seems to be done in C, but this
# regex was taken from lib2to3.pgen.tokenize.
encoding_re = re.compile(r'^[ \t\f]*#.*coding[:=][ \t]*([-\w.]+)')


def ast_parse(contents):
    """Return the abstract syntax parse tree of some Python file contents,
    stripped of the encoding cookie, if any.

    Solves a problem where compiling a unicode string with an encoding
    declaration is a SyntaxError in Python 2 (issue #22221).

    """
    return ast.parse(
        u''.join(
            # The encoding declaration is only meaningful in the top two lines.
            u'\n' if i < 2 and encoding_re.match(line) else line
            for i, line in enumerate(split_content_lines(contents))
        )
    )


def local_name(absolute_name):
    """Return the local part of an absolute name. For example,
    `os.path.join` would become `join`.

    """
    return absolute_name.rsplit('.', 1)[-1]


def package_for_module(abs_module_name):
    """Return the absolute package name of the given absolute module name, or
    None if this is a top-level module. For example:
        'package.subpackage.my_module' -> 'package.subpackage'
        'my_module' -> None

    """
    return abs_module_name.rsplit('.', 1)[0] if '.' in abs_module_name else None


def convert_node_to_name(node):
    """Convert an AST node to a name if possible. Return None if we
    can't (such as function calls).

    """
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return node.attr
    else:
        return None


def convert_node_to_fullname(node):
    """Convert an AST node to a full dotted name if possible. Return None
    if we can't (such as function calls).

    """
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        value_name = convert_node_to_name(node.value)
        if value_name:
            return value_name + '.' + node.attr
    else:
        return None


def path_to_module(python_path, module_path):
    """Convert a file path into a dotted module path, using the given
    python_path as the base directory that modules live in.

    """
    module_path = trim_end(module_path, '.py')
    module_path = trim_end(module_path, '/__init__')
    common_path = os.path.commonprefix([python_path, module_path])
    return module_path.replace(common_path, '', 1).replace('/', '.').strip('.')


def trim_end(string, end):
    if string.endswith(end):
        return string[:-len(end)]
    else:
        return string


class ClassFunctionVisitorMixin(object):
    """Mixin for NodeVisitors that detects member functions on classes
    and handles them specifically.

    """
    def __init__(self, *args, **kwargs):
        super(ClassFunctionVisitorMixin, self).__init__(*args, **kwargs)

        self._current_class = None
        self._visiting_class_functions = False

    def visit_ClassDef(self, node):
        old_class = self._current_class
        self._current_class = node
        with self._visit_class_functions(True):
            self.generic_visit(node)
        self._current_class = old_class

    def visit_FunctionDef(self, node):
        if self._visiting_class_functions:
            self.visit_ClassFunction(self._current_class, node)

        # Disable collection in case there are any inner functions.
        with self._visit_class_functions(False):
            self.generic_visit(node)

    def visit_ClassFunction(self, class_node, function_node):
        raise NotImplementedError()

    @contextmanager
    def _visit_class_functions(self, visiting):
        old = self._visiting_class_functions
        self._visiting_class_functions = visiting
        yield
        self._visiting_class_functions = old
