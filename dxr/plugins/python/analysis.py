"""Tools for analyzing a Python codebase as a whole. Analysis happens
before indexing in order to compute data that requires knowledge of the
entire codebase.

"""
import ast
import os
from collections import defaultdict
from warnings import warn

from dxr.build import unicode_contents
from dxr.plugins.python.utils import (ClassFunctionVisitorMixin,
                                      convert_node_to_fullname, package_for_module,
                                      path_to_module, ast_parse)


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
        self.names = {}
        self.ignore_paths = set()

        for path, encoding in paths:
            self._analyze_file(path, encoding)
        self._finish_analysis()

    def _analyze_file(self, path, encoding):
        """Analyze an individual file. If the file isn't valid Python, add
        it to the ignore_paths list on the analysis.

        """
        try:
            contents = unicode_contents(path, encoding)
            if contents is None:
                # Then we could not decode the file, nothing we can do here.
                return
            syntax_tree = ast_parse(contents)
        except (IOError, SyntaxError, TypeError, UnicodeDecodeError) as error:
            rel_path = os.path.relpath(path, self.source_folder)
            warn('Failed to analyze {filename} due to error "{error}".'.format(
                 filename=rel_path, error=error))
            self.ignore_paths.add(rel_path)
            return

        abs_module_name = path_to_module(self.python_path, path)  # e.g. package.sub.current_file
        visitor = AnalyzingNodeVisitor(abs_module_name, self)
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
            base_classes = self.get_base_classes(class_name, set([class_name]))

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

    def get_base_classes(self, absolute_class_name, seen):
        """Return a list of all the classes that the given class
        inherits from in their canonical form.

        :arg seen: The set of normalized base class names already known.  Python
            doesn't permit actual inheritance cycles, but we don't currently
            distinguish between a locally defined name and a name from the
            built-in namespace, so something like
            'class DeprecationWarning(DeprecationWarning)' (with no import
            needed for the built-in DeprecationWarning) would lead to a cycle.

        """
        for base in self.base_classes[absolute_class_name]:
            base = self.normalize_name(base)
            if base not in seen:
                seen.add(base)

                yield base
                for base_parent in self.get_base_classes(base, seen):
                    yield base_parent

    def get_derived_classes(self, absolute_class_name, seen):
        """Return a list of all the classes that derive from the given
        class in their canonical form.

        :arg seen: The set of normalized base class names already known.  Python
            doesn't permit actual inheritance cycles, but we don't currently
            distinguish between a locally defined name and a name from the
            built-in namespace, so something like
            'class DeprecationWarning(DeprecationWarning)' (with no import
            needed for the built-in DeprecationWarning) would lead to a cycle.

        """
        for derived in self.derived_classes[absolute_class_name]:
            if derived not in seen:
                seen.add(derived)

                yield derived
                for derived_child in self.get_derived_classes(derived, seen):
                    yield derived_child

    def normalize_name(self, absolute_local_name):
        """Given a local name, figure out the actual module that the
        thing that name points to lives and return that name.

        For example, if you have `from os import path` in a module
        called `foo.bar`, then the name `foo.bar.path` would return
        `os.path`.

        """
        while absolute_local_name in self.names:
            absolute_local_name = self.names[absolute_local_name]

        mod, var = absolute_local_name
        if mod is None:  # Assuming `var` contains an absolute module name
            return var

        # When you refer to `imported_module.foo`, we need to normalize the
        # `imported_module` prefix in case it's not the canonical name of
        # that module.
        if '.' in var:
            prefix, local_name = var.rsplit('.', 1)
            return self.normalize_name((mod, prefix)) + '.' + local_name
        else:
            return mod + "." + var


class AnalyzingNodeVisitor(ast.NodeVisitor, ClassFunctionVisitorMixin):
    """Node visitor that analyzes code for data we need prior to
    indexing, including:

    - A graph of imported names and the files that they were originally
      defined in.
    - A mapping of class names to the classes they inherit from.

    """
    def __init__(self, abs_module_name, tree_analysis):
        super(AnalyzingNodeVisitor, self).__init__()

        self.abs_module_name = abs_module_name  # name of the module we're walking
        self.tree_analysis = tree_analysis

    def visit_ClassDef(self, node):
        super(AnalyzingNodeVisitor, self).visit_ClassDef(node)

        # Save the base classes of any class we find.
        class_path = self.abs_module_name + '.' + node.name
        bases = []
        for base in node.bases:
            base_name = convert_node_to_fullname(base)
            if base_name:
                bases.append((self.abs_module_name, base_name))
        self.tree_analysis.base_classes[class_path] = bases

    def visit_ClassFunction(self, class_node, function_node):
        """Save any member functions we find on a class."""
        class_path = self.abs_module_name + '.' + class_node.name
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

        # We're processing statements like the following in the file
        # corresponding to <self.abs_module_name>:
        #   [from <node.module>] import <alias.name> as <alias.asname>
        #
        # Try to find `abs_import_name`, so that the above is equivalent to
        #   import <abs_import_name> as <local_name>
        # ...and store the mapping
        #   (abs_module_name, local_name) -> (abs_import_name)
        for alias in node.names:
            local_name = alias.asname or alias.name
            absolute_local_name = self.abs_module_name, local_name

            # TODO: we're assuming this is an absolute name, but it could also
            # be relative to the current package or a var
            abs_import_name = None, alias.name
            if isinstance(node, ast.ImportFrom):
                # `from . import x` means node.module is None.
                if node.module:
                    abs_import_name = node.module, alias.name
                else:
                    package_path = package_for_module(self.abs_module_name)
                    if package_path:
                        abs_import_name = package_path, alias.name
            if absolute_local_name != abs_import_name:
                self.tree_analysis.names[absolute_local_name] = abs_import_name
