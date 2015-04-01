import ast
from contextlib import contextmanager


def package_for_module(module_path):
    return module_path.rsplit('.', 1)[0] if '.' in module_path else None


def convert_node_to_name(node):
    """Convert an AST node to a name if possible. Return None if we
    can't (such as function calls).

    """
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        value_name = convert_node_to_name(node.value)
        if value_name:
            return value_name + '.' + node.attr
    else:
        return None


def relative_module_path(python_path, module_path):
    """Covert an absolute path to a module to a path relative to the
    given python path.

    """
    return module_path.replace(python_path, '', 1).strip('/')


def path_to_module(python_path, module_path):
    """Convert a file path into a dotted module path, using the given
    python_path as the base directory that modules live in.

    """
    module_path = relative_module_path(python_path, module_path)
    module_path = trim_end(module_path, '.py')
    module_path = trim_end(module_path, '/__init__')
    return module_path.replace('/', '.')


def trim_end(string, end):
    if string.endswith(end):
        return string[:-len(end)]
    else:
        return string


def all_subclasses(cls):
    """Yield all subclasses for the given class."""
    for subclass in cls.__subclasses__():
        yield subclass
        for descendant in all_subclasses(subclass):
            yield descendant


# ast.NodeVisitor doesn't implement any of the visit_* methods, which
# means our subclasses can't just call super(...).visit_* when they've
# finished their specific tweaks. We can't call generic_visit directly
# either, or multiple inheritance would have them visit nodes multiple
# times.
#
# The solution is to build a base class that implements visit_* methods
# for all ast.AST subclasses that just calls generic_visit on the node.
ast_class_names = [cls.__name__ for cls in all_subclasses(ast.AST)]
def _visit(self, node):
    self.generic_visit(node)

generic_methods = dict(('visit_' + name, _visit) for name in ast_class_names)
GenericNodeVisitor = type('GenericNodeVisitor', (ast.NodeVisitor,),
                          generic_methods)


class ClassFunctionVisitor(GenericNodeVisitor):
    """Base class for NodeVisitors that detects member functions on
    classes and handles them specifically.

    """
    def __init__(self, *args, **kwargs):
        super(ClassFunctionVisitor, self).__init__(*args, **kwargs)

        self._current_class = None
        self._visiting_class_functions = False

    def visit_ClassDef(self, node):
        old_class = self._current_class
        self._current_class = node
        with self._visit_class_functions(True):
            super(ClassFunctionVisitor, self).visit_ClassDef(node)
        self._current_class = old_class

    def visit_FunctionDef(self, node):
        if self._visiting_class_functions:
            self.visit_ClassFunction(self._current_class, node)

        # Disable collection in case there are any inner functions.
        with self._visit_class_functions(False):
            super(ClassFunctionVisitor, self).visit_FunctionDef(node)

    def visit_ClassFunction(self, class_node, function_node):
        raise NotImplementedError()

    @contextmanager
    def _visit_class_functions(self, visiting):
        old = self._visiting_class_functions
        self._visiting_class_functions = visiting
        yield
        self._visiting_class_functions = old


class QualNameVisitor(GenericNodeVisitor):
    """NodeVisitor that adds a qualname property to ClassDef and
    FunctionDef nodes with their qualified name.

    """

    def __init__(self, *args, **kwargs):
        """Expects self.module_path to have the dotted path for the
        module being visited before this is called.

        """
        super(QualNameVisitor, self).__init__(*args, **kwargs)

        self._current_qualname_parts = [self.module_path]

    def visit_FunctionDef(self, node):
        with self._enter_qualname(node.name):
            node.qualname = self._current_qualname
            super(QualNameVisitor, self).visit_FunctionDef(node)

    def visit_ClassDef(self, node):
        with self._enter_qualname(node.name):
            node.qualname = self._current_qualname
            super(QualNameVisitor, self).visit_ClassDef(node)

    @property
    def _current_qualname(self):
        return '.'.join(self._current_qualname_parts)

    @contextmanager
    def _enter_qualname(self, name):
        self._current_qualname_parts.append(name)
        yield
        self._current_qualname_parts.pop()
