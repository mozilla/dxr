import cgi, sys, re

def like_escape(val):
  return '%' + val.replace("\\", "\\\\").replace("_", "\\_") \
    .replace("%", "\\%") + '%'


def processString(queries, tree, conn, string, path=None, ext=None, regexp=None):
  string = string.strip()
  vrootfix = ""
  if vrootfix == '/':
    vrootfix = ''
  if ext is not None and ext[0] == '.':
    ext = ext[1:]
  def printSidebarResults(name, results):
    outputtedResults = False
    for res in results:
      # Make sure we're not matching part of the scope
      colon = res[0].rfind(':')
      if colon != -1 and res[0].lower()[colon:].find(string.lower()) == -1:
        continue
      if path and path.lower() != res[1].lower():
        continue
      if not outputtedResults:
        outputtedResults = True
        print '<div class="bubble"><span class="title">%s</span><ul>' % name
      print '<li><a href="%s/%s/%s#l%d">%s</a></li>' % \
        (vrootfix, tree, res[1], res[2], res[0])
    if outputtedResults:
      print '</ul></div>'


  # Print smart sidebar
  print '<div id="sidebar">'
  config = [
    ('types', ['tname']),
    ('macros', ['macroname']),
    ('functions', ['fqualname', 'fname']),
    ('variables', ['vname']),
  ]
  for table, cols in config:
    results = []
    if len(cols) > 1:
      search_col = cols[1]
    else:
      search_col = cols[0]

    for row in conn.execute('SELECT %s , (SELECT path FROM files WHERE files.ID = %s.file_id), file_line, file_col FROM %s WHERE %s LIKE ? ESCAPE "\\";' % (
        cols[0], table, table, search_col), (like_escape(string),)).fetchall():
      results.append((row[0], row[1], row[2], row[3]))
    printSidebarResults(str.capitalize(table), results)

  # Print file sidebar
  printHeader = True

  for row in queries.getFileMatches(conn, string):
    if printHeader:
      print '<div class=bubble><span class="title">Files</span><ul>'
      printHeader = False
    filename = vrootfix + '/' + tree + '/' + row[0]
    print '<li><a href="%s">%s</a></li>' % (filename, row[1])

  if not printHeader:
    print "</ul></div>"

  print '</div><div id="content">'

  # Text search results
  first = True
  prevpath = None

  if regexp is None:
    matches = queries.getFTSMatches(conn, string, path, ext)
  else:
    matches = queries.getRegexMatches(conn, string, path, ext)

  for row in matches:
    if first:
      first = False

    if prevpath is None or prevpath != row[0]:
      if prevpath is not None:
        print '</ul>'
      print '<div class="searchfile"><a href="%s/%s/%s">%s</a></div><ul class="searchresults">' % (vrootfix, tree, row[0], row[0])

    line_str = cgi.escape(row[2])
    line_str = re.sub(r'(?i)(' + re.escape(string) + ')', '<b>\\1</b>', line_str)
    print '<li class="searchresult"><a href="%s/%s/%s#l%s">%s:</a>&nbsp;&nbsp;%s</li>' % (vrootfix, tree, row[0], row[1] + 1, row[1] + 1, line_str)
    prevpath = row[0]


  if first is True:
    print '<p>No files match your search parameters.</p>'
  else:
    print '</ul>'
