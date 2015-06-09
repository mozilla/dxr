from itertools import chain


from dxr.indexers import unsparsify
from dxr.plugins.clang.condense import functions, symbols, properties


def function_needles_sparse(condensed):
    return (('js-function', name, props['!span']) for name, props
            in functions(condensed))


def symbol_needles_sparse(condensed):
    return (('js-symbol', name, props['!span']) for name, props
            in symbols(condensed))


def property_needles_sparse(condensed):
    return (('js-property', name, span) for _, name, span
            in properties(condensed))


@unsparsify
def get_needles(condensed):
    """From a condensed output, return all needles for the plugin interface."""
    sparse_needles = chain(function_needles_sparse(condensed),
                           symbol_needles_sparse(condensed),
                           property_needles_sparse(condensed))

    return sparse_needles
