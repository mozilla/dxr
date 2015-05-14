"""Tools for analyzing a Python codebase as a whole. Analysis happens
before indexing in order to compute data that requires knowledge of the
entire codebase.

"""
import ast
import os
from collections import defaultdict, namedtuple
from contextlib import contextmanager
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
        except (IOError, SyntaxError, TypeError) as error:
            rel_path = os.path.relpath(path, self.source_folder)
            warn('Failed to analyze {filename} due to error "{error}".'.format(
                 filename=rel_path, error=error))
            self.ignore_paths.add(rel_path)
            return

        abs_module_name = path_to_module(self.python_path, path)
        relative_path = relative_module_path(self.python_path, path)
        module = Module(abs_module_name, relative_path)
        import q
        q(abs_module_name)
        q(module.path)
        visitor = AnalyzingNodeVisitor(module, self)
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
    def __init__(self, module, tree_analysis):
        # Set before calling super().__init__ for QualNameVisitor.
        # Name of the module we're walking, e.g. package.sub.current_file
        self.abs_module_name = module.name
        super(AnalyzingNodeVisitor, self).__init__()

        self.module = module
        self.tree_analysis = tree_analysis

    def visit_ClassDef(self, node):
        super(AnalyzingNodeVisitor, self).visit_ClassDef(node)

        # Save the base classes of any class we find.
        bases = []
        for base in node.bases:
            base_name = convert_node_to_name(base)
            if base_name:
                bases.append(self.abs_module_name + '.' + base_name)
        self.tree_analysis.base_classes[node.qualname] = bases

        # Store the definition of this class.
        class_def = Definition(name=node.name, line=node.lineno,
                               col=node.col_offset)
        self.module.add(node.name, class_def)

    def visit_FunctionDef(self, node):
        super(AnalyzingNodeVisitor, self).visit_FunctionDef(node)

        # Store definition of this function.
        function_def = Definition(name=node.name, line=node.lineno,
                                  col=node.col_offset)
        import q
        q(self.module.name + ':' + node.name)
        self.module.add(node.name, function_def)

    def visit_ClassFunction(self, class_node, function_node):
        """Save any member functions we find on a class."""
        class_path = self.abs_module_name + '.' + class_node.name
        self.tree_analysis.class_functions[class_path].append(function_node.name)

    def visit_Import(self, node):
        """
        Save this import to the DefinitionTree. Handles imports of the
        form:

        import <alias.name> [as <alias.asname>]

        """
        for alias in node.names:
            local_name = alias.asname or alias.name
            _import = Import(name=local_name,
                             line=node.lineno, col=node.col_offset,
                             module_name=alias.name,
                             as_name=alias.asname)
            self.module.add(local_name, _import)

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """
        Save this import to the DefinitionTree. Handles imports of the
        form:

        from <node.module> import <alias.name> [as <alias.asname>]

        """
        for alias in node.names:
            local_name = alias.asname or alias.name

            _import = ImportFrom(name=local_name,
                                 line=node.lineno, col=node.col_offset,
                                 module_name=node.module,
                                 import_name=alias.name,
                                 as_name=alias.asname)
            self.module.add(local_name, _import)

        self.generic_visit(node)


class Definition(object):
    """
    Represents the definition of a name, whether it be defining a value,
    class, function, or even an imported value.
    """
    def __init__(self, name, line, col, module=None):
        self.name = name
        self.module = module
        self.line = line
        self.col = col

    @property
    def absolute_name(self):
        return self.module.name + '.' + self.name


class Import(Definition):
    """
    Represents an import statement of the form:

    import <self.module_name> [as <self.as_name>]

    """
    def __init__(self, name, line, col, module_name, as_name=None):
        super(Import, self).__init__(name, line, col)
        self.module_name = module_name
        self.as_name = as_name


class ImportFrom(Definition):
    """
    Represents an import statement of the form:

    from <self.module_name> import <self.import_name> [as <self.as_name>]

    """
    def __init__(self, name, line, col, module_name, import_name, as_name=None):
        super(ImportFrom, self).__init__(name, line, col)
        self.module_name = module_name
        self.import_name = import_name
        self.as_name = as_name


def is_import(definition):
    return isinstance(defintion, (Import, ImportFrom))


class Module(object):
    def __init__(self, name, path):
        self.name = name  # Absolute name
        self.path = path
        self.tree = None
        self.submodules = {}
        self.definitions = {}

    def add(self, name, definition):
        self.definitions[name] = definition
        definition.module = self

    @property
    def parent(self):
        if '.' not in self.name:
            return None
        else:
            parent_name = self.name.rsplit('.', 1)[0]
            return self.tree.get(parent_name)


class DefinitionTree(object):
    """Stores definitions across the entire project, such as classes and
    functions, as well as the imports that link them together.

    """
    def __init__(self):
        self.modules = {}

    def add_module(self, module):
        self.modules[module.name] = module
        module.tree = self

    def get(self, name):
        """Fetch the definition for the given name, following imports if
        necessary.

        If the definition is not found, return None. Top-level modules
        that have not been added to the tree are assumed external and
        valid, and definitions will be returned for them with no path
        or position data.
        """
        if '.' not in name:
            return self.modules.get(name, Module(name=name, path=None))

        abs_module_name, definition_name = name.rsplit('.', 1)
        module_names = abs_module_name.split('.')

        # If we don't even find the top-level module, assume this is a
        # built-in or external library.
        root_module_name = module_names.pop(0)
        module = self.modules.get(root_module_name, None)
        if not module:
            module = Module(name=root_module_name, path=None)
            import q
            q('EXTERNAL: ' + name)
            return Definition(name=name, line=None, col=None, module=module)

        for name in module_names:
            next_module = module.submodules.get(name, None)
            if not next_module:
                _import = module.definitions.get(name, None)
                if not is_import(_import):
                    return None

                module = self.follow_import(_import)

        definition = module.definitions.get(names[-1], None)
        if is_import(defintion):
            definition = self.follow_import(definition)
        return definition

    def follow_import(self, _import):
        if _import.module_name:
            module = self.get(_import.module_name)
        else:
            # Relative import.
            module = _import.module.parent

        if isinstance(_import, ImportFrom):
            definition = module.definitions.get(_import.import_name)
            if not definition:
                return module.submodules.get(_import.import_name)
            elif is_import(definition):
                return self.follow_import(definition)
            else:
                return definition
        else:
            return module

    def normalize_name(self, absolute_name):
        """Given a name, figure out the actual module that the thing
        that name points to lives and return that name.

        For example, if you have `from os import path` in a module
        called `foo.bar`, then the name `foo.bar.path` would return
        `os.path`.

        """
        definition = self.get(absolute_name)
        return definition.absolute_name if definition else absolute_name
