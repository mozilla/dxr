#!/usr/bin/env python
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

"""Tokenize C++ source code."""

__author__ = 'nnorwitz@google.com (Neal Norwitz), modified david.humphrey@senecac.on.ca (David Humphrey)'

import sys, os
from cgi import escape
import sqlite3
import re

# Add $ as a valid identifier char since so much code uses it.
_letters = 'abcdefghijklmnopqrstuvwxyz'
VALID_IDENTIFIER_CHARS = frozenset(_letters + _letters.upper() + '_0123456789$')
HEX_DIGITS = frozenset('0123456789abcdefABCDEF')
INT_OR_FLOAT_DIGITS = frozenset('01234567890eE-+')

# C++0x string preffixes.
_STR_PREFIXES = frozenset(('R', 'u8', 'u8R', 'u', 'uR', 'U', 'UR', 'L', 'LR'))

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

# Where the token originated from.  This can be used for backtracking.
# It is always set to WHENCE_STREAM in this code.
WHENCE_STREAM, WHENCE_QUEUE = range(2)


class Token(object):
    """Data container to represent a C++ token.

    Tokens can be identifiers, syntax char(s), constants, or
    pre-processor directives.

    start contains the index of the first char of the token in the source
    end contains the index of the last char of the token in the source
    """

    def __init__(self, token_type, name, start, end, line):
        self.token_type = token_type
        self.name = name
        self.start = start
        self.end = end
        self.whence = WHENCE_STREAM
        self.line = line

    def __str__(self):
        if not utils.DEBUG:
            return 'Token(%r)' % self.name
        return 'Token(%r, %s, %s)' % (self.name, self.start, self.end)

    __repr__ = __str__


def _GetString(source, start, i):
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


def _GetChar(source, start, i):
    # NOTE(nnorwitz): may not be quite correct, should be good enough.
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


def GetTokens(source):
    """Returns a sequence of Tokens.

    Args:
      source: string of C++ source code.

    Yields:
      Token that represents the next token in the source.
    """
    # Cache various valid character sets for speed.
    valid_identifier_chars = VALID_IDENTIFIER_CHARS
    hex_digits = HEX_DIGITS
    int_or_float_digits = INT_OR_FLOAT_DIGITS
    int_or_float_digits2 = int_or_float_digits | set('.')

    # Are we in a multi-line comment?  This is position of comment's start
    in_comment = -1

    # Are we in a multi-line macro? This is the position of the macro's start
    in_macro = -1

    # Only ignore errors while in a #if 0 block.
    ignore_errors = False

    # keep track of which line we're on
    line = 1

    i = 0
    end = len(source)
    while i < end:
        # Skip whitespace if not in macro/comment.
        if in_comment == -1 and in_macro == -1:
            while i < end and source[i] == ' ' or source[i] == '\t' or source[i] == '\r':
                i += 1
            if i >= end:
                return

        token_type = UNKNOWN
        start = i
        c = source[i]
        if c == '\n':
            token_type = NEWLINE
            i += 1
        elif in_comment > -1:                      # Deal with being in multi-line comments (report each comment line)
            token_type = COMMENT
            while i < end and source[i] != '\n' and not (source[i] == '*' and source[i+1] == '/'):
                i += 1
            
            if i >= end:
                return

            if source[i] == '*' and source[i+1] == '/':
                in_comment = -1
                i += 2
        elif in_macro > -1:                        # Deal with being in macros (report each macro line)
            token_type = PREPROCESSOR
            while i < end and source[i] != '\n':
                i += 1
            
            if i >= end:
                return

            if source[i-1] != '\\' and source[i] == '\n':
                in_macro = -1
        elif c.isalpha() or c == '_':              # Find a string token.
            token_type = NAME
            while source[i] in valid_identifier_chars:
                i += 1
            # String and character constants can look like a name if
            # they are something like L"".
            if (source[i] == "'" and (i - start) == 1 and
                source[start:i] in 'uUL'):
                # u, U, and L are valid C++0x character preffixes.
                token_type = CONSTANT
                i = _GetChar(source, start, i)
            elif source[i] == "'" and source[start:i] in _STR_PREFIXES:
                token_type = CONSTANT
                i = _GetString(source, start, i)
        elif c == '/' and source[i+1] == '/':    # Find // comments.
            token_type = COMMENT
            i = source.find('\n', i)
            if i == -1:  # Handle EOF.
                i = end
        elif c == '/' and source[i+1] == '*':    # Find /* comments. */
            in_comment = i
            continue
        elif c in ':+-<>&|*=':                   # : or :: (plus other chars).
            token_type = SYNTAX
            i += 1
            new_ch = source[i]
            if new_ch == c:
                i += 1
            elif c == '-' and new_ch == '>':
                i += 1
            elif new_ch == '=':
                i += 1
        elif c in '()[]{}~!?^%;/.,@':             # Handle single char tokens (adding @ for obj-c/c++).
            token_type = SYNTAX
            i += 1
            if c == '.' and source[i].isdigit():
                token_type = CONSTANT
                i += 1
                while source[i] in int_or_float_digits:
                    i += 1
                # Handle float suffixes.
                for suffix in ('l', 'f'):
                    if suffix == source[i:i+1].lower():
                        i += 1
                        break
        elif c.isdigit():                        # Find integer.
            token_type = CONSTANT
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
            token_type = STRING
            i = _GetString(source, start, i)
        elif c == "'":                           # Find char.
            token_type = STRING
            i = _GetChar(source, start, i)
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
        if token_type == NEWLINE:
            line += 1

        # if this is a C++ keyword, change token type
        if token_type == NAME and source[start:i] in _keywords:
            token_type = KEYWORD

        yield Token(token_type, source[start:i], start, i, line)

def FormatSource(html_header, html_footer, dxr_db, srcroot, virtroot, tree, filepath, newroot):
    source = ReadFile(filepath)
    filename = os.path.basename(filepath)
    out = open(os.path.join(newroot, filename + '.html'), 'w')
    if not srcroot.endswith('/'):
        srcroot = srcroot + '/'
    srcpath = filepath.replace(srcroot, '')

    conn = sqlite3.connect(dxr_db)
    conn.execute('PRAGMA temp_store = MEMORY;')

    # Make temporary tables for all statements in this file to speed-up lookups
    conn.executescript('BEGIN TRANSACTION;' +
                       'CREATE TEMPORARY TABLE stmts_for_file(vfuncname, vshortname, vlocl);' + 
                       'INSERT INTO stmts_for_file SELECT vfuncname, vshortname, vlocl FROM stmts where vlocf="' + srcpath + '";' +
                       'CREATE INDEX idx_stmts_for_file ON stmts_for_file (vfuncname, vshortname, vlocl ASC);' +
                       'COMMIT;')

    conn.executescript('BEGIN TRANSACTION;' +
                       'CREATE TEMPORARY TABLE types_all (tname);' + 
                       'INSERT INTO types_all SELECT tname from types;' + # should ignore, but missing too many -- where not tignore = 1;' +
                       'INSERT INTO types_all SELECT ttypedefname from types;' + # where not tignore = 1;' +
                       'INSERT INTO types_all SELECT ttemplate from types;' + # where not tignore = 1;' +
                       'CREATE INDEX idx_types_all ON types_all (tname);' +
                       'COMMIT;')

    offset = 0       # offset is how much token.start/token.end are off due to extra html being added
    html = ''        # line after being made into html

    line_start = 0
    line = source[:source.find('\n')]
    line_num = 1

    # Fix-up virtroot in html header
    html_header = html_header.replace('$VIRTROOT', virtroot)
    out.write(html_header + '\n')

    # Add app config info
    out.write("""<script type="text/javascript">
// Config info used by dxr.js
virtroot="%s";
tree="%s";
</script>\n""" % (virtroot, tree))

    currentType = ''
    closeDiv = False
    # TODO: this ordering (by mdecl) is wrong (e.g., if you're in a file of defs) if you want file order
    for mdecls in conn.execute('select mtname, mtloc, mname, mdecl, mdef, mshortname from members where mdef like "' + 
                               srcpath + '%" or mdecl like "' + srcpath + '%" order by mtname, mdecl;').fetchall():
        if currentType != mdecls[0]:
            if closeDiv:
                out.write('</div><br />\n')

            currentType = mdecls[0]
            tname = mdecls[0]

            if mdecls[1] and mdecls[1].startswith(srcpath):
                p = mdecls[1].split(':')
                mtlocline = None
                # file scope statics have no type and use containing file for loc (no :line)
                if len(p) == 2:
                    mtlocline = p[1]
                else:
                    mtlocline = p[0]
                    
                # TODO: ugly hack, fix this      
                if tname == '[File Scope Static]':
                    tname = ''
                else:
                    tname = '<a class="sidebarlink" title="'+ mdecls[0] + '" href="#l' + mtlocline + '">' + mdecls[0] + '</a>'
            out.write("<b>" + tname + "</b>\n")
            out.write('<div>\n')
            closeDiv = True
                
        # TODO: is there a better way to deal with showing decl and/or def?
        # If decl + def are both in this file, or defn is, defn for text and decl for icon
        if ((mdecls[3] and mdecls[3].startswith(srcpath)) and (mdecls[4] and mdecls[4].startswith(srcpath))) or (mdecls[4] and mdecls[4].startswith(srcpath)):
            declparts = mdecls[3].split(':')
            out.write('<a title="Declaration: ' + mdecls[3] + '" href="' + virtroot + '/' + tree + '/' + declparts[0] + '.html#l' + declparts[1] + 
                      '"><img src="' + virtroot + '/' + 'images/icons/page_white_code.png" border="0" width="16" height="16"></a>\n')
            out.write('&nbsp;<a class="sidebarlink" title="' + mdecls[2] + ' [Definition]" href="#l' + mdecls[4].split(':')[1] + '">' + mdecls[5] + '</a><br />\n')
        else:
            if mdecls[4]:
                defparts = mdecls[4].split(':')
                out.write('<a title="Definition: ' + mdecls[4] + '" href="' + virtroot + '/' + tree + '/' + defparts[0] + '.html#l' + defparts[1] + 
                          '"><img src="' + virtroot + '/images/icons/page_white_wrench.png" border="0" width="16" height="16"></a>\n')
                out.write('&nbsp;<a class="sidebarlink" title="' + mdecls[2] + ' [Declaration]" href="#l' + mdecls[3].split(':')[1] + '">' + mdecls[5] + '</a><br />\n')
    if closeDiv:
        out.write('</div><br />\n')

    for extraTypes in conn.execute('select tname, tloc from types where tloc like "' + srcpath + 
                                   '%" and tname not in (select mtname from members where mdef like "' + srcpath + '%" or mdecl like "' + srcpath + 
                                   '%" order by mtname);').fetchall():
        out.write('<b><a class="sidebarlink" title="' + extraTypes[0] + '" href="#l' + extraTypes[1].split(':')[1] + '">' + extraTypes[0] + '</a></b><br /><br />\n')
        
# TODO: Need to figure out static funcs now that I changed how they are done in the db...
#        printFuncsHeader = True
#        printFuncsFooter = False
#        for staticFuncs in conn.execute('select fname, floc from funcs where floc like "' + srcpath + '%" order by floc;').fetchall():
#            if printFuncsHeader:
#                printFuncsHeader = False
#                printFuncsFooter = True
#                print('<b>File Scope Statics</b><br />')
#                print('<div style="padding-left:10px">')
#                
#            print('<a class="sidebarlink" title="' + staticFuncs[0] + '" href="#l' + staticFuncs[1].split(':')[1] + '">' + staticFuncs[0] + '</a><br />')
#        if printFuncsFooter:
#            print('</div><br />')

    out.write('</div>\n')
    out.write('<div id="maincontent" dojoType="dijit.layout.ContentPane" region="center" style="border:solid 1px #cccccc">\n')
    out.write('<pre>\n')
    out.write('<div id="ttd" style="display: none;" dojoType="dijit.TooltipDialog"></div>\n')

    for token in GetTokens(source):
        if token.token_type == NEWLINE:
            # See if there are any warnings for this line
            warningString = ''
            for warnings in conn.execute('select wmsg from warnings where wfile=? and wloc=?;', (srcpath, line_num)).fetchall():
                warningString += warnings[0] + '\n'

            if len(warningString) > 0:
                warningString = warningString[0:-1] # remove extra \n
                out.write('<div class="lnw" title="' + warningString + '" id="l' + `line_num` + '"><a class="ln" href="#l' + `line_num` + '">' + `line_num` + '</a>' + line + '</div>')
            else:
                out.write('<div id="l' + `line_num` + '"><a class="ln" href="#l' + `line_num` + '">' + `line_num` + '</a>' + line + '</div>')

            line_num += 1
            line_start = token.end
            offset = 0

            # Get next line
            eol = source.find('\n', line_start)
            if eol > -1:
                line = source[line_start:eol]

        else:
            if token.token_type == KEYWORD or token.token_type == STRING or token.token_type == COMMENT:
                start = token.start - line_start + offset
                end = token.end - line_start + offset

                if token.token_type == KEYWORD:
                    link = '<span class="k">' + token.name + '</span>'
                elif token.token_type == STRING:
                    link = '<span class="str">' + escape(token.name) + '</span>'
                else:
                    link = '<span class="c">' + escape(token.name) + '</span>'
                offset += len(link) - len(token.name)       # token is linkified, so update offset with new width
                line = line[:start] + link + line[end:]
            elif token.token_type == NAME:
                # Could be a macro, type, or statement
                prefix = ''
                suffix = '</a>'

                # Figure out which function we're in, and get the start/end line nums
                if conn.execute('select count(*) from macros where mshortname=?;', (token.name,)).fetchone()[0] > 0:
                    prefix = '<a class="m" aria-haspopup="true">'

                if prefix == '' and conn.execute('select count(*) from types_all where tname=?;', (token.name,)).fetchone()[0] > 0:
                    prefix = '<a class="t" aria-haspopup="true">'

                if prefix == '':
                    cur = conn.execute('select distinct vfuncname from stmts_for_file where vlocl<=? order by vlocl desc limit 1;', (line_num,)).fetchone()

                    if cur:
                        range = conn.execute('select min(vlocl), max(vlocl) from stmts_for_file where vfuncname=?;', (cur[0],)).fetchone()
                        # Now look for the token in that function, taking the line closest to the current line
                        # TODO: this is not totally accurate, since vshortname can happen in multiple cases (a->offset, g->b->offset)
                        hit = 0
                        for l in conn.execute('select distinct vlocl from stmts_for_file where vlocl>=? and vlocl<=? and vshortname=? order by vlocl', 
                                              (range[0], range[1], token.name)):
                            if abs(line_num - l[0]) < abs(line_num - hit):
                                hit = l[0]

                        if hit == line_num:
                            prefix = '<a class="s" aria-haspopup="true" line="' + `hit` + '" pos=' + `token.start` + '>'
                        elif hit != 0:  # fuzzy match, as long as hit isn't still at 0
                            prefix = '<a class="s-fuzzy" aria-haspopup="true" line="' + `hit` + '">'

                if prefix== '' and conn.execute('select count(*) from members where mshortname=?;', (token.name,)).fetchone()[0] > 0:
                    prefix = '<a class="mem" aria-haspopup="true" pos=' + `token.start` + '>'

                if prefix == '':      # we never found a match
                    # Don't bother making it a link
                    suffix = ''
                    prefix = ''

                start = token.start - line_start + offset
                end = token.end - line_start + offset
                link = prefix + escape(token.name) + suffix
                offset += len(link) - len(token.name)       # token is linkified, so update offset with new width
                line = line[:start] + link + line[end:]
            elif token.token_type == PREPROCESSOR:
                line = '<span class="p">' + escape(token.name) + '</span>'
                # Try to match header include filename: #include "nsPIDOMWindow.h"
                line = re.sub('#include "([^"]+)"', '#include "<a class="f">\g<1></a>"', line)
            elif token.token_type == SYNTAX or token.token_type == CONSTANT:
                continue
    out.write(html_footer + '\n')

def ReadFile(filename, print_error=True):
    """Returns the contents of a file."""
    try:
        fp = open(filename)
        try:
            return fp.read()
        finally:
            fp.close()
    except IOError:
        if print_error:
            print('Error reading %s: %s' % (filename, sys.exc_info()[1]))
        return None
