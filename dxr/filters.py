from collections import defaultdict
from string import Formatter

from ordereddict import OrderedDict
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

    def filter(self, term, aliases):
        """Yield a tuple of (fields, tables, a condition, a join clause, list
        of arguments) that expresses the filtration for a single query term.

        The SQL fields will be added to the SELECT clause and must either be
        empty or come in a pair taken to be (extent start, extent end). The
        condition will be ANDed into the WHERE clause.

        :arg term: A dictionary representing the term to handle. Example::

                {'type': 'function',
                 'arg': 'o hai',
                 'not': False,
                 'case_sensitive': False,
                 'qualified': False}

        :arg aliases: An iterable of unique SQL names for use as table aliases,
            to keep them unique. Advancing the iterator reserves the alias it
            returns.

        """
        raise NotImplementedError


class TextFilter(SearchFilter):
    """Filter for matching static text using trilite"""

    def filter(self, term, aliases):
        if term['arg']:
            if term['not']:
                return ([],
                        [],
                        'NOT EXISTS (SELECT 1 FROM trg_index WHERE '
                            'trg_index.id=lines.id AND trg_index.contents MATCH ?)',
                        [],
                        [('substr:' if term['case_sensitive'] else 'isubstr:') +
                            term['arg']])
            else:
                return ([],
                        [],
                        "trg_index.contents MATCH ?",
                        [],
                        [('substr-extents:' if term['case_sensitive']
                                            else 'isubstr-extents:') +
                         term['arg']])


class RegexpFilter(SearchFilter):
    def filter(self, terms, aliases):
        if term['arg']:
            if term['not']:
                return ([],
                        [],
                        'NOT EXISTS (SELECT 1 FROM trg_index WHERE '
                            'trg_index.id=lines.id AND trg_index.contents MATCH ?)',
                        [],
                        'regexp:' + term['arg'])
            else:
                return ([],
                        [],
                        "trg_index.contents MATCH ?",
                        [],
                        ["regexp-extents:" + term['arg']])


class SimpleFilter(SearchFilter):
    has_lines = False  # just happens to be so for all uses at the moment

    def __init__(self, filter_sql, neg_filter_sql, formatter, **kwargs):
        """Construct.

        :arg filter_sql: WHERE clause for positive queries
        :arg neg_filter_sql: WHERE clause for negative queries
        :arg formatter: Function/lambda expression for formatting the argument

        """
        super(SimpleFilter, self).__init__(**kwargs)
        self.filter_sql = filter_sql
        self.neg_filter_sql = neg_filter_sql
        self.formatter = formatter

    def filter(self, term, aliases):
        arg = term['arg']
        if term['not']:
            return [], [], self.neg_filter_sql, [], self.formatter(arg)
        else:
            return [], [], self.filter_sql, [], self.formatter(arg)


class ExistsLikeFilter(SearchFilter):
    """Search filter for asking of something LIKE this exists"""

    def __init__(self, tables, qual_name, like_name, wheres=None, **kwargs):
        """Construct.

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
        self.tables = tables
        self.wheres = wheres or []
        self.qual_expr = '%s=?' % qual_name
        self.like_expr = '%s LIKE ? ESCAPE "\\"' % like_name

    def filter(self, term, aliases, force_positive=False):
        # select ... t1.file_col, t1.file_col+t1.extent_end-t1.extent_start
        # from functions t1
        # where ...
        #   t1.file_id=files.id AND lines.number=t1.file_line AND
        #   t1.name LIKE ? ESCAPE "\\"

        # negated:
        # select ...
        # ...
        # where NOT EXISTS (SELECT 1 FROM functions t1 WHERE
        #   t1.file.id=files.id AND t1.file_line=lines.number AND
        #   f.name LIKE ? ESCAPE "\\")
        namer = LocalNamer(aliases)
        is_qualified = term['qualified']
        arg = term['arg']
        sql_params = [arg if is_qualified else like_escape(arg)]
        constraints = [
                '{a}.file_id=files.id AND {a}.file_line=lines.number',
                self.qual_expr if is_qualified else self.like_expr
            ] + self.wheres
        join_and_find = namer.format(' AND '.join(constraints))
        named_tables = [namer.format(table) for table in self.tables]
        if term['not'] and not force_positive:
            return ([],
                    [],
                    'NOT EXISTS (SELECT 1 FROM {tables} WHERE '
                        '{condition})'.format(
                             tables=', '.join(named_tables),
                             condition=join_and_find),
                    [],
                    sql_params)
        else:
            return (
                [namer.format('{a}.file_col'),
                 namer.format('{a}.file_col + {a}.extent_end - {a}.extent_start')],
                named_tables,
                join_and_find,
                [],
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
        self.filters = filters

    def filter(self, term, aliases):
        # Union all the terms together as if they were positive. Then, in the
        # WHERE clause, make the positive terms look like (extents from filter
        # A IS NOT NULL OR extents from filter B IS NOT NULL OR ...) and
        # negative ones look like (extents from filter A IS NULL AND extents
        # from filter B IS NULL AND ...).
        #
        # For example...
        # -type:foo type:bar -type:qux
        # start1: foo is a class on some line
        # start2: foo is a type on some line
        # start3: bar is a class on some line
        # start4: bar is a type on some line
        # start5: qux is a class on some line
        # start6: qux is a type on some line
        # ...
        # WHERE (start1 IS NULL AND start2 IS NULL) AND  -- -foo
        #       (start3 IS NOT NULL OR start4 IS NOT NULL) AND  -- bar
        #       (start5 IS NULL AND start6 IS NULL)  -- -qux
        term_fields, term_tables, term_args, term_joins, term_wheres = [], [], [], [], []
        for filter in self.filters:
            fields, tables, join_condition, _, args = filter.filter(term, aliases, force_positive=True)
            if not fields or not tables or not join_condition:
                raise ValueError('UnionFilter needs non-empty extents, tables, and a condition.')
            namer = LocalNamer(aliases)
            start, end = fields
            named_start = namer.format('{start_field} AS {s}',
                                      start_field=start)

            term_fields.extend([named_start, end])
            term_tables.extend(tables)
            term_joins.append(
                'LEFT JOIN {tables} ON {join_condition}'.format(
                    tables=tables,
                    join_condition=join_condition))
            term_wheres.append(namer.format('{s} IS NULL' if term['not']
                               else '{s} IS NOT NULL'))
            term_args.extend(args)
        return (term_fields,
                term_tables,
                '(' + (' AND ' if term['not'] else ' OR ').join(term_wheres) + ')',
                term_joins,
                term_args)


class LocalNamer(Formatter):
    """Hygiene provider for SQL aliases

    Maps all single-char placeholders to consistent made-up names. Fills in
    others from kwargs.

    """
    def __init__(self, aliases):
        """Construct.

        :arg aliases: Iterable of unique SQL aliases

        """
        super(LocalNamer, self).__init__()
        self.map = defaultdict(lambda: next(aliases))

    def get_value(self, key, args, kwargs):
        """Map a one-char local alias placeholder into a global SQL alias.

        Other placeholders are treated in accordance with format()'s usual
        behavior.

        """
        if len(key) == 1:  # Supports only string keys at the moment
            return self.map[key]
        else:
            return super(LocalNamer, self).get_value(key, args, kwargs)


def like_escape(val):
    """Escape for usage in as argument to the LIKE operator """
    return (val.replace("\\", "\\\\")
               .replace("_", "\\_")
               .replace("%", "\\%")
               .replace("?", "_")
               .replace("*", "%"))


# Register filters by adding them to this list:
filters = OrderedDict([
    ('path',
     SimpleFilter(
         description = Markup('File or directory sub-path to search within. <code>*</code> and <code>?</code> act as shell wildcards.'),
         filter_sql = """files.path LIKE ? ESCAPE "\\" """,
         neg_filter_sql = """files.path NOT LIKE ? ESCAPE "\\" """,
         formatter = lambda arg: ['%' + like_escape(arg) + '%'])),

    ('ext',
     SimpleFilter(
         description = Markup('Filename extension: <code>ext:cpp</code>'),
         filter_sql = """files.path LIKE ? ESCAPE "\\" """,
         neg_filter_sql = """files.path NOT LIKE ? ESCAPE "\\" """,
         formatter = lambda arg: ['%' +
             like_escape(arg if arg.startswith(".") else "." + arg)])),

    ('regexp',
     RegexpFilter(Markup(r'Regular expression. Examples: <code>regexp:(?i)\bs?printf</code> <code>regexp:"(three|3) mice"</code>'))),

    ('text',
     TextFilter('')),

    ('function',
     ExistsLikeFilter(
         description = Markup('Function or method definition: <code>function:foo</code>'),
         tables = ['functions AS {a}'],
         like_name = "{a}.name",
         qual_name = "{a}.qualname")),

    ('function-ref',
     ExistsLikeFilter(
         description = 'Function or method references',
         tables = ['function_refs AS {a}', 'functions AS {f}'],
         wheres = ['{f}.id={a}.refid'],
         like_name = "{f}.name",
         qual_name = "{f}.qualname")),

    ('function-decl',
     ExistsLikeFilter(
         description = 'Function or method declaration',
         tables = ['function_decldef AS {a}', 'functions AS {f}'],
         wheres = ['{f}.id={a}.defid'],
         like_name = "{f}.name",
         qual_name = "{f}.qualname")),

    ('callers', UnionFilter([
      # direct calls
      ExistsLikeFilter(
          tables = ['functions AS {a}', 'functions AS {t}', 'callers AS {c}'],
          wheres = ['{c}.targetid={t}.id', '{c}.callerid={a}.id'],
          like_name = "{t}.name",
          qual_name = "{t}.qualname"),
      # indirect calls
      ExistsLikeFilter(
          tables = ['functions AS {a}', 'functions AS {t}', 'callers AS {c}', 'targets AS {s}'],
          wheres = ['{s}.funcid={t}.id', '{s}.targetid={c}.targetid', '{c}.callerid={a}.id'],
          like_name = "target.name",
          qual_name = "target.qualname")],
      description = Markup('Functions which call the given function or method: <code>callers:GetStringFromName</code>'))),

    ('called-by', UnionFilter([
      # direct calls
      ExistsLikeFilter(
          tables = ['functions AS {a}', 'functions AS {c}', 'callers AS {s}'],
          wheres = ['{s}.callerid={c}.id', '{s}.targetid={a}.id'],
          like_name = "{c}.name",
          qual_name = "{c}.qualname"
      ),
      # indirect calls
      ExistsLikeFilter(
          tables = ['functions AS {a}', 'functions AS {c}', 'callers AS {d}', 'targets AS {t}'],
          # {c} is caller, {a} is target
          wheres = ['{d}.callerid={c}.id', '{t}.funcid={a}.id', '{t}.targetid={d}.targetid'],
          like_name = "{c}.name",
          qual_name = "{c}.qualname"
      )],
      description = 'Functions or methods which are called by the given one')),

    ('type', UnionFilter([
      ExistsLikeFilter(
        tables = ['types AS {a}'],
        like_name = "{a}.name",
        qual_name = "{a}.qualname"
      ),
      ExistsLikeFilter(
        tables = ['typedefs AS {a}'],
        like_name = "{a}.name",
        qual_name = "{a}.qualname")],
      description = Markup('Type or class definition: <code>type:Stack</code>'))),

    ('type-ref', UnionFilter([
      ExistsLikeFilter(
        tables = ['type_refs AS {a}', 'types AS {t}'],
        wheres = ['{a}.refid={t}.id'],
        like_name = "{t}.name",
        qual_name = "{t}.qualname"
      ),
      ExistsLikeFilter(
        tables = ['typedef_refs AS {a}', 'typedefs AS {d}'],
        wheres = ['{a}.refid={d}.id'],
        like_name = "{d}.name",
        qual_name = "{d}.qualname")],
      description = 'Type or class references, uses, or instantiations')),

    ('type-decl',
     ExistsLikeFilter(
       description = 'Type or class declaration',
       tables = ['type_decldef AS {a}', 'types AS {t}'],
       wheres = ['{a}.defid={t}.id'],
       like_name = "{t}.name",
       qual_name = "{t}.qualname")),

    ('var',
     ExistsLikeFilter(
       description = 'Variable definition',
       tables = ['variables AS {a}'],
       like_name = "{a}.name",
       qual_name = "{a}.qualname")),

    ('var-ref',
     ExistsLikeFilter(
         description = 'Variable uses (lvalue, rvalue, dereference, etc.)',
         tables = ['variable_refs AS {a}', 'variables AS {v}'],
         wheres = ['{a}.refid={v}.id'],
         like_name = "{v}.name",
         qual_name = "{v}.qualname")),

    ('var-decl',
     ExistsLikeFilter(
         description = 'Variable declaration',
         tables = ['variable_decldef AS {a}', 'variables AS {v}'],
         wheres = ['{a}.defid={v}.id'],
         like_name = "{v}.name",
         qual_name = "{v}.qualname")),

    ('macro',
     ExistsLikeFilter(
         description = 'Macro definition',
         tables = ['macros AS {a}'],
         like_name = "{a}.name",
         qual_name = "{a}.name")),

    ('macro-ref',
     ExistsLikeFilter(
         description = 'Macro uses',
         tables = ['macro_refs AS {a}', 'macros AS {m}'],
         wheres = ['{m}.id={a}.refid'],
         like_name = "{m}.name",
         qual_name = "{m}.name")),

    ('namespace',
     ExistsLikeFilter(
         description = 'Namespace definition',
         tables = ['namespaces AS {a}'],
         like_name = "{a}.name",
         qual_name = "{a}.qualname")),

    ('namespace-ref',
     ExistsLikeFilter(
         description = 'Namespace references',
         tables = ['namespace_refs AS {a}', 'namespaces AS {n}'],
         wheres = ['{a}.refid={n}.id'],
         like_name = "{n}.name",
         qual_name = "{n}.qualname")),

    ('namespace-alias',
     ExistsLikeFilter(
         description = 'Namespace alias',
         tables = ['namespace_aliases AS {a}'],
         like_name = "{a}.name",
         qual_name = "{a}.qualname")),

    ('namespace-alias-ref',
     ExistsLikeFilter(
         description = 'Namespace alias references',
         tables = ['namespace_alias_refs AS {a}', 'namespace_aliases AS {n}'],
         wheres = ['{a}.refid={n}.id'],
         like_name = "{n}.name",
         qual_name = "{n}.qualname")),

    ('bases',
     ExistsLikeFilter(
         description = Markup('Superclasses of a class: <code>bases:SomeSubclass</code>'),
         tables = ['types AS {a}', 'impl AS {i}', 'types AS {t}'],
         # [a} is base type, {t} is derived type
         wheres = ['{i}.tbase={a}.id', '{i}.tderived={t}.id'],
         like_name = "{t}.name",
         qual_name = "{t}.qualname")),

    ('derived',
     ExistsLikeFilter(
         description = Markup('Subclasses of a class: <code>derived:SomeSuperclass</code>'),
         tables = ['types AS {a}', 'impl AS {i}', 'types AS {t}'],
         # [a} is subtype
         wheres = ['{i}.tbase={t}.id', '{i}.tderived={a}.id'],
         like_name = "{t}.name",
         qual_name = "{t}.qualname")),

    ('member', UnionFilter([
      # member filter for functions
      ExistsLikeFilter(
        tables = ['functions AS {a}', 'types AS {t}'],
        wheres = ['{a}.scopeid={t}.id'],
        like_name = "{t}.name",
        qual_name = "{t}.qualname"
      ),
      # member filter for types
      ExistsLikeFilter(
        tables = ['types AS {a}', 'types AS {t}'],
        wheres = ['{a}.scopeid={t}.id'],
        like_name = "{t}.name",
        qual_name = "{t}.qualname"
      ),
      # member filter for variables
      ExistsLikeFilter(
        tables = ['variables AS {a}', 'types AS {t}'],
        wheres = ['{a}.scopeid={t}.id'],
        like_name = "{t}.name",
        qual_name = "{t}.qualname")],
      description = Markup('Member variables, types, or methods of a class: <code>member:SomeClass</code>'))),

    ('overridden',
     ExistsLikeFilter(
         description = Markup('Methods which are overridden by the given one. Useful mostly with fully qualified methods, like <code>+overridden:Derived::foo()</code>.'),
         tables = ['base AS {a}', 'functions AS {d}', 'targets AS {t}'],
         wheres = ['{a}.id=-{t}.targetid', '{d}.id={t}.funcid', '{a}.id<>{d}.id'],
         like_name = "{d}.name",
         qual_name = "{d}.qualname")),

    ('overrides',
     ExistsLikeFilter(
         description = Markup('Methods which override the given one: <code>overrides:someMethod</code>'),
         tables = ['functions AS {b}', 'functions AS {a}', 'targets AS {t}'],
         # {b} is base, {a} is derived
         wheres = ['{b}.id =-{t}.targetid', '{a}.id={t}.funcid', '{b}.id<>{a}.id'],
         like_name = "{b}.name",
         qual_name = "{b}.qualname")),

    ('warning',
     ExistsLikeFilter(
         description = 'Compiler warning messages',
         tables = ['warnings AS {a}'],
         like_name = "{a}.msg",
         qual_name = "{a}.msg")),

    ('warning-opt',
     ExistsLikeFilter(
         description = 'Warning messages brought on by a given compiler command-line option',
         tables = ['warnings AS {a}'],
         like_name = "{a}.opt",
         qual_name = "{a}.opt"
     ))
])
