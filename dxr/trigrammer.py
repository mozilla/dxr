"""An extractor of boolean trigram queries from a regex, such that a superset
of the docs matching the regex are returned. You can then run the actual regex
over just the returned docs, saving a lot of computation and IO.

We support a subset of the PCRE regex language at the moment, lacking
lookarounds and noncapturing parens. We can add those later after we decide
the consequences they have for substring extraction. We may be selective about
what we support in order to avoid regex-based DOS attacks, but, aside from
that, DXR's flavor of regex should approach some more popular flavor as
closely as possible.

Junghoo Ch and Sridhar Rajagopalan, in "A fast regular expression indexing
engine", descibe an intuitive method for accelerating regex searching with a
trigram index. This is roughly an implementation of that.

Russ Cox, in http://swtch.com/~rsc/regexp/regexp4.html, refines
that to {(1) extract use from runs of less than 3 static chars and (2) extract
trigrams that cross the boundaries between subexpressions} by keeping track of
prefix and suffix information while chewing through a pattern and effectively
merging adjacent subpatterns. This is a direction we may go in the future.

"""
from itertools import chain

from parsimonious import Grammar, NodeVisitor


NGRAM_LENGTH = 3


class NoTrigrams(Exception):
    """We couldn't extract any trigrams (or longer) from a regex."""


# We should parse a regex. Then go over the tree and turn things like c+ into cc*, perhaps, as it makes it easier to see trigrams to extract.
# TODO: Parse normal regex syntax, but spit out Lucene-compatible syntax, with " escaped. And all special chars escaped even in character classes, in accordance with https://lucene.apache.org/core/4_6_0/core/org/apache/lucene/util/automaton/RegExp.html?is-external=true.

# TODO: Expand positive char classes so we can get trigrams out of [sp][rne]
# (trilite expands char classes of up to 10 chars but does nothing for larger
# ones), and be able to get trigrams out of sp(rint) as well. Production
# currently does that much. It is not, however, smart enough to expand
# spr{1,3}, nor spr+. An easy way would be to keep track of prefixes and
# suffixes (and trigram-or-better infixes) for each node, then work our way up
# the tree.


class SubstringTree(list):
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
                super(SubstringTree, self).__eq__(other))

    def simplified(self, min_length=NGRAM_LENGTH):
        """Return a smaller but equivalent tree structure or a string.

        Simplify by turning nodes with only 1 child into mere strings and
        removing nodes with 0. If the top-level node ends up having 0
        children, the final result is ``u''``.

        """
        def simplified(tree_or_string):
            """Typewise dispatcher to turn short strings into '' and
            recursively descend Ands and Ors"""
            if isinstance(tree_or_string, basestring):
                return (tree_or_string if len(tree_or_string) >= min_length
                        else '')
            return tree_or_string.simplified(min_length=min_length)

        # TODO: Think about implementing the Cox method. I now see that I'm
        # going to have to write some kind of theorems into even the FREE
        # method if I want to be able to extract trigrams from ab[cd]
        # (prefixes, cross products), so I might as well use Cox's. We can
        # code his theorems right into the visitor. I don't think it will get
        # too messy. Low-level nodes' visitation will just cast strings to
        # ints, etc., and high-level ones will just apply Cox theorems. Btw,
        # http://code.ohloh.net/file?fid=rfNSbmGXJxqJhWDMLp3VaEMUlgQ&cid=
        # eDOmLT58hyw&s=&fp=305491&mp=&projSelected=true#L0 is PG's
        # explanation of their simplification stuff.

        # Filter out empty strings and empty subtrees, both of which are
        # equally useless. (Remember, adjacent strings in an And don't mean
        # adjacent strings in the found text, so a '' in an Or doesn't help us
        # narrow down the result set at all.)
        simple_children = filter(None,
                                 (simplified(n) for n in self))
        if len(simple_children) > 1:
            return self.__class__(simple_children)
        elif len(simple_children) == 1:
            return simple_children[0]
        else:  # Empty nodes occur at empty regex branches.
            return u''


class Useless(SubstringTree):
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


class And(SubstringTree):
    """A list of strings (or other Ands and Ors) which will all be found in
    texts matching a given node

    The strings herein are not necessarily contiguous with each other, but two
    strings appended in succession are taken to be contiguous and are merged
    internally.

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


class Or(SubstringTree):
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


class BadRegex(Exception):
    """A user-provided regular expression was invalid."""


# Sequences that represent something fancier than just a single, unchanging
# char:
BACKSLASH_METAS = 'AbBdDsSwWZ'
# Single chars that have to be backslashed in regexes lest they mean something
# else:
NONLITERALS = r'][^$?*+(){}|\.'

# This recognizes a subset of Python's regex language, minus lookaround
# assertions, non-greedy quantifiers, and named and other special sorts of
# groups. Lucene doesn't support those, though we might be able to fake it
# later via some transformation. [We're no longer using Lucene regexes, so it
# doesn't matter.]
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
    atom = group / inverted_class / class / hat / dollars / dot / char  # Optimize: vacuum up any harmless sequence of chars in one regex, first: [^()[\]^$.?*+{}]+
    group = "(" regexp ")"
    hat = "^"
    dollars = "$"
    dot = "."

    inverted_class = "[^" class_contents "]"
    class = "[" !"^" class_contents "]"

    # An unescaped ] is treated as a literal when the first char of a positive
    # or inverted character class:
    class_contents = "]"? class_items  # ['x', USELESS, ('a', 'z')]

    class_items = class_item*
    class_item = char_range / class_char
    char_range = class_char "-" class_char  # ('a', 'z') or USELESS

    # Chars like $ that are ordinarily special are not special inside classes.
    class_char = backslash_char / literal_class_char  # 'x' or USELESS
    literal_class_char = ~"[^]]"

    char = backslash_char / literal_char
    backslash_char = "\\" backslash_operand
    backslash_operand = backslash_special / backslash_hex / backslash_normal
    # We require escaping ]{} even though these are tolerated unescaped by
    # Python's re parser:
    literal_char = ~r"[^""" +
        # \ inside a Python regex char class is an escape char. Escape it:
        NONLITERALS.replace('\\', r'\\') + r"""]"
    # Char class abbreviations and untypeable chars:
    backslash_special = ~r"[""" + BACKSLASH_METAS + r"""aefnrtv]"
    backslash_hex = ~r"x[0-9a-fA-F]{2}"
    # Normal char with no special meaning:
    backslash_normal = ~"."
    """)


class SubstringTreeVisitor(NodeVisitor):
    """Visitor that converts a parsed ``regex_grammar`` tree into one suitable
    for extracting boolean substring queries from.

    In the returned tree, strings represent literal strings, ruling out any
    fancy meanings like "*" would have.

    I throw away any information that can't contribute to trigrams. In the
    future, we might throw away less, expanding things like ``[ab]`` to
    ``Or(['a', 'b'])``.

    """
    unwrapped_exceptions = (BadRegex,)

    visit_piece = visit_atom = visit_char = visit_class_char = \
        visit_class_item = visit_backslash_operand = NodeVisitor.lift_child

    # Not only does a ^ or a $ break up two otherwise contiguous literal
    # strings, but there is no text which matches a^b or a$b.
    visit_hat = visit_dollars = visit_dot = visit_inverted_class = \
        lambda self, node, children: USELESS

    backslash_specials = {'a': '\a',
                          'e': '\x1B',  # for PCRE compatibility
                          'f': '\f',
                          'n': '\n',
                          'r': '\r',
                          't': '\t',
                          'v': '\v'}  # TODO: What about \s and such?
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
        # It'll either be in the hash, or it will have already been broken
        # down into a tuple by visit_repeat_range.
        return self.quantifier_expansions.get(quantifier.text, quantifier)

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

    def visit_class(self, class_, (bracket, no_hat, contents, end_bracket)):
        """Return an Or of unicode chars and 2-tuples of unicode chars.

        If the class has too many members, to the point where we guess the
        expense of checking so many Or branches in ES would be greater than
        the selectivity benefit, return USELESS.

        """
        MAX_ORS = 5  # Wild guess. Tune.
        if USELESS in contents:  # Or-ing with USELESS = USELESS.
            return USELESS
        if len(contents) > MAX_ORS:
            return USELESS
        if sum((1 if isinstance(x, basestring) else ord(x[1]) - ord(x[0]) + 1)
               for x in contents) > MAX_ORS:
            return USELESS
        return Or(chain.from_iterable(x if isinstance(x, basestring) else
                                      (unichr(y) for y in xrange(ord(x[0]),
                                                              ord(x[1]) + 1))
                                      for x in contents))

    def visit_class_contents(self, class_contents, (maybe_bracket,
                                                    class_items)):
        """Return a list of unicode chars, USELESS, and 2-tuples of unicode
        chars."""
        items = [']'] if maybe_bracket.text else []
        items.extend(getattr(i, 'text', i) for i in class_items)
        return items

    def visit_class_items(self, class_item, items):
        """Keep class_item from using visit_generic, which would do the wrong
        thing."""
        return items

    def visit_char_range(self, char_range, (start, _, end)):
        """Return (start char, end char) bounding a char range or USELESS."""
        if start is USELESS or end is USELESS:
            return USELESS
        if start.text > end.text:
            raise BadRegex(u'Out-of-order character range: %s-%s' %
                           (start.text, end.text))
        return start.text, end.text

    def visit_literal_char(self, literal_char, children):
        return literal_char.text

    def visit_backslash_special(self, backslash_special, children):
        """Return a char if there is a char equivalent. Otherwise, return a
        BackslashSpecial."""
        # TODO: Don't return USELESS so much.
        return self.backslash_specials.get(backslash_special.text, USELESS)

    def visit_backslash_char(self, backslash_char, (backslash, operand)):
        """Return the visited char or special thing. Lose the backslash."""
        return operand

    def visit_backslash_hex(self, backslash_hex, children):
        """Return the character specified by the hex code."""
        return unichr(backslash_hex.text[1:])

    def visit_backslash_normal(self, backslash_normal, children):
        return backslash_normal.text


class JsRegexVisitor(NodeVisitor):
    """Visitor for converting a parsed DXR-flavored regex to a JS equivalent"""

    # All specials but these just stay the same between DXR-flavored and
    # JS-flavored regexes:
    backslash_specials = {'a': r'\x07',
                          'e': r'\x1B'}

    def text_of_node(self, node, children):
        return node.text

    visit_piece = visit_atom = visit_class_item = visit_class_char = \
        visit_char = visit_backslash_operand = NodeVisitor.lift_child

    visit_literal_char = visit_dot = visit_dollars = visit_hat = text_of_node

    visit_regexp = visit_more_branches = visit_branch = visit_quantified = \
        visit_class_items = lambda self, node, children: u''.join(children)

    def generic_visit(self, node, children):
        """We ignore some nodes and handle them higher up the tree."""
        return node

    def visit_another_branch(self, another_branch, (pipe, branch)):
        return u'|{0}'.format(branch)

    def visit_quantifier(self, quantifier, children):
        """All quantifiers are the same in JS as in DXR-flavored regexes."""
        return quantifier.text

    def visit_group(self, group, (paren, regexp, end_paren)):
        return u'({0})'.format(regexp)

    def visit_inverted_class(self, class_, (bracket_and_hat,
                                            contents,
                                            end_bracket)):
        return u'[^{0}]'.format(u''.join(contents))

    def visit_class(self, class_, (bracket, no_hat, contents, end_bracket)):
        return u'[{0}]'.format(u''.join(contents))

    def visit_class_contents(self, class_contents, (maybe_bracket,
                                                    class_items)):
        bracket = u']' if maybe_bracket.text else u''
        return bracket + u''.join(class_items)

    def visit_char_range(self, char_range, (start, _, end)):
        return u'{0}-{1}'.format(start, end)

    def visit_literal_class_char(self, literal_class_char, children):
        """Turn a boring, normal class char into text."""
        return literal_class_char.text

    def visit_backslash_char(self, backslash_char, (backslash, operand)):
        """We reapply the backslash at lower-level nodes than this so we don't
        accidentally preserve backslashes on chars that don't need them, like
        c.

        That would be bad for c, because \\c is special in JS (but not in
        DXR-flavored regexes.

        """
        return operand

    def visit_backslash_special(self, backslash_special, children):
        """Return the unchanged char (without the backslash)."""
        return u'\\' + self.backslash_specials.get(backslash_special.text,
                                                   backslash_special.text)

    def visit_backslash_hex(self, backslash_hex, children):
        return u'\\' + backslash_hex.text

    def visit_backslash_normal(self, backslash_normal, children):
        """Take unnecessary backslashes away so we don't end up treading on
        metas that are special only in JS, like \\c."""
        char = backslash_normal.text
        return ur'\{0}'.format(char) if char in NONLITERALS else char


class PythonRegexVisitor(JsRegexVisitor):
    """Visitor for converting a parsed DXR-flavored regex to a Python
    equivalent, for highlighting

    There's really only one spot where Python's regex language (or at least
    the parts whose functionality is implemented by DXR's flavor so far)
    differ from JS's: Python's understands \a natively. There are other
    differences, like Python's tolerance for unescaped ], {, and } in contrast
    to our insistence at backslash-escaping them, but those differences go in
    the other direction and so don't matter when translating from DXR to
    Python.

    """
    # Python supports the rest of the escape sequences natively.
    backslash_specials = {'e': r'\x1B'}


def boolean_filter_tree(substrings, trigram_field):
    """Return a (probably nested) ES filter clause expressing the boolean
    constraints embodied in ``substrings``.

    :arg substrings: A SubstringTree
    :arg trigram_field: The ES property under which a trigram index of the
        field to match is stored

    """
    if isinstance(substrings, basestring):
        return {
            'query': {
                'match_phrase': {
                    trigram_field: substrings
                }
            }
        }
    return {
        'and' if isinstance(substrings, And) else 'or':
            [boolean_filter_tree(x, trigram_field) for x in substrings]
    }


def es_regex_filter(parsed_regex, raw_field, is_case_sensitive):
    """Return an efficient ES filter to find matches to a regex.

    Looks for fields of which ``regex`` matches a substring. (^ and $ do
    anchor the pattern to the beginning or end of the field, however.)

    :arg parsed_regex: A regex pattern as an AST from regex_grammar
    :arg raw_field: The name of an ES property to match against. The
        lowercase-folded trigram field is assumed to be
        raw_field.trigrams_lower, and the non-folded version
        raw_field.trigrams.
    :arg is_case_sensitive: Whether the match should be performed
        case-sensitive

    """
    trigram_field = ('%s.trigrams' if is_case_sensitive else
                     '%s.trigrams_lower') % raw_field
    substrings = SubstringTreeVisitor().visit(parsed_regex).simplified()

    # If tree is a string, just do a match_phrase. Otherwise, add .* to the
    # front and back, and build some boolean algebra.
    if isinstance(substrings, basestring) and len(substrings) < NGRAM_LENGTH:
        raise NoTrigrams
        # We could alternatively consider doing an unaccelerated Lucene regex
        # query at this point. It would be slower but tolerable on a
        # moz-central-sized codebase: perhaps 500ms rather than 80.
    else:
        # Should be fine even if the regex already starts or ends with .*:
        js_regex = JsRegexVisitor().visit(parsed_regex)
        return {
            'and': [
                boolean_filter_tree(substrings, trigram_field),
                {
                    'script': {
                        'lang': 'js',
                        # test() tests for containment, not matching:
                        'script': '(new RegExp(pattern, flags)).test(doc["%s"][0])' % raw_field,
                        'params': {
                            'pattern': js_regex,
                            'flags': '' if is_case_sensitive else 'i'
                        }
                    }
                }
            ]
        }
