from dxr.plugins import direct_search


def insensitive(field):
    def matcher(term):
        """Return an elasticsearch clause demanding a case-insensitive match of
        the term's ``arg`` against the given field."""
        return {'query': {'match': {field: term['arg']}}}
    return matcher


def exact(field):
    def matcher(term):
        """Return an elasticsearch clause demanding a case-sensitive match of
        the term's ``arg`` against the given field."""
        return {'term': {field: term['arg']}}
    return matcher


def qualified(matcher):
    """Wrap a matcher with a thing that gives up unless the query text looks
    like it might be a fully qualified name."""
    def up_giver(term):
        if '::' in term['arg']:
            return matcher(term)
    return up_giver


searchers = [
    # If the query was an exact match for a type or class name, jump there:
    direct_search(200)(exact('c_type.name')),

    # If the query was an exact match for a function name, jump there:
    direct_search(300)(exact('c_function.name')),

    # And so on:
    direct_search(400)(exact('c_macro.name')),

    # Try fully qualified names of types/classes and functions, case-sensitive:
    direct_search(500)(qualified(exact('c_type.qualname'))),
    direct_search(600)(qualified(exact('c_function.qualname'))),

    # Try fully qualified names of types/classes and functions, case-insensitive:
    direct_search(700)(qualified(insensitive('c_type.qualname.lower'))),
    direct_search(800)(qualified(insensitive('c_function.qualname.lower'))),

    direct_search(900)(insensitive('c_type.name.lower')),
    direct_search(1000)(insensitive('c_function.name.lower')),
    direct_search(1100)(insensitive('c_macro.name.lower'))]
