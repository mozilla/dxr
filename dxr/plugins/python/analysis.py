"""Tools for analyzing a Python codebase as a whole. Analysis happens
before indexing in order to compute data that requires knowledge of the
entire codebase.

"""
import ast
import os
from collections import defaultdict, namedtuple
from warnings import warn

from dxr.build import file_contents
from dxr.plugins.python.utils import (ClassFunctionVisitor,
                                      convert_node_to_name, package_for_module,
                                      path_to_module, QualNameVisitor,
                                      relative_module_path)


class TreeAnalysis(object):
    """Performs post-build analysis and stores the results."""

    def __init__(self, python_path, source_folder, paths):
        """Analyze the given paths.

        :arg python_path: Absolute path to the root folder where Python
        modules for the tree are stored.

        :arg source_folder: Absolute path to the root folder storing all the
        files in the tree. Used to generate relative paths when emitting
        warnings.

        :arg paths: Iterable containing tuples of the form (path, encoding)
        for each file that should be analyzed.
        """
        self.python_path = python_path
        self.source_folder = source_folder

        self.base_classes = defaultdict(list)
        self.derived_classes = defaultdict(list)
        self.class_functions = defaultdict(list)
        self.overridden_functions = defaultdict(list)
        self.overriding_functions = defaultdict(list)
        self.definition_tree = DefinitionTree()
        self.ignore_paths = set()

        for path, encoding in paths:
            self._analyze_file(path, encoding)
        self._finish_analysis()

    def _analyze_file(self, path, encoding):
        """Analyze an individual file. If the file isn't valid Python, add
        it to the ignore_paths list on the analysis.

        """
        try:
            syntax_tree = ast.parse(file_contents(path, encoding))
        except (SyntaxError, TypeError) as error:
            rel_path = os.path.relpath(path, self.source_folder)
            warn('Failed to analyze {filename} due to error "{error}".'.format(
                 filename=rel_path, error=error))
            self.ignore_paths.add(rel_path)
            return

        visitor = AnalyzingNodeVisitor(path, self)
        visitor.visit(syntax_tree)

    def _finish_analysis(self):
        """Finishes the analysis by computing some relations that
        depend on the entire tree having been analyzed, such as method
        overrides (which we can't compute until we've analyzed every
        class method).

        """
        # Compute derived classes from base class relations.
        for class_name, bases in self.base_classes.iteritems():
            for base_name in bases:
                base_name = self.normalize_name(base_name)
                self.derived_classes[base_name].append(class_name)

        # Compute which functions override other functions.
        for class_name, functions in self.class_functions.iteritems():
            functions = set(functions)
            base_classes = self.get_base_classes(class_name)

            # For each base class, find the union of functions within
            # the current class and functions in the base; those are
            # overridden methods!
            for base_class in base_classes:
                # Use get here to avoid modifying class_functions while
                # looping over it.
                base_class_functions = self.class_functions.get(base_class, set())
                matches = functions.intersection(base_class_functions)
                for match in matches:
                    function_qualname = class_name + '.' + match
                    overridden_qualname = base_class + '.' + match
                    self.overriding_functions[function_qualname].append(overridden_qualname)

        # Compute which functions are overridden by which (the reverse
        # of what we just computed above).
        for function, overridden_functions in self.overriding_functions.iteritems():
            for overridden_function in overridden_functions:
                self.overridden_functions[overridden_function].append(function)

    def get_base_classes(self, absolute_class_name):
        """Return a list of all the classes that the given class
        inherits from in their canonical form.

        """
        for base in self.base_classes[absolute_class_name]:
            base = self.normalize_name(base)
            yield base
            for base_parent in self.get_base_classes(base):
                yield base_parent

    def get_derived_classes(self, absolute_class_name):
        """Return a list of all the classes that derive from the given
        class in their canonical form.

        """
        for derived in self.derived_classes[absolute_class_name]:
            yield derived
            for derived_child in self.get_derived_classes(derived):
                yield derived_child

    def normalize_name(self, absolute_name):
        """Defer name normalization to the definition tree."""
        return self.definition_tree.normalize_name(absolute_name)

    def get_definition(self, absolute_name):
        """Defer definitions to the definition tree."""
        return self.definition_tree.get(absolute_name)


class AnalyzingNodeVisitor(ClassFunctionVisitor, QualNameVisitor):
    """Node visitor that analyzes code for data we need prior to
    indexing, including:

    - A graph of imported names and the files that they were originally
      defined in.
    - A mapping of class names to the classes they inherit from.

    """
    def __init__(self, path, tree_analysis):
        # Set before calling super().__init__ for QualNameVisitor.
        self.module_path = path_to_module(tree_analysis.python_path, path)
        super(AnalyzingNodeVisitor, self).__init__()

        self.path = relative_module_path(tree_analysis.python_path, path)
        self.tree_analysis = tree_analysis

    def visit_ClassDef(self, node):
        super(AnalyzingNodeVisitor, self).visit_ClassDef(node)

        # Save the base classes of any class we find.
        bases = []
        for base in node.bases:
            base_name = convert_node_to_name(base)
            if base_name:
                bases.append(self.module_path + '.' + base_name)
        self.tree_analysis.base_classes[node.qualname] = bases

        # Store the definition of this class.
        class_def = Definition(absolute_name=node.qualname, line=node.lineno,
                               col=node.col_offset, path=self.path)
        self.tree_analysis.definition_tree.add(class_def)

    def visit_FunctionDef(self, node):
        super(AnalyzingNodeVisitor, self).visit_FunctionDef(node)

        # Store definition of this function.
        function_def = Definition(absolute_name=node.qualname, line=node.lineno,
                                  col=node.col_offset, path=self.path)
        self.tree_analysis.definition_tree.add(function_def)

    def visit_ClassFunction(self, class_node, function_node):
        """Save any member functions we find on a class."""
        class_path = self.module_path + '.' + class_node.name
        self.tree_analysis.class_functions[class_path].append(function_node.name)

    def visit_Import(self, node):
        self.analyze_import(node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        self.analyze_import(node)
        self.generic_visit(node)

    def analyze_import(self, node):
        """Whenever we import something, remember the local name of what
        was imported and where it actually lives.

        """
        for alias in node.names:
            local_name = alias.asname or alias.name
            absolute_local_name = self.module_path + '.' + local_name

            import_name = alias.name
            if isinstance(node, ast.ImportFrom):
                # `from . import x` means node.module is None.
                if node.module:
                    import_name = node.module + '.' + import_name
                else:
                    package_path = package_for_module(self.module_path)
                    if package_path:
                        import_name = package_path + '.' + import_name

            import_tuple = Import(absolute_name=absolute_local_name,
                                  line=node.lineno, col=node.col_offset,
                                  import_name=import_name)
            self.tree_analysis.definition_tree.add(import_tuple)


# Namedtuples that are stored in DefinitionTree.
Definition = namedtuple('Definition', ('absolute_name', 'line', 'col', 'path'))
Import = namedtuple('Import', ('absolute_name', 'line', 'col', 'import_name'))


class DefinitionTree(object):
    """Stores definitions across the entire project, such as classes and
    functions, as well as the imports that link them together.

    """
    def __init__(self):
        self.modules = {}

    def add(self, definition):
        """Add a definition to the tree. """
        names = definition.absolute_name.split('.')
        scope = self.modules

        for name in names[:-1]:
            scope = scope.setdefault(name, {})
        scope[names[-1]] = definition

    def get(self, name):
        """Fetch the definition for the given name, following imports if
        necessary.

        If the definition is not found, return None. Top-level modules
        that have not been added to the tree are assumed external and
        valid, and definitions will be returned for them with no path
        or position data.
        """
        names = name.split('.')
        module_name = names.pop(0)
        value = self.modules.get(module_name, None)

        # If we don't even find the top-level module, assume this is a
        # built-in or external library.
        if not value:
            return Definition(name)

        for name in names:
            value = value.get(name, None)
            if not value:
                return None

            while isinstance(value, Import):  # Follow imports.
                value = self.get(value.import_name)

        return value

    def normalize_name(self, absolute_name):
        """Given a name, figure out the actual module that the thing
        that name points to lives and return that name.

        For example, if you have `from os import path` in a module
        called `foo.bar`, then the name `foo.bar.path` would return
        `os.path`.

        """
        definition = self.get(absolute_name)
        return definition.absolute_name if definition else absolute_name
