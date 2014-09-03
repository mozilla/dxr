"""An extractor of boolean trigram queries from a regex, such that a superset
of the docs matching the regex are returned. You can then run the actual regex
over just the returned docs, saving a lot of computation and IO.

Junghoo Ch and Sridhar Rajagopalan, in "A fast regular expression indexing
engine", descibe an intuitive method for accelerating regex searching with a
trigram index. Russ Cox, in http://swtch.com/~rsc/regexp/regexp4.html, refines
that to {(1) extract use from runs of less than 3 static chars and (2) extract
trigrams that cross the boundaries between subexpressions} by keeping track of
prefix and suffix information while chewing through a pattern and effectively
merging adjacent subpatterns. This is an implementation of his method.

"""
from parsimonious import Grammar
from parsimonious.nodes import NodeVisitor


class TrigramQuery(object):
    """A query which matches a superset of the docs its corresponding regex
    does. Abstract.

    """
    def __init__(self, trigrams, subassertions):
        """I am a logical AND or OR of trigrams and subassertions.

        These are divided just for implementation ease.

        :arg trigrams: A list of trigram strings
        :arg subassertions: A list of Assertions

        """
        self.trigrams = trigrams
        self.subassertions = subassertions


class And(TrigramQuery):
    pass


class Or(TrigramQuery):
    pass


# class None?
# class Any?


class RegexSummary(object):
    """The digested result of analyzing a parsed regex

    :attr can_match_empty: Whether the regex can match the empty string
    :attr exacts: Set of exact strings which, unioned, exhaust the regex. For
        example (s?printf) would yield {sprintf, printf}.
    :attr prefixes: The set of prefixes of strings the regex can match
    :attr suffixes: The set of suffixes of strings the regex can match
    :attr query: An TrigramQuery that must be satisfied by any matching
        string, in addition to the restrictions expressed by the other
        attributes

    Prefixes, suffixes, and the rest are used only as intermediate values. The
    point is for them ultimately to become part of the query, which is itself a
    boolean combination of trigrams.

    """
    def __init__(self, regex):
        """Dispatch on the opcode of regex, and descend recursively, analyzing
        lower nodes and then pulling back up to finally summarize the whole.

        :arg regex: A parsed regex, as returned by ``sre_parse.parse()``

        """
        self.can_match_empty = can_match_empty
        self.exacts = exacts
        self.prefix = prefix  # This can probably be an actual set. The Go impl blows a lot of code removing dupes and such.
        self.suffix = suffix
        self.query = query


def trigrams(s):
    """Return an iterable of all trigrams contained in a string."""
    # Optimization: return indices rather than actual substrings to save
    # instantiation cost.
    return (s[i:i + 3] for i in xrange(0, len(s) - 2))


def summarize_regex(regex):
    """Return a RegexSummary of a regex.

    :arg regex: A string containing a regex pattern

    """


def trigram_query(regex):
    """Return an iterable of trigrams that will be found in any text matching
    the given regex.

    :arg regex: A string containing a regex pattern

    """
    # TODO: Veto patterns which are easy DOSes.

    # I suspect simplify(force=True) mashes everything down into `match` in
    # preparation for actually running `match` against a corpus.

    summary = RegexSummary(regex)
    summary.simplify(force=True)
    summary.add_exact()
    return summary.query


def trigrammify_tree(tree):
    """Explode the strings in a tree into trigrams. Return a tree whose leaves are trigrams and whose inner nodes are boolean operations. This can then be trivially turned into an ES query."""
    # Remember that Lucene regexes are always anchored. The caller will have to add a leading .*, etc.
    # Raise an exception somewhere, maybe in simplify_tree, if there are no trigrams.


def simplify_tree(tree):
    """Do the node reduction to collapse branches of a string tree that aren't
    useful. Remove strings that aren't long enough to generate any trigrams."""


def build_tree(regex):
    """Turn a parsed regex into a tree of ANDed and ORed literal strings."""
    op, param = regex
    if op == 'branch':
        mystery, alternatives = param
        return or_(string_tree(alternatives))
    elif op == 'literal':
        return param


# We should parse a regex. Then go over the tree and turn things like c+ into cc*, perhaps, as it makes it easier to see trigrams to extract.
# TODO: Parse normal regex syntax, but spit out Lucene-compatible syntax, with " escaped. And all special chars escaped even in character classes, in accordance with https://lucene.apache.org/core/4_6_0/core/org/apache/lucene/util/automaton/RegExp.html?is-external=true.

BACKSLASH_SPECIAL_CHARS = 'AbBdDsSwWZ'

# This recognizes a subset of Python's regex language, minus lookaround
# assertions, non-greedy quantifiers, and named and other special sorts of
# groups. Lucene doesn't support those, though we might be able to fake it
# later via some transformation.
regex_grammar = Grammar(r"""
    regexp = branch more_branches
    more_branches = another_branch*  # TODO: If I merge this into regexp, why does generic_visit() start getting called for it?
    branch = piece*
    another_branch = "|" branch
    piece = quantified / atom
    quantified = atom quantifier
    quantifier = "*" / "+" / "?" / repeat
    repeat = "{" repeat_range "}"
    repeat_range = number ("," number)?
    number = ~r"\d+"

    # By making each parenthesized subexpr just a "regexp", visit_regexp can
    # assign group numbers, starting from 0, and the top-level expression
    # conveniently ends up in the conventional group 0.
    atom = group / class / hat / dollars / dot / char  # Optimize: vacuum up any harmless sequence of chars in one regex, first: [^()[\]^$.?*+{}]+
    group = "(" regexp ")"
    hat = "^"
    dollars = "$"
    dot = "."

    # Character classes are pretty complex little beasts, even though we're
    # just scanning right over them rather than trying to pull any info out:
    class = "[" (inverted_class_start / positive_class_start) initial_class_char class_char* "]"
    inverted_class_start = "^"
    positive_class_start = !"^"
    # An unescaped ] is treated as a literal when the first char of a positive
    # or inverted character class:
    initial_class_char = "]" / class_char
    class_char = backslash_char / ~r"[^\]]"

    char = backslash_char / literal_char
    backslash_char = "\\" backslash_operand
    backslash_operand = backslash_special / backslash_hex / backslash_normal
    # We require escaping ]{} even though these are tolerated unescaped by
    # Python's re parser:
    literal_char = ~r"[^^$?*+()[\]{}|.\\]"
    # Char class abbreviations and untypeable chars:
    backslash_special = ~r"[""" + BACKSLASH_SPECIAL_CHARS + """aefnrtv]"
    backslash_hex = ~r"x[0-9a-fA-F]{2}"
    # Normal char with no special meaning:
    backslash_normal = ~"."
    """)

# TODO: Expand positive char classes so we can get trigrams out of [sp][rne]
# (trilite expands char classes of up to 10 chars but does nothing for larger
# ones), and be able to get trigrams out of sp(rint) as well. Production
# currently does that much. It is not, however, smart enough to expand
# spr{1,3}, not spr+. An easy way would be to keep track of prefixes and
# suffixes (and trigram-or-better infixes) for each node, then work our way up
# the tree.


class StringTreeNode(list):
    """A node specifying a boolean operator, with strings or more such nodes as
    its children"""

    def __init__(self, iterable=()):
        self.extend(iterable)

    def __str__(self):
        return repr(self)

    def __ne__(self, other):
        return not self == other

    def __eq__(self, other):
        return (self.__class__ is other.__class__ and
                super(StringTreeNode, self).__eq__(other))

    def simplified():
        """Return a simpler but equivalent tree structure.

        Simplify by collapsing nodes with only 1 child.

        """
        # NEXT: Probably finish this. We'll need it in any case, and it makes
        # tests shorter to write. But also think about implementing the Cox
        # method. I now see that I'm going to have to write some kind of
        # theorems into even the FREE method if I want to be able to extract
        # trigrams from ab[cd] (prefixes, cross products), so I might as well
        # use Cox's. We can code his theorems right into the visitor. I don't
        # think it will get too messy. Low-level nodes' visitation will just
        # cast strings to ints, etc., and high-level ones will just apply Cox
        # theorems.
        # Btw, http://code.ohloh.net/file?fid=rfNSbmGXJxqJhWDMLp3VaEMUlgQ&cid=eDOmLT58hyw&s=&fp=305491&mp=&projSelected=true#L0 is PG's explanation of their simplification stuff.
        simple_children = ifilter(None, (n.simplified() for n in self))
        if len(self) > 1:
            return self.__class__(simple_children)
        elif len(self) == 1:
            raise NotiMplementedError
        else:  # Empty nodes occur at empty regex branches.
            return


class Useless(StringTreeNode):
    """This doubles as the singleton USELESS and a "ruined" Or, to which adding
    anything yields USELESS back.

    Don't construct any more of these.

    """
    def __repr__(self):
        return 'USELESS'

    def appended(self, branch):
        return self

    def extended(self, branches):
        return self


# Stand-in for a subpattern that's useless for producing trigrams. It is opaque
# for our purposes, either intrinsically or just because we're not yet smart
# enough to shatter it into a rain of ORed literals. USELESS breaks the
# continuity between two things we *can* extract trigrams from, meaning we
# shouldn't try making any trigrams that span the two.
USELESS = Useless()


class And(StringTreeNode):
    """A list of strings (or other Ands and Ors) which will all be found in
    texts matching a given node

    The strings herein are not necessarily contiguous with each other.

    """
    # If we just hit a non-string, we should break the previous string of chars
    # and start a new one:
    string_was_interrupted = True

    def __repr__(self):
        return 'And(%s)' % super(And, self).__repr__()

    def appended(self, thing):
        """Add a string or And or Or as one of my children.

        Merge it with the previous node if both are string literals. Return
        myself. If the new thing is something useless for the purpose of
        extracting trigrams, don't add it.

        """
        if thing is USELESS:  # TODO: Doesn't handle Ors. Why not?
            # ANDs eat USELESSes. We can ignore it.
            self.string_was_interrupted = True
        elif isinstance(thing, basestring):
            if self.string_was_interrupted:
                self.string_was_interrupted = False
                self.append(thing)
            else:
                self[-1] += thing
        else:  # an And or Or node
            self.string_was_interrupted = True
            self.append(thing)
        return self

    def extended(self, things):
        a = self
        for t in things:
            a = a.appended(t)
        return a


# NEXT: Simplify(), break strings into trigrams, uniquify them, and build a
# query. Then see about exploiting some of the more opaque features of
# regexes more intelligently.


class Or(StringTreeNode):
    """A list of strings (or other Ands and Ors) of which one will be found in
    all texts matching a given node"""

    def __repr__(self):
        return 'Or(%s)' % super(Or, self).__repr__()

    def appended(self, branch):
        """Add a string or And or Or as one of my children.

        Return myself. If the new branch is something that makes me become
        useless for the purpose of extracting trigrams, return USELESS.

        """
        if branch is USELESS:
            return USELESS
        self.append(branch)
        return self

    def extended(self, branches):
        """Like ``appended`` but for multiple children"""
        if USELESS in branches:
            return USELESS
        self.extend(branches)
        return self


class TrigramTreeVisitor(NodeVisitor):
    """Visitor that converts a parsed ``regex_grammar`` tree into one suitable
    for extracting logical trigram queries from.

    In the returned tree, strings represent literal strings, ruling out any
    fancy meanings like "*" would have.

    I throw away any information that can't contribute to trigrams. In the
    future, we might throw away less, expanding things like ``[ab]`` to
    ``OR('a', 'b')``.

    """
    visit_piece = visit_atom = visit_initial_class_char = visit_char = \
            visit_backslash_operand = NodeVisitor.lift_child

    # Not only does a ^ or a $ break up two otherwise contiguous literal
    # strings, but there is no text which matches a^b or a$b.
    visit_hat = visit_dollars = visit_dot = lambda self, node, children: USELESS

    backslash_special_chars = {'a': '\a',
                               'e': '\x1B',  # for PCRE compatibility
                               'f': '\f',
                               'n': '\n',
                               'r': '\r',
                               't': '\t',
                               'v': '\v'}
    quantifier_expansions = {'*': (0, ''),
                             '+': (1, ''),
                             '?': (0, 1)}


    def generic_visit(self, node, children):
        """Return the node verbatim if we have nothing better to do.

        These will all be thrown away.

        """
        return node

    def visit_regexp(self, regexp, (branch, other_branches)):
        o = Or().appended(branch)
        o = o.extended(other_branches)
        return o

    def visit_branch(self, branch, pieces):
        """Merge adjacent literals (anything we could turn into a string).

        Return an And.

        """
        # All this thing's possible children return strings, Ors, or USELESS.
        a = And().extended(pieces)
        if not a:
            # Represent a 0-length And with an empty string, for consistency.
            a.append('')
        return a

    def visit_more_branches(self, more_branches, branches):
        return branches

    def visit_another_branch(self, another_branch, (pipe, branch)):
        return branch

    def visit_quantified(self, quantified, (atom, (min, max))):
        # TODO: This is one place to make smarter. Return USELESS less often.
        # At the moment, we just return one copy of ourselves iff we have a min
        # of at least 1.
        return atom if min else USELESS

    def visit_quantifier(self, or_, (quantifier,)):
        """Return a tuple of (min, max), where '' means infinity."""
        return quantifier_expansions.get(quantifier, quantifier)

    def visit_repeat(self, repeat, (brace, repeat_range, end_brace)):
        return repeat_range

    def visit_repeat_range(self, repeat_range, children):
        """Return a tuple of (min, max) representing a repeat range.

        If max is unspecified (open-ended), return '' for max.

        """
        min, comma, max = repeat_range.text.partition(',')
        return int(min), (max if max == '' else int(max))

    def visit_number(self, number, children):
        return int(number)

    def visit_group(self, group, (paren, regexp, end_paren)):
        return regexp

    def visit_class(self, class_, children):
        # We can improve this later by breaking it into an OR or by just
        # implementing the Cox method.
        return USELESS

    def visit_literal_char(self, literal_char, children):
        return literal_char.text

    def visit_backslash_special(self, backslash_special, children):
        """Return a char if there is a char equivalent. Otherwise, return a
        BackslashSpecial."""
        return self.backslash_specials.get(backslash_special.text, USELESS)

    def visit_backslash_char(self, backslash_char, (backslash, operand)):
        """Return the visited char or special thing. Lose the backslash."""
        return operand

    def visit_backslash_hex(self, backslash_hex, children):
        """Return the character specified by the hex code."""
        return chr(backslash_char.text[1:])

    def visit_backslash_normal(self, backslash_normal, children):
        return backslash_normal.text
