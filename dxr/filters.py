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
    """Search filter for asking of something LIKE this exists"""

    def __init__(self, param, tables, qual_name, like_name, wheres=None, **kwargs):
        """Construct.

        :arg param: The filter name the user types before the colon
        :arg tables: A list of tables (with optional aliases) to include in the
            SELECT clause. The one aliased to {a} gets implicitly joined to the
            files table via its file_id and file_line fields and has extents
            extracted from its file_col, extent_start, and extent_end columns.
        :arg qual_name: The column to compare the filter argument to when doing
            a fully qualified match
        :arg like_name: The column to compare the filter argument to when doing
            a normal match
        :arg wheres: Additional WHERE clauses. Will be ANDed together with the
            implicitly provided file-table joins and LIKE constraints.

        """
        super(ExistsLikeFilter, self).__init__(**kwargs)
        self.param = param
        self.tables = tables
        self.wheres = wheres or []
        self.qual_expr = '%s=?' % qual_name
        self.like_expr = '%s LIKE ? ESCAPE "\\"' % like_name

    def filter(self, terms, aliases, force_positive=False):
        """Return a tuple for each query term that matches my param name."""
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
            named_tables = [table.format(namer) for table in self.tables]
            if term['not'] and not force_positive:
                yield ([],
                       [],
                       'NOT EXISTS (SELECT 1 FROM {tables} WHERE '
                           '{condition})'.format(
                                tables=', '.join(named_tables),
                                condition=join_and_find),
                       sql_params)
            else:
                yield (
                    ['{a}.file_col'.format(namer),
                     '{a}.file_col + {a}.extent_end - {a}.extent_start'.format(namer)],
                    named_tables,
                    join_and_find,
                    sql_params)


class UnionFilter(SearchFilter):
    """A (possibly negated) ORing of ExistsLikeFilters.

    Other filters probably work, too, but I haven't coded with them in mind.

    """
    def __init__(self, filters, **kwargs):
        """Construct.

        :arg filters: A list of filters to union together. Each one's filter()
            method must yield tuples which give extents, tables, and conditions.
            In other words, none of those can be empty.

        """
        super(UnionFilter, self).__init__(**kwargs)
        # For the moment, UnionFilter supports only single-param filters. There
        # is no reason this can't change.
        unique_params = set(f.param for f in filters)
        if len(unique_params) > 1:
            raise ValueError('All filters that make up a union filter must have the same name, but we got %s.' % ' and '.join(unique_params))
        self.param = unique_params.pop()  # for consistency with other filters
        self.filters = filters

    def filter(self, terms, aliases):
        all_fields, all_tables, all_args = [], [], []
        for filter in self.filters:  # These get ORed together.
            term_tuples = filter.filter(terms, aliases, force_positive=True)
            term_wheres = []

            for fields, tables, join_condition, args in term_tuples:  # For each term. These get ANDed together.
                if not fields or not tables or not condition:
                    raise ValueError('UnionFilter needs non-empty extents, tables, and a condition.')
                namer = LocalNamer(aliases)
                # Okay. Union all the terms together as if they were positive. (Add a force_positive=True arg to ExistsFilter.filter().) Then, in the WHERE clause, make the positive terms look like (condition from subfilter A OR condition from subfilter B OR ...) and negative ones look like (field from subfilter A IS NULL AND field from subfilter B IS NULL AND ...). The negative ones don't even need the parens, obviously; they can be yielded as separate conditions.
                # TODO: Support negation.
                start, end = fields
                named_start = '{start_field} AS {s}'.format(namer).format(start_field=start)
                all_fields.extend([named_start, end])

                term_wheres.append('{s} IS NOT NULL'.format(namer))
                all_tables.extend(tables)
                all_args.extend(args)
                all_joins.append(
                    'LEFT JOIN {tables} ON {join_condition}'.format(
                        tables=tables,
                        join_condition=join_condition))
            all_wheres.append(' AND '.join(term_wheres))
        return {
            'fields': all_fields,
            'tables': all_tables,
            'joins': all_joins,
            'wheres': '((' + ') OR ('.join(all_wheres) + '))',
        }


class LocalNamer(object):
    """Hygiene provider for SQL aliases

    Maps all single-char placeholders to consistent made-up names. Leaves all
    longer ones along.

    """
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
        tables        = ['function_refs AS {a}', 'functions AS {f}'],
        wheres        = ['{f}.id={a}.refid'],
        like_name     = "{f}.name",
        qual_name     = "{f}.qualname"
    ),

    # function-decl filter
    ExistsLikeFilter(
        description   = 'Function or method declaration',
        param         = "function-decl",
        tables        = ['function_decldef AS {a}', 'functions AS {f}'],
        wheres        = ['{f}.id={a}.defid'],
        like_name     = "{f}.name",
        qual_name     = "{f}.qualname"
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

#v SELECT {extent_start1} AS start1, {extent_end1} AS end1  # UnionFilter will stick the ASes on so we know what names to use in the WHERE.
#v        {extent_start2} AS start2, {extent_end2} AS end2
# ...
#v LEFT JOIN {table1} ON {condition1}
#v LEFT JOIN {table2} ON {condition2}
# ...
#v WHERE start1 IS NOT NULL OR start2 IS NOT NULL

# Then how do we do a negative UnionFilter? WHERE ... IS NULL AND ... IS NULL, I suppose?
# I think we'd want to pass positive things to the ExistsFilters in any case and then take care of the negativizing ourselves.

# type:foo type:bar -->  # Find type:foo and type:bar on the same line, either classes or typedefs.
# SELECT {extent_start1} AS start1, {extent_end1} AS end1  # filter 1, term 1
#        {extent_start2} AS start2, {extent_end2} AS end2  # filter 1, term 2
#        {extent_start3} AS start3, {extent_end3} AS end3  # filter 2, term 1
#        {extent_start4} AS start4, {extent_end4} AS end4  # All 4 of the "subqueries" have to be in here, or we can't get extents for them all in the case that they all do turn up something.
# So we want the first 2 ANDed together, the second 2 ANDed together, and then the 2 pairs ORed.
# LEFT JOIN the class1 thing ON whatever
# LEFT JOIN the typedef1 thing ON whatever
# LEFT JOIN the class2 thing ON whatever
# LEFT JOIN the typedef2 thing on whatever
#
# WHERE ((start1 IS NOT NULL AND start2 IS NOT NULL) OR (start3 IS NOT NULL AND start4 IS NOT NULL)).

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
        tables        = ['macro_refs AS {a}', 'macros AS {m}'],
        wheres        = ['{m}.id={a}.refid'],
        like_name     = "{m}.name",
        qual_name     = "{m}.name"
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
