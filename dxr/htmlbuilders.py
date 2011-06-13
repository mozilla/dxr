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
    """Returns a list of (name, line, title, img, container) for items that
    belong in the sidebar."""
    return []

  def getSyntaxRegions(self):
    """Returns a list of (start, end+1, kind) tokens for syntax highlighting."""
    return []

  def getLinkRegions(self):
    """Returns a list of (start, end+1, {attr:val}) tokens for links."""
    return []

  def getLineAnnotations(self):
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
    out.write(self.html_header + '\n')
    self.writeSidebar(out)
    self.writeMainContent(out)
    self.writeGlobalScript(out)
    out.write(self.html_footer + '\n')
    out.close()

  def writeSidebar(self, out):
    sidebarElements = [x for x in self.collectSidebar()]
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
    out.write(self.html_main_header)
    self.writeMainBody(out)
    out.write(self.html_main_footer)

  def writeMainBody(self, out):
    syntax_regions = self.getSyntaxRegions()
    links = self.getLinkRegions()
    lines = self.getLineAnnotations()

    # Split up the entire source, and annotate each char invidually
    line_markers = [0]
    closure = ['', 0]
    def handle_char(x):
      if x == '\n':
        line_markers.append(closure[1])
      elif closure[0] == '\r':
        line_markers.append(closure[1] - 1)
      closure[0] = x
      closure[1] += 1
      if x == '\r' or x == '\n': return ''
      return cgi.escape(x)
    chars = [handle_char(x) for x in self.source]
    chars.append('')

    def off(val):
      if isinstance(val, tuple):
        return line_markers[val[0] - 1] + val[1]
      return val
    for syn in syntax_regions:
      chars[off(syn[0])] = '<span class="%s">%s' % (syn[2], chars[off(syn[0])])
      chars[off(syn[1]) - 1] += '</span>'
    for link in links:
      chars[off(link[0])] = '<a aria-haspopup="true" %s>%s' % (
        ' '.join([attr + '="' + str(link[2][attr]) + '"' for attr in link[2]]),
        chars[off(link[0])])
      chars[off(link[1]) - 1] += '</a>'

    # the hack is that we need the first and end to work better
    # The last "char" is the place holder for the first line entry
    line_markers[0] = -1
    # Line attributes
    for l in lines:
      chars[line_markers[l[0] - 1]] = \
        ' '.join([attr + '="' + str(l[1][attr]) + '"' for attr in l[1]])
    line_num = 2 # First line is special
    for ind in line_markers[1:]:
      chars[ind] = '</div><div %s id="l%d"><a class="ln" href="l%d">%d</a>' % \
        (chars[ind], line_num, line_num, line_num)
      line_num += 1
    out.write('<div %s id="l1"><a class="ln" href="l1">1</a>' % chars[-1])
    chars[-1] = '</div>'
    out.write(''.join(chars))

  def writeGlobalScript(self, out):
    """ Write any extra JS for the page. Lines of script are stored in self.globalScript."""
    # Add app config info
    out.write('<script type="text/javascript">')
    out.write('\n'.join(self.globalScript))
    out.write('</script>')


class CppHtmlBuilder(HtmlBuilderBase):
  def __init__(self, dxrconfig, treeconfig, filepath, newroot, blob):
    HtmlBuilderBase.__init__(self, dxrconfig, treeconfig, filepath, newroot)
    self.syntax_regions = None
    self.lines = None
    self.blob_file = blob["byfile"].get(self.srcpath, None)
    self.blob = blob

  def _createTokenizer(self):
    return CppTokenizer(self.source)

  def collectSidebar(self):
    if self.blob_file is None:
      return
    lst = []
    def line(linestr):
      return linestr.split(':')[1]
    def make_tuple(df, name, loc, scope="scopeid"):
      img = 'images/icons/page_white_wrench.png'
      if scope in df:
        return (df[name], df[loc].split(':')[1], img,
          self.blob["scopes"][df[scope]]["sname"])
      return (df[name], df[loc].split(':')[1], img)
    for df in self.blob_file["types"]:
      yield make_tuple(df, "tname", "tloc")
    for df in self.blob_file["functions"]:
      yield make_tuple(df, "flongname", "floc", "scopeid")
    for df in self.blob_file["variables"]:
      if "scopeid" in df: #XXX only kill local vars
        continue
      yield make_tuple(df, "vname", "vloc", "scopeid")

  def _getFromTokenizer(self):
    syntax_regions = []
    lines = []
    line_num = 1
    for token in self.tokenizer.getTokens():
      if token.token_type == self.tokenizer.NEWLINE:
        #warningString = '\n'.join([warnings[0] for warnings in
        #  self.conn.execute('select wmsg from warnings where wfile=? and wloc=?;',
        #                  (self.srcpath, line_num)).fetchall()])
        #if len(warningString) > 0:
        #  lines.append((line_num, {'class': "lnw", 'title': warningString}))
        line_num += 1
      elif token.token_type == self.tokenizer.KEYWORD:
        syntax_regions.append((token.start, token.end, 'k'))
      elif token.token_type == self.tokenizer.STRING:
        syntax_regions.append((token.start, token.end, 'str'))
      elif token.token_type == self.tokenizer.COMMENT:
        syntax_regions.append((token.start, token.end, 'c'))
      elif token.token_type == self.tokenizer.PREPROCESSOR:
        syntax_regions.append((token.start, token.end, 'p'))
    self.syntax_regions = syntax_regions
    self.lines = lines

  def getSyntaxRegions(self):
    if self.syntax_regions is None:
      self._getFromTokenizer()
    return self.syntax_regions

  def getLinkRegions(self):
    if self.blob_file is None:
      return
    def make_link(obj, loc, name, clazz):
      line, col = obj[loc].split(':')[1:]
      line, col = int(line), int(col)
      return ((line, col), (line, col + len(obj[name])),
        {'class': clazz, 'line': line})
    for df in self.blob_file["variables"]:
      yield make_link(df, 'vloc', 'vname', 's')
    for df in self.blob_file["functions"]:
      yield make_link(df, 'floc', 'fname', 'func')
    for df in self.blob_file["types"]:
      yield make_link(df, 'tloc', 'tname', 't')
    for df in self.blob_file["refs"]:
      start, end = df["extent"].split(':')
      line = df["refloc"].split(':')[1]
      yield (int(start), int(end), {'class': 'ref', 'line': int(line)})

  def getLineAnnotations(self):
    if self.lines is None:
      self._getFromTokenizer()
    return self.lines


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
