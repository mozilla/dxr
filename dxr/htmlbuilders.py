#!/usr/bin/env python2.6

import sys
import os
import re
import sqlite3
import template
import cgi
from tokenizers import Token, BaseTokenizer, CppTokenizer, IdlTokenizer

class HtmlBuilderBase:
  def collectSidebar(self):
    """ Returns a list of (name, line, title, img, container) for items that
    belong in the sidebar."""
    return []

  def _init_db(self, database):
    self.conn = sqlite3.connect(database)
    self.conn.execute('PRAGMA temp_store = MEMORY;')

  def __init__(self, dxrconfig, treeconfig, filepath, newroot):
    # Read and expand all templates
    def read_template(prop):
      return template.expand(template.readFile(dxrconfig[prop]),
        dxrconfig["virtroot"], treeconfig["tree"])
    self.html_header = read_template("html_header")
    self.html_footer = read_template("html_footer")
    self.html_sidebar_header = read_template("html_sidebar_header")
    self.html_sidebar_footer = read_template("html_sidebar_footer")
    self.html_main_header = read_template("html_main_header")
    self.html_main_footer = read_template("html_main_footer")
    
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

  def toHTML(self):
    out = open(os.path.join(self.newroot, self.filename + '.html'), 'w')
    self.writeHeader(out)
    self.writeSidebar(out)
    self.writeMainContent(out)
    self.writeGlobalScript(out)
    self.writeFooter(out)
    out.close()

  def writeHeader(self, out):
    out.write(self.html_header + '\n')

  def writeSidebar(self, out):
    sidebarElements = self.collectSidebar()
    if len(sidebarElements) == 0: return

    out.write(self.html_sidebar_header + '\n')
    self.writeSidebarBody(out, sidebarElements)
    out.write(self.html_sidebar_footer + '\n')

  def writeSidebarBody(self, out, elements):
    containers = {}
    for e in elements:
      containers.setdefault(len(e) > 4 and e[4] or None, []).append(e)

    for cont in containers:
      if cont is not None:
        out.write('<b>%s</b>\n<div>\n' % str(cont))
      containers[cont].sort(lambda x, y: int(x[1]) - int(y[1]))
      for e in containers[cont]:
        img = len(e) > 3 and e[3] or "images/icons/page_white_code.png"
        title = len(e) > 2 and e[2] or e[0]
        img = self._buildFullPath(img)
        out.write('<img src="%s" class="sidebarimage">' % (img))
        out.write('<a class="sidebarlink" title="%s" href="#l%d">%s</a><br>\n' %
          (title, int(e[1]), e[0]))
      if cont is not None:
        out.write('</div><br />\n')

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


class CppHtmlBuilder(HtmlBuilderBase):
  def __init__(self, dxrconfig, treeconfig, filepath, newroot, ball):
    HtmlBuilderBase.__init__(self, dxrconfig, treeconfig, filepath, newroot)
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


  def collectSidebar(self):
    lst = []
    for df in self.conn.execute('SELECT name, sname, sloc, loc ' +
        'FROM file_defs LEFT JOIN scopes USING (scopeid)').fetchall():
      line = df[3].split(':')[1]
      if df[1] is None:
        e = (df[0], line, df[0], 'images/icons/page_white_wrench.png')
      else:
        e = (df[0], line, df[0], 'images/icons/page_white_wrench.png', df[1])
      lst.append(e)
    return lst

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
          #    (self.srcpath, line, token.start)).fetchone()[0] > 0:
          #  prefix = '<a class="s" aria-haspopup="true" line="%s" pos="%s">' % (`line`, `token.start`)

          if prefix == '':    # we never found a match
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

class IdlHtmlBuilder(HtmlBuilderBase):
  def __init__(self, dxrconfig, treeconfig, filepath, newroot):
    HtmlBuilderBase.__init__(self, dxrconfig, treeconfig, filepath, newroot)

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
    offset = 0     # offset is how much token.start/token.end are off due to extra html being added
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
