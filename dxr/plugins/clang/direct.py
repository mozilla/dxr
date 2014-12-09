from dxr.plugins import direct_search


def insensitive_clause(field, text):
    """Return an ES clause that matches ``text`` case-insensitively against
    the ``field`` property of a line."""
    return {'query': {'match': {field: text}}}


def insensitive(field):
    def matcher(term):
        """Return an elasticsearch clause demanding a case-insensitive match of
        the term's ``arg`` against the given field."""
        return insensitive_clause(field, term['arg'])
    return matcher


def qualified_insensitive(field):
    def matcher(term):
        """If the term could be a fully qualified name, see if there is a line
        whose ``field`` matches, case-insensitively."""
        text = term['arg']
        if '::' in text:
            return insensitive_clause(field, text)
    return matcher


def exact(field):
    def matcher(term):
        """Return an elasticsearch clause demanding a case-sensitive match of
        the term's ``arg`` against the given field."""
        return {'term': {field: term['arg']}}
    return matcher


searchers = [
    # If the query was an exact match for a type or class name, jump there:
    direct_search(200)(exact('c_type.name')),

    # If the query was an exact match for a function name, jump there:
    direct_search(300)(exact('c_function.name')),

    # And so on:
    direct_search(400)(exact('c_macro.name')),

    # Try fully qualified names of types/classes and functions, case-insensitive:
    direct_search(500)(qualified_insensitive('c_type.qualname.lower')),
    direct_search(600)(qualified_insensitive('c_function.qualname.lower')),

    direct_search(700)(insensitive('c_type.name.lower')),
    direct_search(800)(insensitive('c_function.name.lower')),
    direct_search(900)(insensitive('c_macro.name.lower'))]
