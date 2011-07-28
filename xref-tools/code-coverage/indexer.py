import dxr.plugins
import os

''' A DXR plugin that can highlight code-coverage lines.

    For the time being, the tool expects the file to be the results of running
    lcov in a result app.info in the root of the build directory; I don't want
    to play around with reading output from gcov or from .gcno/.gcda files
    manually. The upside of this approach is it allows you to run gcov from
    other machines. '''

def read_file(fd, path, filestruct):
  lines = filestruct.setdefault('lines', {})
  for line in fd:
    line = line.strip()
    if line == 'end_of_record':
      return
    instr, data = line.split(':')
    if instr == 'DA': # DA:<line number>,<execution count>[,<checksum>]
      data = data.split(',')
      lno, hits = int(data[0]), int(data[1])
      lines[lno] = lines.get(lno, 0) + hits
    elif instr in ['LH', 'LF']: # Hit/found -> we count these ourselves
      continue

def read_lcov(fd):
  all_data = {}
  for line in fd:
    line = line.strip()
    instr, data = line.split(':')
    if instr == 'TN': # TN:<test name>
      continue
    elif instr == 'SF': # SF:<absolute path to the source file>
      read_file(fd, data, all_data.setdefault(data, {}))
  return all_data

def post_process(srcdir, objdir):
  try:
    appinfo = open(os.path.join(objdir, "app.info"))
  except IOError:
    # No file? No gcov
    return {}
  try:
    blob = read_lcov(appinfo)
  finally:
    appinfo.close()

  return blob

def can_use(treecfg):
  # We need to have clang and llvm-config in the path
  return dxr.plugins.in_path('lcov')

def get_schema():
  return ''
sqlify = dxr.plugins.default_sqlify
pre_html_process = dxr.plugins.default_pre_html_process

def get_line_annotations(blob, srcpath, treecfg):
  if srcpath in blob and 'lines' in blob[srcpath]:
    for line, hits in blob[srcpath]['lines'].iteritems():
      yield (line, { "data-gcov-hits": str(hits) })

htmlifier = {}
for f in ('.c', '.cc', '.cpp', '.h', '.hpp'):
  htmlifier[f] = {
    'get_line_annotations': get_line_annotations,
    'no-override': True
  }

def get_htmlifiers():
  return htmlifier

__all__ = dxr.plugins.required_exports()
