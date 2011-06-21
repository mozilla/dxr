#!/usr/bin/env python2.6

# Tokenizer code adapted by David Humphrey from Neal Norwitz's C++ tokenizer:
#
# Copyright 2007 Neal Norwitz
# Portions Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import os
from cgi import escape

class Token(object):
    """Data container to represent an IDL token.

    Tokens can be identifiers, syntax char(s), constants, or
    pre-processor directives.

    start contains the index of the first char of the token in the source
    end contains the index of the char just beyond the token in the source
    """

    def __init__(self, token_type, name, start, end, line):
        self.token_type = token_type
        self.name = name
        self.start = start
        self.end = end
        self.line = line

    def __str__(self):
        if not utils.DEBUG:
            return 'Token(%r)' % self.name
        return 'Token(%r, %s, %s)' % (self.name, self.start, self.end)

    __repr__ = __str__


class BaseTokenizer:
    # Token Types
    UNKNOWN = 'unknown'
    NEWLINE = 'newline'
    TEXTLINE = 'textline'

    def __init__(self, source):
        self.source = source

    def getTokens(self):
        line = 1
        i = 0
        end = len(self.source)

        while i < end:
            token_type = self.UNKNOWN
            start = i
            c = self.source[i]
            if c == '\n':
                token_type = self.NEWLINE
                i += 1
                line += 1
            else:
                token_type = self.TEXTLINE
                while i < end and not self.source[i] == '\n':
                    i += 1
                if i >= end: return

            yield Token(token_type, self.source[start:i], start, i, line)


class CppTokenizer(BaseTokenizer):
    # Add $ as a valid identifier char since so much code uses it.
    _letters = 'abcdefghijklmnopqrstuvwxyz'
    VALID_IDENTIFIER_CHARS = frozenset(_letters + _letters.upper() + '_0123456789$')
    HEX_DIGITS = frozenset('0123456789abcdefABCDEF')
    INT_OR_FLOAT_DIGITS = frozenset('01234567890eE-+')

    # C++0x string preffixes.
    _STR_PREFIXES = frozenset(('R', 'u8', 'u8R', 'u', 'uR', 'U', 'UR', 'L', 'LR'))

    # Token types.
    UNKNOWN = 'UNKNOWN'
    SYNTAX = 'SYNTAX'
    CONSTANT = 'CONSTANT'
    NAME = 'NAME'
    PREPROCESSOR = 'PREPROCESSOR'
    NEWLINE = 'NEWLINE'
    COMMENT = 'COMMENT'
    STRING = 'STRING'
    KEYWORD = 'KEYWORD'

    # C++ keywords
    _keywords = frozenset(['auto', 'const', 'double',  'float',  'int', 'short', 'struct', 
                           'unsigned', 'break', 'continue', 'else', 'for', 'long', 'signed',
                           'switch', 'void', 'case', 'default', 'enum', 'goto', 'register',
                           'sizeof' ,'typedef', 'volatile', 'char', 'do', 'extern', 'if',
                           'return', 'static', 'union', 'while', 'asm', 'dynamic_cast',
                           'namespace', 'reinterpret_cast', 'try', 'bool', 'explicit',
                           'new', 'static_cast', 'typeid', 'catch', 'false', 'operator',
                           'template', 'typename', 'class', 'friend', 'private', 'this',
                           'using', 'const_cast', 'inline', 'public', 'throw', 'virtual',
                           'delete', 'mutable', 'protected', 'true', 'wchar_t', 'and',
                           'bitand', 'compl', 'not_eq', 'or_eq', 'xor_eq', 'and_eq', 'bitor',
                           'not', 'or', 'xor'])

    def __init__(self, source):
        BaseTokenizer.__init__(self, source)

    def _getString(self, source, start, i):
        i = source.find('"', i+1)
        while source[i-1] == '\\':
            # Count the trailing backslashes.
            backslash_count = 1
            j = i - 2
            while source[j] == '\\':
                backslash_count += 1
                j -= 1
            # When trailing backslashes are even, they escape each other.
            if (backslash_count % 2) == 0:
                break
            i = source.find('"', i+1)
        return i + 1

    def _getChar(self, source, start, i):
        i = source.find("'", i+1)
        while source[i-1] == '\\':
            # Need to special case '\\'.
            if (i - 2) > start and source[i-2] == '\\':
                break
            i = source.find("'", i+1)
        # Try to handle unterminated single quotes (in a #if 0 block).
        if i < 0:
            i = start
        return i + 1

    def getTokens(self):
        # Cache various valid character sets for speed.
        valid_identifier_chars = self.VALID_IDENTIFIER_CHARS
        hex_digits = self.HEX_DIGITS
        int_or_float_digits = self.INT_OR_FLOAT_DIGITS
        int_or_float_digits2 = int_or_float_digits | set('.')

        # Are we in a multi-line comment?  This is position of comment's start
        in_comment = -1

        # Are we in a multi-line macro? This is the position of the macro's start
        in_macro = -1

        # Only ignore errors while in a #if 0 block.
        ignore_errors = False

        # keep track of which line we're on
        line = 1

        source = self.source

        i = 0
        end = len(source)
        while i < end:
            # Skip whitespace if not in macro/comment.
            if in_comment == -1 and in_macro == -1:
                while i < end and source[i] in [' ', '\t', '\r', '\x0c']:
                    i += 1
                if i >= end:
                    return

            token_type = self.UNKNOWN
            start = i
            c = source[i]
            if c == '\n':
                token_type = self.NEWLINE
                i += 1
            elif in_comment > -1:                      # Deal with being in multi-line comments (report each comment line)
                token_type = self.COMMENT
                while i < end and source[i] != '\n' and not (source[i] == '*' and source[i+1] == '/'):
                    i += 1

                if i >= end:
                    return

                if source[i] == '*' and source[i+1] == '/':
                    in_comment = -1
                    i += 2
            elif in_macro > -1:                        # Deal with being in macros (report each macro line)
                token_type = self.PREPROCESSOR
                while i < end and source[i] != '\n':
                    i += 1

                if i >= end:
                    return

                if source[i-1] != '\\' and source[i] == '\n':
                    in_macro = -1
            elif c.isalpha() or c == '_':              # Find a string token.
                token_type = self.NAME
                while source[i] in valid_identifier_chars:
                    i += 1
                # String and character constants can look like a name if
                # they are something like L"".
                if (source[i] == "'" and (i - start) == 1 and
                    source[start:i] in 'uUL'):
                    # u, U, and L are valid C++0x character preffixes.
                    token_type = self.CONSTANT
                    i = self._getChar(source, start, i)
                elif source[i] == "'" and source[start:i] in self._STR_PREFIXES:
                    token_type = self.CONSTANT
                    i = self._getString(source, start, i)
            elif c == '/' and source[i+1] == '/':    # Find // comments.
                token_type = self.COMMENT
                i = source.find('\n', i)
                if i == -1:  # Handle EOF.
                    i = end
            elif c == '/' and source[i+1] == '*':    # Find /* comments. */
                in_comment = i
                continue
            elif c in ':+-<>&|*=':                   # : or :: (plus other chars).
                token_type = self.SYNTAX
                i += 1
                new_ch = source[i]
                if new_ch == c:
                    i += 1
                elif c == '-' and new_ch == '>':
                    i += 1
                elif new_ch == '=':
                    i += 1
            elif c in '$()[]{}~!?^%;/.,@':             # Handle single char tokens (adding @ for obj-c/c++).
                token_type = self.SYNTAX
                i += 1
                if c == '.' and source[i].isdigit():
                    token_type = self.CONSTANT
                    i += 1
                    while source[i] in int_or_float_digits:
                        i += 1
                    # Handle float suffixes.
                    for suffix in ('l', 'f'):
                        if suffix == source[i:i+1].lower():
                            i += 1
                            break
            elif c.isdigit():                        # Find integer.
                token_type = self.CONSTANT
                if c == '0' and source[i+1] in 'xX':
                    # Handle hex digits.
                    i += 2
                    while source[i] in hex_digits:
                        i += 1
                else:
                    while source[i] in int_or_float_digits2:
                        i += 1
                # Handle integer (and float) suffixes.
                for suffix in ('ull', 'll', 'ul', 'l', 'f', 'u'):
                    size = len(suffix)
                    if suffix == source[i:i+size].lower():
                        i += size
                        break
            elif c == '"':                           # Find string.
                token_type = self.STRING
                i = self._getString(source, start, i)
            elif c == "'":                           # Find char.
                token_type = self.STRING
                i = self._getChar(source, start, i)
            elif c == '#':                           # Find pre-processor command.
                in_macro = i
                continue
            elif c == '\\':                          # Handle \ in code.
                # This is different from the pre-processor \ handling.
                i += 1
                continue
            elif ignore_errors:
                # The tokenizer seems to be in pretty good shape.  This
                # raise is conditionally disabled so that bogus code
                # in an #if 0 block can be handled.  Since we will ignore
                # it anyways, this is probably fine.  So disable the
                # exception and  return the bogus char.
                i += 1
            else:
                sys.stderr.write('Got invalid token in %s @ %d token:%s: %r\n' %
                                 ('?', i, c, source[i-10:i+10]))
                raise RuntimeError('unexpected token')

            if i <= 0:
                print('Invalid index, exiting now.')
                return

            # if we get a NEWLINE, bump line number, but don't report
            if token_type == self.NEWLINE:
                line += 1

            # if this is a keyword, change token type
            if token_type == self.NAME and source[start:i] in self._keywords:
                token_type = self.KEYWORD

            yield Token(token_type, source[start:i], start, i, line)


class IdlTokenizer(CppTokenizer):
    # IDL is close enough to C++ that we just need a new keyword set.
    _keywords = frozenset(['interface', 'attribute', 'readonly', 'uuid', 'scriptable',
                           'const', 'native', 'ptr', 'ref', 'nsid', 'retval', 'shared',
                           'iid_is', 'notxpcom', 'noscript', 'in', 'out', 'inout'])

    def __init__(self, source):
        CppTokenizer.__init__(self, source)
