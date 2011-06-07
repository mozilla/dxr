#!/usr/bin/env python2.6

import sys
import os
import re
import sqlite3
import template
import cgi
from tokenizers import Token, BaseTokenizer, CppTokenizer, IdlTokenizer

class HtmlBuilderBase:
    def _init_db(self, database):
        self.conn = sqlite3.connect(database)
        self.conn.execute('PRAGMA temp_store = MEMORY;')

    def __init__(self, dxrconfig, treeconfig, filepath, newroot):
        # Read and expand all templates
        self.html_header = template.expand(template.readFile(dxrconfig["html_header"]),
                                           dxrconfig["virtroot"], treeconfig["tree"])
        self.html_footer = template.expand(template.readFile(dxrconfig["html_footer"]),
                                           dxrconfig["virtroot"], treeconfig["tree"])
        self.html_sidebar_header = template.expand(template.readFile(dxrconfig["html_sidebar_header"]),
                                                   dxrconfig["virtroot"], treeconfig["tree"])
        self.html_sidebar_footer = template.expand(template.readFile(dxrconfig["html_sidebar_footer"]),
                                                   dxrconfig["virtroot"], treeconfig["tree"])
        self.html_main_header = template.expand(template.readFile(dxrconfig["html_main_header"]),
                                                dxrconfig["virtroot"], treeconfig["tree"])
        self.html_main_footer = template.expand(template.readFile(dxrconfig["html_main_footer"]),
                                                dxrconfig["virtroot"], treeconfig["tree"])
        
        self.source = template.readFile(filepath)
        self.virtroot = dxrconfig["virtroot"]
        self.treename = treeconfig["tree"]
        self.filename = os.path.basename(filepath)
        self.srcroot = treeconfig["sourcedir"]
        self.newroot = os.path.normpath(newroot)
        self.srcpath = filepath.replace(self.srcroot + '/', '')

        self._init_db(dxrconfig["database"])
        self.tokenizer = self._createTokenizer()

        # Config info used by dxr.js
        self.globalScript = ['var virtroot = "%s", tree = "%s";' % (self.virtroot, self.treename)]

    def _createTokenizer(self):
        return BaseTokenizer(self.source)

    def _buildFullPath(self, ending, includeTreename=True):
        if includeTreename:
            return os.path.join(self.virtroot, self.treename, ending) 
        else:
            return os.path.join(self.virtroot, ending) 

    def escapeString(self, token, line, line_start, offset, prefix='', suffix=''):
        start = token.start - line_start + offset
        end = token.end - line_start + offset
        escaped = prefix + cgi.escape(token.name) + suffix
        # token is (perhaps) different size, so update offset with new width
        offset += len(escaped) - len(token.name)
        line = line[:start] + escaped + line[end:]

        return (offset, line)

    def toHTML(self, skipSidebar=True):
        out = open(os.path.join(self.newroot, self.filename + '.html'), 'w')
        self.writeHeader(out)
        self.writeSidebar(out, skipSidebar)
        self.writeMainContent(out)
        self.writeGlobalScript(out)
        self.writeFooter(out)
        out.close()

    def writeHeader(self, out):
        out.write(self.html_header + '\n')

    def writeSidebar(self, out, skipSidebar):
        if skipSidebar: return

        self.writeSidebarHeader(out)
        self.writeSidebarBody(out)
        self.writeSidebarFooter(out)

    def writeSidebarHeader(self, out):
        out.write(self.html_sidebar_header + '\n')

    def writeSidebarBody(self, out):
        pass

    def writeSidebarFooter(self, out):
        out.write(self.html_sidebar_footer + '\n')

    def writeMainContent(self, out):
        self.writeMainHeader(out)
        self.writeMainBody(out)
        self.writeMainFooter(out)

    def writeMainHeader(self, out):
        out.write(self.html_main_header + '\n')

    def writeMainBody(self, out):
        # offset is how much token.start/token.end are off due to extra html being added
        offset = 0
        line_start = 0
        line = self.source[:self.source.find('\n')]
        line_num = 1

        for token in self.tokenizer.getTokens():
            if token.token_type == self.tokenizer.NEWLINE:
                out.write('<div id="l%s"><a href="#l%s" class="ln">%s</a>%s</div>' % 
                          (`line_num`, `line_num`, `line_num`, line))

                line_num += 1
                line_start = token.end
                offset = 0

                # Get next line
                eol = self.source.find('\n', line_start)
                if eol > -1:
                    line = self.source[line_start:eol]

            else:
                offset, line = self.escapeString(token, line, line_start, offset)

    def writeMainFooter(self, out):
        out.write(self.html_main_footer + '\n')

    def writeGlobalScript(self, out):
        """ Write any extra JS for the page. Lines of script are stored in self.globalScript."""
        # Add app config info
        out.write('<script type="text/javascript">')
        out.write('\n'.join(self.globalScript))
        out.write('</script>')

    def writeFooter(self, out):
        out.write(self.html_footer + '\n')


class HtmlBuilderSidebar(HtmlBuilderBase):
    """ HtmlBuilder that prints the sidebar. """

    def __init__(self, dxrconfig, treeconfig, filepath, newroot):
        HtmlBuilderBase.__init__(self, dxrconfig, treeconfig, filepath, newroot)

    def toHTML(self):
        """Override so we don't skip the sidebar."""
        HtmlBuilderBase.toHTML(self, False)


class CppHtmlBuilder(HtmlBuilderSidebar):
    def __init__(self, dxrconfig, treeconfig, filepath, newroot):
        HtmlBuilderSidebar.__init__(self, dxrconfig, treeconfig, filepath, newroot)
        # Build up the temporary table for all declarations in the file
        # XXX: this includes local variables which is ... sub optimal, I think.
        # Maybe not?
        self.conn.executescript('''BEGIN TRANSACTION;
            CREATE TEMPORARY TABLE file_defs (name, scopeid, loc);
            INSERT INTO file_defs SELECT tname, 0, tloc FROM types;
            INSERT INTO file_defs SELECT flongname, scopeid, floc FROM functions;
            INSERT INTO file_defs SELECT vname, scopeid, vloc FROM variables
                WHERE scopeid <= 0;
            DELETE FROM file_defs WHERE loc NOT LIKE '%s:%%';
            COMMIT;''' % (self.srcpath))
        self.conn.executescript('BEGIN TRANSACTION;' +
                                'CREATE TEMPORARY TABLE types_all (tname);' + 
                                'INSERT INTO types_all SELECT tname from types;' + # should ignore -- where not tignore = 1;' +
                                'INSERT INTO types_all SELECT ttypedefname from types;' + # where not tignore = 1;' +
                                'INSERT INTO types_all SELECT ttemplate from types;' + # where not tignore = 1;' +
                                'CREATE INDEX idx_types_all ON types_all (tname);' +
                                'COMMIT;')

    def _createTokenizer(self):
        return CppTokenizer(self.source)


    def getMemberRange(self, func, sid, loc):
        pass
        #lineRange = self.conn.execute("select min(vlocl), max(vlocl) from stmts_for_file where vfuncname=?;",
        #                              (func,)).fetchone()
        #if lineRange and lineRange[0] and lineRange[1]:
        #    self.globalScript.append('this.ranges.push({start: %s, end: %s, sid: "%s", sig:"%s", loc: %s});' % 
        #                             (lineRange[0], lineRange[1], sid, cgi.escape(func), loc.split(':')[1]))

    def buildSidebarLink(self, loc, mname, anchor, mshortname, sid, isDeclaration):
      img = None
      title1 = None
      title2 = None
      parts = loc.split(':') # split path/filename:loc

      # Add extra title info depending on whether this is a decl/def
      if isDeclaration:
          title1 = 'Go to Declaration: ' + loc
          title2 = mname + ' [Definition]'
          img = self._buildFullPath('images/icons/page_white_code.png', False)
      else:
          title1 = 'Go to Definition: ' + loc
          title2 = mname + ' [Declaration]'
          img = self._buildFullPath('images/icons/page_white_wrench.png', False)

      return ('<a title="%s" href="%s"><img src="%s" class="sidebarimage"></a>' \
              '<a id="%s" class="sidebarlink" title="%s" href="#l%s">%s</a><br />\n' %
              (title1, self._buildFullPath(parts[0] + '.html#l' + parts[1]), img, sid,
               title2, anchor, cgi.escape(mshortname)))

    def writeSidebarBody(self, out):
        srcpath = self.srcpath
        currentScope = ''
        closeDiv = False
        sid = 0

        # We'll keep track of member loc ranges in the file
        self.globalScript.append('this.ranges = [];')

        for defs in self.conn.execute('SELECT name, sname, sloc, loc ' +
                'FROM file_defs LEFT JOIN scopes USING (scopeid) ' +
                'ORDER BY sname, loc').fetchall():
            sid += 1
            # If we are in a class
            if currentScope != defs[1] and defs[1] is not None:
                if closeDiv:
                    out.write('</div><br />\n')

                currentScope = defs[1]
                scopename = defs[1]

                # If the scope itself is defined here, make that link
                if defs[2] and defs[2].startswith(srcpath + ':'):
                    scopeline = defs[2].split(':')[1]
                    scopename = '<a class="sidebarlink" title="%s" href="#l%s">%s</a>' % \
                        (scopename, scopeline, cgi.escape(scopename))

                out.write("<b>%s</b>\n" % scopename)
                out.write('<div>\n')
                closeDiv = True

            # Output the link for this sidebar
            sidText = 'sid-' + `sid`
            shortname = defs[0]
            if defs[1] and shortname.startswith(defs[1] + '::'):
                # If our scope has a name, remove that portion plus the ::
                shortname = shortname[len(defs[1]) + 2:]
            out.write(self.buildSidebarLink(defs[3], defs[0], \
                defs[3].split(':')[1], shortname, sidText, False))
            self.getMemberRange(defs[0], sidText, defs[3])

        if closeDiv:
            out.write('</div><br />\n')

        #for extraTypes in self.conn.execute('select tname, tloc from types where tloc like "' + srcpath + 
        #                                    '%" and tname not in (select mtname from members where mdef like "' + srcpath +
        #                                    '%" or mdecl like "' + srcpath + '%" order by mtname);').fetchall():
        #    out.write('<b><a class="sidebarlink" title="%s" href="#l%s">%s</a></b><br /><br />\n' %
        #              (extraTypes[0], extraTypes[1].split(':')[1], cgi.escape(extraTypes[0])))

        # Sort the range lines so lookups are faster
        self.globalScript.append('this.ranges.sort(function(x,y) { return x.start - y.start; });')

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

    def writeMainBody(self, out):
        offset = 0
        line_start = 0
        line = self.source[:self.source.find('\n')]
        line_num = 1

        for token in self.tokenizer.getTokens():
            if token.token_type == self.tokenizer.NEWLINE:
                # See if there are any warnings for this line
                warningString = ''
                for warnings in self.conn.execute('select wmsg from warnings where wfile=? and wloc=?;',
                                                  (self.srcpath, line_num)).fetchall():
                    warningString += warnings[0] + '\n'

                if len(warningString) > 0:
                    warningString = warningString[0:-1] # remove extra \n
                    out.write('<div class="lnw" title="%s" id="l%s"><a class="ln" href="#l%s">%s</a>%s</div>' %
                              (warningString, `line_num`, `line_num`, `line_num`, line))
                else:
                    out.write('<div id="l%s"><a class="ln" href="#l%s">%s</a>%s</div>' % 
                              (`line_num`, `line_num`, `line_num`, line))

                line_num += 1
                line_start = token.end
                offset = 0

                # Get next line
                eol = self.source.find('\n', line_start)
                if eol > -1:
                    line = self.source[line_start:eol]

            else:
                if token.token_type == self.tokenizer.KEYWORD or token.token_type == self.tokenizer.STRING \
                        or token.token_type == self.tokenizer.COMMENT:
                    prefix = None
                    suffix = '</span>'

                    if token.token_type == self.tokenizer.KEYWORD:
                        prefix = '<span class="k">'
                    elif token.token_type == self.tokenizer.STRING:
                        prefix = '<span class="str">'
                    else:
                        prefix = '<span class="c">'

                    offset, line = self.escapeString(token, line, line_start, offset, prefix, suffix)
                elif token.token_type == self.tokenizer.NAME:
                    # Could be a macro, type, or statement
                    prefix = ''
                    suffix = '</a>'

                    # Figure out which function we're in, and get the start/end line nums
                    if self.conn.execute('select count(*) from macros where mshortname=?;',
                                         (token.name,)).fetchone()[0] > 0:
                        prefix = '<a class="m" aria-haspopup="true">'

                    if prefix == '' and self.conn.execute('select count(*) from types_all where tname=?;',
                                                          (token.name,)).fetchone()[0] > 0:
                        prefix = '<a class="t" aria-haspopup="true">'

                    if prefix == '' and self.conn.execute('select count(*) from functions where fname=?',
                                                          (token.name,)).fetchone()[0] > 0:
                        prefix = '<a class="func" aria-haspopup=true" pos=%s>' % `token.start`

                    if prefix == '' and self.conn.execute('select count(*) from variables where vname=? and vloc=?',
                                                          (token.name,self.srcpath+':'+line)).fetchone()[0] > 0:
                        prefix = '<a class="s" aria-haspopup="true" line="%s" pos=%s>' % (`line`, `token.start`)

                    # XXX: too slow
                    #if prefix == '' and self.conn.execute('select count(*) from refs where reff=? and refl=? and refc=?',
                    #        (self.srcpath, line, token.start)).fetchone()[0] > 0:
                    #    prefix = '<a class="s" aria-haspopup="true" line="%s" pos="%s">' % (`line`, `token.start`)

                    if prefix == '':      # we never found a match
                        # Don't bother making it a link
                        suffix = ''
                        prefix = ''

                    offset, line = self.escapeString(token, line, line_start, offset, prefix, suffix)
                elif token.token_type == self.tokenizer.PREPROCESSOR:
                    line = '<span class="p">%s</span>' % cgi.escape(token.name)
                    # Try to match header include filename: #include "nsPIDOMWindow.h"
                    line = re.sub('#include "([^"]+)"', '#include "<a class="f">\g<1></a>"', line)
                elif token.token_type == self.tokenizer.SYNTAX or token.token_type == self.tokenizer.CONSTANT:
                    offset, line = self.escapeString(token, line, line_start, offset)

class IdlHtmlBuilder(HtmlBuilderSidebar):
    def __init__(self, dxrconfig, treeconfig, filepath, newroot):
        HtmlBuilderSidebar.__init__(self, dxrconfig, treeconfig, filepath, newroot)

    def _createTokenizer(self):
        return IdlTokenizer(self.source)
    
    def writeSidebarBody(self, out):
        currentType = ''
        closeDiv = False
        srcpath = self.srcpath
        for mdecls in self.conn.execute('select mtname, mtloc, mname, mdecl, mshortname from members where mdecl like "' +
                                        srcpath + '%" order by mtname, mdecl;').fetchall():
            if currentType != mdecls[0]:
                if closeDiv:
                    out.write('</div><br />\n')

                currentType = mdecls[0]
                tname = mdecls[0]
                if mdecls[1] and mdecls[1].startswith(srcpath):
                    mtlocline = mdecls[1].split(':')[1]
                    tname = '<a class="sidebarlink" href="#l%s">%s</a>' % (mtlocline, mdecls[0])
                out.write("<b>%s</b>\n" % tname)
                out.write('<div style="padding-left:16px">\n')
                closeDiv = True

            if mdecls[3]: # mdecl
                out.write('&nbsp;<a class="sidebarlink" title="%s [Definition]" href="#l%s">%s</a><br />\n' % 
                          (mdecls[2], mdecls[3].split(':')[1], mdecls[4]))

        if closeDiv:
            out.write('</div><br />\n')

        for extraTypes in self.conn.execute('select tname, tloc from types where tloc like "' + srcpath + 
                                       '%" and tname not in (select mtname from members where mdef like "' + srcpath + 
                                       '%" or mdecl like "' + srcpath + '%" order by mtname);').fetchall():
            out.write('<b><a class="sidebarlink" href="#l%s">%s</a></b><br /><br />\n' %
                       (extraTypes[1].split(':')[1], extraTypes[0]))

    def writeMainBody(self, out):
        offset = 0       # offset is how much token.start/token.end are off due to extra html being added
        line_start = 0
        line = self.source[:self.source.find('\n')]
        line_num = 1

        for token in self.tokenizer.getTokens():
            if token.token_type == self.tokenizer.NEWLINE:
                out.write('<div id="l' + `line_num` + '"><a href="#l' + `line_num` + '" class="ln">' +
                          `line_num` + '</a>' + line + '</div>')
                line_num += 1
                line_start = token.end
                offset = 0

                # Get next line
                eol = self.source.find('\n', line_start)
                if eol > -1:
                    line = self.source[line_start:eol]

            else:
                if token.token_type == self.tokenizer.KEYWORD or token.token_type == self.tokenizer.STRING \
                        or token.token_type == self.tokenizer.COMMENT:
                    prefix = None
                    suffix = '</span>'

                    if token.token_type == self.tokenizer.KEYWORD:
                        prefix = '<span class="k">'
                    elif token.token_type == self.tokenizer.STRING:
                        prefix = '<span class="str">'
                    else:
                        prefix = '<span class="c">'

                    offset, line = self.escapeString(token, line, line_start, offset, prefix, suffix)

                elif token.token_type == self.tokenizer.SYNTAX or token.token_type == self.tokenizer.CONSTANT:
                    offset, line = self.escapeString(token, line, line_start, offset)
                else:
                    prefix = None
                    suffix = None

                    if token.token_type == self.tokenizer.KEYWORD:
                        prefix = '<span class="k">'
                        suffix = '</span>'
                    elif token.token_type == self.tokenizer.NAME:
                        prefix = ''
                        suffix = ''
                    else:
                        prefix = '<span class="p">'
                        suffix = '</span>'

                    offset, line = self.escapeString(token, line, line_start, offset, prefix, suffix)
