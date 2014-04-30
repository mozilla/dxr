from jinja2 import Markup


class SearchFilter(object):
    """Base class for all search filters, plugins subclasses this class and
            registers an instance of them calling register_filter
    """
    # True iff this filter asserts line-based restrictions, shows lines, and
    # highlights text. False for filters that act only on file-level criteria
    # and select no extra SQL fields. This is used to suppress showing all
    # lines of all found files if you do a simple file- based query like
    # ext:html.
    has_lines = True

    def __init__(self, description=''):
        self.description = description

    def filter(self, terms, aliases):
        """Yield tuples of (fields, tables, a condition, list of arguments).

        The SQL fields will be added to the SELECT clause and must either be
        empty or come in a pair taken to be (extent start, extent end). The
        condition will be ANDed into the WHERE clause.

        :arg terms: A dictionary with keys for each filter name I handle (as
            well as others, possibly, which should be ignored). Example::

                {'function': [{'arg': 'o hai',
                               'not': False,
                               'case_sensitive': False,
                               'qualified': False},
                               {'arg': 'what::next',
                                'not': True,
                                'case_sensitive': False,
                                'qualified': True}],
                  ...}
        :arg aliases: An iterable of unique SQL names for use as table aliases,
            to keep them unique. Advancing the iterator reserves the alias it
            returns.

        """
        return []

    def names(self):
        """Return a list of filter names this filter handles.

        This smooths out the difference between the trilite filter (which
        handles 2 different params) and the other filters (which handle only 1).

        """
        return [self.param] if hasattr(self, 'param') else self.params

    def menu_item(self):
        """Return the item I contribute to the Filters menu.

        Return a dict with ``name`` and ``description`` keys.

        """
        return dict(name=self.param, description=self.description)


class TriliteSearchFilter(SearchFilter):
    params = ['text', 'regexp']

    def filter(self, terms, aliases):
        not_conds = []
        not_args  = []
        for term in terms.get('text', []):
            if term['arg']:
                if term['not']:
                    not_conds.append("trg_index.contents MATCH ?")
                    not_args.append(('substr:' if term['case_sensitive']
                                               else 'isubstr:') +
                                    term['arg'])
                else:
                    yield ([],
                           [],
                           "trg_index.contents MATCH ?",
                           [('substr-extents:' if term['case_sensitive']
                                               else 'isubstr-extents:') +
                            term['arg']])
        for term in terms.get('re', []) + terms.get('regexp', []):
            if term['arg']:
                if term['not']:
                    not_conds.append("trg_index.contents MATCH ?")
                    not_args.append("regexp:" + term['arg'])
                else:
                    yield ([],
                           [],
                           "trg_index.contents MATCH ?",
                           ["regexp-extents:" + term['arg']])

        if not_conds:
            yield ([],
                   [],
                   'NOT EXISTS (SELECT 1 FROM trg_index WHERE '
                               'trg_index.id=lines.id AND (%s))' %
                               ' OR '.join(not_conds),
                   not_args)

    def menu_item(self):
        return {'name': 'regexp',
                'description': Markup(r'Regular expression. Examples: <code>regexp:(?i)\bs?printf</code> <code>regexp:"(three|3) mice"</code>')}


class SimpleFilter(SearchFilter):
    has_lines = False  # just happens to be so for all uses at the moment

    def __init__(self, param, filter_sql, neg_filter_sql, formatter, **kwargs):
        """Construct.

        :arg param: Search parameter from query
        :arg filter_sql: Sql condition for limited using argument to param
        :arg neg_filter_sql: Sql condition for limited using argument to param negated.
        :arg formatter: Function/lambda expression for formatting the argument

        """
        super(SimpleFilter, self).__init__(**kwargs)
        self.param = param
        self.filter_sql = filter_sql
        self.neg_filter_sql = neg_filter_sql
        self.formatter = formatter

    def filter(self, terms, aliases):
        for term in terms.get(self.param, []):
            arg = term['arg']
            if term['not']:
                yield [], [], self.neg_filter_sql, self.formatter(arg)
            else:
                yield [], [], self.filter_sql, self.formatter(arg)


class ExistsLikeFilter(SearchFilter):
    """Search filter for asking of something LIKE this EXISTS,
            This filter takes 5 parameters, param is the search query parameter,
            "-" + param is a assumed to be the negated search filter.
            The filter_sql must be an (SELECT 1 FROM ... WHERE ... %s ...), sql condition on files.id,
            s.t. replacing %s with "qual_name = ?" or "like_name LIKE %?%" where ? is arg given to param
            in search query, and prefixing with EXISTS or NOT EXISTS will yield search
            results as desired :)
            (BTW, did I mention that 'as desired' is awesome way of writing correct specifications)
            ext_sql, must be an sql statement for a list of extent start and end,
            given arguments (file_id, %arg%), where arg is the argument given to
            param. Again %s will be replaced with " = ?" or "LIKE %?%" depending on
            whether or not param is prefixed +
    """
    def __init__(self, param, tables, wheres=None, qual_name, like_name, **kwargs):
        """Construct.

        :arg tables: A list of tables (with optional aliases) to include in the
            SELECT clause. The one aliased to {a} gets implicitly joined to the
            files table via its file_id and file_line fields and has extents
            extracted from its file_col, extent_start, and extent_end columns.
        :arg wheres: Additional WHERE clauses. Will be ANDed together with the
            implicitly provided file-table joins and LIKE constraints.

        """
        super(ExistsLikeFilter, self).__init__(**kwargs)
        self.param = param
        self.tables = tables
        self.wheres = wheres or []
        self.qual_expr = " %s = ? " % qual_name
        self.like_expr = """ %s LIKE ? ESCAPE "\\" """ % like_name

    def filter(self, terms, aliases):
        for term in terms.get(self.param, []):
            namer = LocalNamer(aliases)
            is_qualified = term['qualified']
            arg = term['arg']
            sql_params = [arg if is_qualified else like_escape(arg)]
            constraints = [
                    '{a}.file_id=files.id AND {a}.file_line=lines.number',
                    self.qual_expr if is_qualified else self.like_expr
                ] + self.wheres
            join_and_find = ' AND '.join(constraints).format(namer)
            formatted_tables = [table.format(namer) for table in self.tables]
            if term['not']:
                yield ([],
                       [],
                       'NOT EXISTS (SELECT 1 FROM {tables} WHERE '
                           '{condition})'.format(table=formatted_tables,
                                                 condition=join_and_find),
                       sql_params)
            else:
                yield (
                    ['{a}.file_col'.format(namer),
                     '{a}.file_col + {a}.extent_end - {a}.extent_start'.format(namer)],
                    formatted_tables,
                    join_and_find,
                    sql_params)


class UnionFilter(SearchFilter):
    """Provides a filter matching the union of the given filters.

            For when you want OR instead of AND.
    """
    def __init__(self, filters, **kwargs):
        super(UnionFilter, self).__init__(**kwargs)
        # For the moment, UnionFilter supports only single-param filters. There
        # is no reason this can't change.
        unique_params = set(f.param for f in filters)
        if len(unique_params) > 1:
            raise ValueError('All filters that make up a union filter must have the same name, but we got %s.' % ' and '.join(unique_params))
        self.param = unique_params.pop()  # for consistency with other filters
        self.filters = filters

    def filter(self, terms):
        for res in zip(*(filt.filter(terms) for filt in self.filters)):
            yield ('(' + ' OR '.join(conds for (conds, args, exts) in res) + ')',
                   [arg for (conds, args, exts) in res for arg in args],
                   any(exts for (conds, args, exts) in res))

    def extents(self, terms, execute_sql, file_id):
        def builder():
            for filt in self.filters:
                for hits in filt.extents(terms, execute_sql, file_id):
                    for hit in hits:
                        yield hit
        def sorter():
            for hits in groupby(sorted(builder())):
                yield hits[0]
        yield sorter()
class LocalNamer(object):
    """Hygiene provider for SQL aliases"""

    def __init__(self, aliases):
        """Construct.

        :arg aliases: Iterable of unique SQL aliases

        """
        self.aliases = aliases
        self.map = {}  # local name -> global name

    def __getitem__(self, key):
        """Map a one-char local alias placeholder into a global SQL alias.

        Longer placeholders map to "{placeholder}" so they can be passed to a
        second format() call.

        """
        if len(key) == 1:
            try:
                ret = self.map[key]
            except KeyError:
                ret = self.map[key] = next(self.aliases)
        else:
            ret = '{%s}' % key
        return ret


def like_escape(val):
    """Escape for usage in as argument to the LIKE operator """
    return (val.replace("\\", "\\\\")
               .replace("_", "\\_")
               .replace("%", "\\%")
               .replace("?", "_")
               .replace("*", "%"))


# Register filters by adding them to this list:
filters = [
    # path filter
    SimpleFilter(
        param             = "path",
        description       = Markup('File or directory sub-path to search within. <code>*</code> and <code>?</code> act as shell wildcards.'),
        filter_sql        = """files.path LIKE ? ESCAPE "\\" """,
        neg_filter_sql    = """files.path NOT LIKE ? ESCAPE "\\" """,
        formatter         = lambda arg: ['%' + like_escape(arg) + '%']
    ),

    # ext filter
    SimpleFilter(
        param             = "ext",
        description       = Markup('Filename extension: <code>ext:cpp</code>'),
        filter_sql        = """files.path LIKE ? ESCAPE "\\" """,
        neg_filter_sql    = """files.path NOT LIKE ? ESCAPE "\\" """,
        formatter         = lambda arg: ['%' +
            like_escape(arg if arg.startswith(".") else "." + arg)]
    ),

    TriliteSearchFilter(),

    # function filter
    ExistsLikeFilter(
    # select ... t1.file_col, t1.file_col+t1.extent_end-t1.extent_start
    # from functions t1
    # where ...
    #   t1.file_id=files.id AND lines.number=t1.file_line AND
    #   t1.name LIKE ? ESCAPE "\\"

    # NOT:
    # select ...
    # ...
    # where NOT EXISTS (SELECT 1 FROM functions t1 WHERE
    #   t1.file.id=files.id AND t1.file_line=lines.number AND
    #   f.name LIKE ? ESCAPE "\\")
        description   = Markup('Function or method definition: <code>function:foo</code>'),
        param         = "function",
        tables        = ['functions AS {a}'],
        like_name     = "{a}.name",
        qual_name     = "{a}.qualname"
    ),

    # function-ref filter
    ExistsLikeFilter(
    # select ... r.file_col, r.file_col+r.extent_end-r.extent_start
    # from functions f, function_refs r
    # where ...
    #    r.file_id=files.id AND r.file_line=lines.number AND
    #    functions.id=refs.refid AND
    #    f.name LIKE ? ESCAPE "\\"

    # NOT:
    # select ...
    # ...
    # where NOT EXISTS (SELECT 1 FROM functions f, function_refs r WHERE
    #    r.file_id=files.id and r.file_line=lines.number AND
    #    functions.id=refs.refid AND
    #    f.name LIKE ? ESCAPE "\\")
        description   = 'Function or method references',
        param         = "function-ref",
        tables        = ['functions AS {f}', 'function_refs AS {a}'],
        wheres        = '{f}.id={a}.refid',
        like_name     = "{f}.name",
        qual_name     = "{f}.qualname"
    ),

    # function-decl filter
    ExistsLikeFilter(
        description   = 'Function or method declaration',
        param         = "function-decl",
        filter_sql    = """SELECT 1 FROM functions, function_decldef as decldef
                           WHERE %s
                             AND functions.id = decldef.defid AND decldef.file_id = files.id
                        """,
        ext_sql       = """SELECT decldef.extent_start, decldef.extent_end FROM function_decldef AS decldef
                           WHERE decldef.file_id = ?
                             AND EXISTS (SELECT 1 FROM functions
                                         WHERE %s
                                           AND functions.id = decldef.defid)
                           ORDER BY decldef.extent_start
                        """,
        like_name     = "functions.name",
        qual_name     = "functions.qualname"
    ),

    UnionFilter([
      # callers filter (direct-calls)
      ExistsLikeFilter(
          param         = "callers",
          filter_sql    = """SELECT 1
                              FROM functions as caller, functions as target, callers
                             WHERE %s
                               AND callers.targetid = target.id
                               AND callers.callerid = caller.id
                               AND caller.file_id = files.id
                          """,
          ext_sql       = """SELECT functions.extent_start, functions.extent_end
                              FROM functions
                             WHERE functions.file_id = ?
                               AND EXISTS (SELECT 1 FROM functions as target, callers
                                            WHERE %s
                                              AND callers.targetid = target.id
                                              AND callers.callerid = functions.id
                                          )
                             ORDER BY functions.extent_start
                          """,
          like_name     = "target.name",
          qual_name     = "target.qualname"
      ),

      # callers filter (indirect-calls)
      ExistsLikeFilter(
          param         = "callers",
          filter_sql    = """SELECT 1
                              FROM functions as caller, functions as target, callers, targets
                             WHERE %s
                               AND targets.funcid = target.id
                               AND targets.targetid = callers.targetid
                               AND callers.callerid = caller.id
                               AND caller.file_id = files.id
                          """,
          ext_sql       = """SELECT functions.extent_start, functions.extent_end
                              FROM functions
                             WHERE functions.file_id = ?
                               AND EXISTS (SELECT 1 FROM functions as target, callers, targets
                                            WHERE %s
                                              AND targets.funcid = target.id
                                              AND targets.targetid = callers.targetid
                                              AND callers.callerid = functions.id
                                          )
                             ORDER BY functions.extent_start
                          """,
          like_name     = "target.name",
          qual_name     = "target.qualname")],

      description = Markup('Functions which call the given function or method: <code>callers:GetStringFromName</code>')
    ),

    UnionFilter([
      # called-by filter (direct calls)
      ExistsLikeFilter(
          param         = "called-by",
          filter_sql    = """SELECT 1
                               FROM functions as target, functions as caller, callers
                              WHERE %s
                                AND callers.callerid = caller.id
                                AND callers.targetid = target.id
                                AND target.file_id = files.id
                          """,
          ext_sql       = """SELECT functions.extent_start, functions.extent_end
                              FROM functions
                             WHERE functions.file_id = ?
                               AND EXISTS (SELECT 1 FROM functions as caller, callers
                                            WHERE %s
                                              AND caller.id = callers.callerid
                                              AND callers.targetid = functions.id
                                          )
                             ORDER BY functions.extent_start
                          """,
          like_name     = "caller.name",
          qual_name     = "caller.qualname"
      ),

      # called-by filter (indirect calls)
      ExistsLikeFilter(
          param         = "called-by",
          filter_sql    = """SELECT 1
                               FROM functions as target, functions as caller, callers, targets
                              WHERE %s
                                AND callers.callerid = caller.id
                                AND targets.funcid = target.id
                                AND targets.targetid = callers.targetid
                                AND target.file_id = files.id
                          """,
          ext_sql       = """SELECT functions.extent_start, functions.extent_end
                              FROM functions
                             WHERE functions.file_id = ?
                               AND EXISTS (SELECT 1 FROM functions as caller, callers, targets
                                            WHERE %s
                                              AND caller.id = callers.callerid
                                              AND targets.funcid = functions.id
                                              AND targets.targetid = callers.targetid
                                          )
                             ORDER BY functions.extent_start
                          """,
          like_name     = "caller.name",
          qual_name     = "caller.qualname"
      )],

      description = 'Functions or methods which are called by the given one'
    ),

# I don't see how I can do a UnionFilter with this query shape. Ah yes, we can:
#
# SELECT types.extent_start AS start1, whatever AS end1
#        typedefs.extent_start AS start2, whatever AS end2
# ...
# LEFT JOIN types ON types.file_id=files.id AND types.file_line=lines.number
# LEFT JOIN types ON typedefs.file_id=files.id AND typedefs.file_line=lines.number
# ...
# WHERE start1 IS NOT NULL OR start2 IS NOT NULL
#
## And then have the extent processing crap filter out any Nones.
#

#√ SELECT {extent_start1} AS start1, {extent_end1} AS end1  # UnionFilter will stick the ASes on so we know what names to use in the WHERE.
#√        {extent_start2} AS start2, {extent_end2} AS end2
# ...
#√ LEFT JOIN {table1} ON {condition1}
#√ LEFT JOIN {table2} ON {condition2}
# ...
#√ WHERE start1 IS NOT NULL OR start2 IS NOT NULL

# Then how do we do a negative UnionFilter? WHERE ... IS NULL AND ... IS NULL, I suppose?
# I think we'd want to pass positive things to the ExistsFilters in any case and then take care of the negativizing ourselves.

#
# Maybe I can take something like "blah {a} whatever {b}

    # type filter
    UnionFilter([
      ExistsLikeFilter(
        param         = "type",
        filter_sql    = """SELECT 1 FROM types
                           WHERE %s
                             AND types.file_id = files.id
                        """,
        ext_sql       = """SELECT types.extent_start, types.extent_end FROM types
                           WHERE types.file_id = ?
                             AND %s
                           ORDER BY types.extent_start
                        """,
        like_name     = "types.name",
        qual_name     = "types.qualname"
      ),
      ExistsLikeFilter(
        param         = "type",
        filter_sql    = """SELECT 1 FROM typedefs
                           WHERE %s
                             AND typedefs.file_id = files.id
                        """,
        ext_sql       = """SELECT typedefs.extent_start, typedefs.extent_end FROM typedefs
                           WHERE typedefs.file_id = ?
                             AND %s
                           ORDER BY typedefs.extent_start
                        """,
        like_name     = "typedefs.name",
        qual_name     = "typedefs.qualname")],
      description=Markup('Type or class definition: <code>type:Stack</code>')
    ),

    # type-ref filter
    UnionFilter([
      ExistsLikeFilter(
        param         = "type-ref",
        filter_sql    = """SELECT 1 FROM types, type_refs AS refs
                           WHERE %s
                             AND types.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM type_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM types
                                         WHERE %s
                                           AND types.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "types.name",
        qual_name     = "types.qualname"
      ),
      ExistsLikeFilter(
        param         = "type-ref",
        filter_sql    = """SELECT 1 FROM typedefs, typedef_refs AS refs
                           WHERE %s
                             AND typedefs.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM typedef_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM typedefs
                                         WHERE %s
                                           AND typedefs.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "typedefs.name",
        qual_name     = "typedefs.qualname")],
      description='Type or class references, uses, or instantiations'
    ),

    # type-decl filter
    ExistsLikeFilter(
      description   = 'Type or class declaration',
      param         = "type-decl",
      filter_sql    = """SELECT 1 FROM types, type_decldef AS decldef
                         WHERE %s
                           AND types.id = decldef.defid AND decldef.file_id = files.id
                      """,
      ext_sql       = """SELECT decldef.extent_start, decldef.extent_end FROM type_decldef AS decldef
                         WHERE decldef.file_id = ?
                           AND EXISTS (SELECT 1 FROM types
                                       WHERE %s
                                         AND types.id = decldef.defid)
                         ORDER BY decldef.extent_start
                      """,
      like_name     = "types.name",
      qual_name     = "types.qualname"
    ),

    # var filter
    ExistsLikeFilter(
        description   = 'Variable definition',
        param         = "var",
        filter_sql    = """SELECT 1 FROM variables
                           WHERE %s
                             AND variables.file_id = files.id
                        """,
        ext_sql       = """SELECT variables.extent_start, variables.extent_end FROM variables
                           WHERE variables.file_id = ?
                             AND %s
                           ORDER BY variables.extent_start
                        """,
        like_name     = "variables.name",
        qual_name     = "variables.qualname"
    ),

    # var-ref filter
    ExistsLikeFilter(
        description   = 'Variable uses (lvalue, rvalue, dereference, etc.)',
        param         = "var-ref",
        filter_sql    = """SELECT 1 FROM variables, variable_refs AS refs
                           WHERE %s
                             AND variables.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM variable_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM variables
                                         WHERE %s
                                           AND variables.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "variables.name",
        qual_name     = "variables.qualname"
    ),

    # var-decl filter
    ExistsLikeFilter(
        description   = 'Variable declaration',
        param         = "var-decl",
        filter_sql    = """SELECT 1 FROM variables, variable_decldef AS decldef
                           WHERE %s
                             AND variables.id = decldef.defid AND decldef.file_id = files.id
                        """,
        ext_sql       = """SELECT decldef.extent_start, decldef.extent_end FROM variable_decldef AS decldef
                           WHERE decldef.file_id = ?
                             AND EXISTS (SELECT 1 FROM variables
                                         WHERE %s
                                           AND variables.id = decldef.defid)
                           ORDER BY decldef.extent_start
                        """,
        like_name     = "variables.name",
        qual_name     = "variables.qualname"
    ),

    # macro filter
    ExistsLikeFilter(
        description   = 'Macro definition',
        param         = "macro",
        filter_sql    = """SELECT 1 FROM macros
                           WHERE %s
                             AND macros.file_id = files.id
                        """,
        ext_sql       = """SELECT macros.extent_start, macros.extent_end FROM macros
                           WHERE macros.file_id = ?
                             AND %s
                           ORDER BY macros.extent_start
                        """,
        like_name     = "macros.name",
        qual_name     = "macros.name"
    ),

    # macro-ref filter
    ExistsLikeFilter(
        description   = 'Macro uses',
        param         = "macro-ref",
        filter_sql    = """SELECT 1 FROM macros, macro_refs AS refs
                           WHERE %s
                             AND macros.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM macro_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM macros
                                         WHERE %s
                                           AND macros.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "macros.name",
        qual_name     = "macros.name"
    ),

    # namespace filter
    ExistsLikeFilter(
        description   = 'Namespace definition',
        param         = "namespace",
        filter_sql    = """SELECT 1 FROM namespaces
                           WHERE %s
                             AND namespaces.file_id = files.id
                        """,
        ext_sql       = """SELECT namespaces.extent_start, namespaces.extent_end FROM namespaces
                           WHERE namespaces.file_id = ?
                             AND %s
                           ORDER BY namespaces.extent_start
                        """,
        like_name     = "namespaces.name",
        qual_name     = "namespaces.qualname"
    ),

    # namespace-ref filter
    ExistsLikeFilter(
        description   = 'Namespace references',
        param         = "namespace-ref",
        filter_sql    = """SELECT 1 FROM namespaces, namespace_refs AS refs
                           WHERE %s
                             AND namespaces.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM namespace_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM namespaces
                                         WHERE %s
                                           AND namespaces.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "namespaces.name",
        qual_name     = "namespaces.qualname"
    ),

    # namespace-alias filter
    ExistsLikeFilter(
        description   = 'Namespace alias',
        param         = "namespace-alias",
        filter_sql    = """SELECT 1 FROM namespace_aliases
                           WHERE %s
                             AND namespace_aliases.file_id = files.id
                        """,
        ext_sql       = """SELECT namespace_aliases.extent_start, namespace_aliases.extent_end FROM namespace_aliases
                           WHERE namespace_aliases.file_id = ?
                             AND %s
                           ORDER BY namespace_aliases.extent_start
                        """,
        like_name     = "namespace_aliases.name",
        qual_name     = "namespace_aliases.qualname"
    ),

    # namespace-alias-ref filter
    ExistsLikeFilter(
        description   = 'Namespace alias references',
        param         = "namespace-alias-ref",
        filter_sql    = """SELECT 1 FROM namespace_aliases, namespace_alias_refs AS refs
                           WHERE %s
                             AND namespace_aliases.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM namespace_alias_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM namespace_aliases
                                         WHERE %s
                                           AND namespace_aliases.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "namespace_aliases.name",
        qual_name     = "namespace_aliases.qualname"
    ),

    # bases filter -- reorder these things so more frequent at top.
    ExistsLikeFilter(
        description   = Markup('Superclasses of a class: <code>bases:SomeSubclass</code>'),
        param         = "bases",
        filter_sql    = """SELECT 1 FROM types as base, impl, types
                            WHERE %s
                              AND impl.tbase = base.id
                              AND impl.tderived = types.id
                              AND base.file_id = files.id""",
        ext_sql       = """SELECT base.extent_start, base.extent_end
                            FROM types as base
                           WHERE base.file_id = ?
                             AND EXISTS (SELECT 1 FROM impl, types
                                         WHERE impl.tbase = base.id
                                           AND impl.tderived = types.id
                                           AND %s
                                        )
                        """,
        like_name     = "types.name",
        qual_name     = "types.qualname"
    ),

    # derived filter
    ExistsLikeFilter(
        description   = Markup('Subclasses of a class: <code>derived:SomeSuperclass</code>'),
        param         = "derived",
        filter_sql    = """SELECT 1 FROM types as sub, impl, types
                            WHERE %s
                              AND impl.tbase = types.id
                              AND impl.tderived = sub.id
                              AND sub.file_id = files.id""",
        ext_sql       = """SELECT sub.extent_start, sub.extent_end
                            FROM types as sub
                           WHERE sub.file_id = ?
                             AND EXISTS (SELECT 1 FROM impl, types
                                         WHERE impl.tbase = types.id
                                           AND impl.tderived = sub.id
                                           AND %s
                                        )
                        """,
        like_name     = "types.name",
        qual_name     = "types.qualname"
    ),

    UnionFilter([
      # member filter for functions
      ExistsLikeFilter(
        param         = "member",
        filter_sql    = """SELECT 1 FROM types as type, functions as mem
                            WHERE %s
                              AND mem.scopeid = type.id AND mem.file_id = files.id
                        """,
        ext_sql       = """ SELECT extent_start, extent_end
                              FROM functions as mem WHERE mem.file_id = ?
                                      AND EXISTS ( SELECT 1 FROM types as type
                                                    WHERE %s
                                                      AND type.id = mem.scopeid)
                           ORDER BY mem.extent_start
                        """,
        like_name     = "type.name",
        qual_name     = "type.qualname"
      ),
      # member filter for types
      ExistsLikeFilter(
        param         = "member",
        filter_sql    = """SELECT 1 FROM types as type, types as mem
                            WHERE %s
                              AND mem.scopeid = type.id AND mem.file_id = files.id
                        """,
        ext_sql       = """ SELECT extent_start, extent_end
                              FROM types as mem WHERE mem.file_id = ?
                                      AND EXISTS ( SELECT 1 FROM types as type
                                                    WHERE %s
                                                      AND type.id = mem.scopeid)
                           ORDER BY mem.extent_start
                        """,
        like_name     = "type.name",
        qual_name     = "type.qualname"
      ),
      # member filter for variables
      ExistsLikeFilter(
        param         = "member",
        filter_sql    = """SELECT 1 FROM types as type, variables as mem
                            WHERE %s
                              AND mem.scopeid = type.id AND mem.file_id = files.id
                        """,
        ext_sql       = """ SELECT extent_start, extent_end
                              FROM variables as mem WHERE mem.file_id = ?
                                      AND EXISTS ( SELECT 1 FROM types as type
                                                    WHERE %s
                                                      AND type.id = mem.scopeid)
                           ORDER BY mem.extent_start
                        """,
        like_name     = "type.name",
        qual_name     = "type.qualname")],

      description = Markup('Member variables, types, or methods of a class: <code>member:SomeClass</code>')
    ),

    # overridden filter
    ExistsLikeFilter(
        description   = Markup('Methods which are overridden by the given one. Useful mostly with fully qualified methods, like <code>+overridden:Derived::foo()</code>.'),
        param         = "overridden",
        filter_sql    = """SELECT 1
                             FROM functions as base, functions as derived, targets
                            WHERE %s
                              AND base.id = -targets.targetid
                              AND derived.id = targets.funcid
                              AND base.id <> derived.id
                              AND base.file_id = files.id
                        """,
        ext_sql       = """SELECT functions.extent_start, functions.extent_end
                            FROM functions
                           WHERE functions.file_id = ?
                             AND EXISTS (SELECT 1 FROM functions as derived, targets
                                          WHERE %s
                                            AND functions.id = -targets.targetid
                                            AND derived.id = targets.funcid
                                            AND functions.id <> derived.id
                                        )
                           ORDER BY functions.extent_start
                        """,
        like_name     = "derived.name",
        qual_name     = "derived.qualname"
    ),

    # overrides filter
    ExistsLikeFilter(
        description   = Markup('Methods which override the given one: <code>overrides:someMethod</code>'),
        param         = "overrides",
        filter_sql    = """SELECT 1
                             FROM functions as base, functions as derived, targets
                            WHERE %s
                              AND base.id = -targets.targetid
                              AND derived.id = targets.funcid
                              AND base.id <> derived.id
                              AND derived.file_id = files.id
                        """,
        ext_sql       = """SELECT functions.extent_start, functions.extent_end
                            FROM functions
                           WHERE functions.file_id = ?
                             AND EXISTS (SELECT 1 FROM functions as base, targets
                                          WHERE %s
                                            AND base.id = -targets.targetid
                                            AND functions.id = targets.funcid
                                            AND base.id <> functions.id
                                        )
                           ORDER BY functions.extent_start
                        """,
        like_name     = "base.name",
        qual_name     = "base.qualname"
    ),

    #warning filter
    ExistsLikeFilter(
        description   = 'Compiler warning messages',
        param         = "warning",
        filter_sql    = """SELECT 1 FROM warnings
                            WHERE %s
                              AND warnings.file_id = files.id """,
        ext_sql       = """SELECT warnings.extent_start, warnings.extent_end
                             FROM warnings
                            WHERE warnings.file_id = ?
                              AND %s
                        """,
        like_name     = "warnings.msg",
        qual_name     = "warnings.msg"
    ),

    #warning-opt filter
    ExistsLikeFilter(
        description   = 'More (less severe?) warning messages',
        param         = "warning-opt",
        filter_sql    = """SELECT 1 FROM warnings
                            WHERE %s
                              AND warnings.file_id = files.id """,
        ext_sql       = """SELECT warnings.extent_start, warnings.extent_end
                             FROM warnings
                            WHERE warnings.file_id = ?
                              AND %s
                        """,
        like_name     = "warnings.opt",
        qual_name     = "warnings.opt"
    )
]
