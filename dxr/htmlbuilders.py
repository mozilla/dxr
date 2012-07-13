#!/usr/bin/env python2

import os
import dxr
import cgi
import itertools
import sys
import subprocess
import re
import codecs

def build_html(dxrconfig, treecfg, filepath, dstpath, _zipper):
  # Make arguments
  arguments = {}
  # Set common template variables
  arguments["wwwroot"]    = treecfg.virtroot
  arguments["tree"]       = treecfg.tree
  arguments["trees"]      = [treecfg.tree for tcfg in dxrconfig.trees]
  # Set file template variables
  arguments["path"]       = filepath.replace(treecfg.sourcedir + '/', '')
  arguments["revision"]   = get_revision(treecfg)
  arguments["lines"]      = build_content(treecfg, filepath, _zipper)
  arguments["sections"]   = build_sections(treecfg, filepath, _zipper)
  arguments["generated"]  = False  #TODO: Figure out when/if a file is generated
  #for nb, line, notes in build_content(treecfg, filepath, _zipper):
  #  print >> sys.stderr, "%3i: %r" % (nb, line)
  # Build and dump template
  treecfg.getTemplate("file.html").stream(**arguments).dump(dstpath, encoding = "utf-8")

_http_pattern = re.compile("^[A-Za-z0-9]+://.*")
def build_content(treecfg, filepath, _zipper):
  # Read source from disk
  try:
    #with codecs.open(filepath, encoding = "utf-8") as f:
    with open(filepath) as f:
      source = f.read()
  except:
    print "ERROR, Failed to read source file: %s" % filepath
    return ""

  # Empty files, have no lines
  if len(source) == 0:
    return []

  # Get a decoder
  decoder = codecs.getdecoder("utf-8")
  # Let's defined a simple way to fetch and decode a slice of source
  def src(start, end = None):
    if isinstance(start, tuple):
      start, end = start[:2]
    return decoder(source[start:end], errors="strict")[0]  #TODO After testing make it replace!
  # We shall decode on-the-fly because we need ascii offsets to do the rendering
  # of regions correctly. But before we stuff anything into the template engine
  # we must ensure that it's correct utf-8 encoded string
  # Yes, we just have to hope that plugin designer don't give us a region that
  # splits a unicode character in two. But what else can we do?
  # (Unless we want to make plugins deal with this mess)

  # Build a line map over the source (without exploding it all over the place!)
  line_map = [0]
  offset = source.find("\n", 0) + 1
  while offset > 0:
    line_map.append(offset)
    offset = source.find("\n", offset) + 1
  # If we don't have a line ending at the end improvise one
  if not source.endswith("\n"):
    line_map.append(len(source))

  # So, we have a minor issue with writing out the main body. Some of our
  # information is (line, col) information and others is file offset. Also,
  # we don't necessarily have the information in sorted order.
  syntax_regions = _zipper("get_syntax_regions")     # start, end, class
  link_regions   = _zipper("get_link_regions")       # start, end, dict (should be set a attribute on the link)
  line_notes     = _zipper("get_line_annotations")   # line, dict (should be set as attributes on the line number)

  # Quickly sort the line annotations in reverse order
  # so we can view it as a stack we just pop annotations off as we generate lines
  line_notes     = sorted(line_notes, reverse = True)

  # start and end, may be either a number (extent) or a tuple of (line, col)
  # we shall normalize this, and sort according to extent
  # This is the fastest way to apply everything, exploding source into an array of chars is a bad way!
  def normalize(region):
    start, end, data = region
    if isinstance(start, tuple):
      line1, col1 = start
      line2, col2 = end
      return (line_map[line1 - 1] + col1 - 1, line_map[line2 - 1] + col2 - 1, data)
    return region
  # Add sanitizer to remove regions that have None as offsets
  # They are just stupid and shouldn't be there in the first place!
  sane_region     = lambda (start, end, data): start is not None and end is not None
  syntax_regions  = (normalize(region) for region in syntax_regions if sane_region(region))
  link_regions    = (normalize(region) for region in link_regions if sane_region(region))
  # That's it we've normalized this mess, so let's just sort it too
  cmp_region      = lambda (start, end, data): (-start, end, data)
  syntax_regions  = sorted(syntax_regions, key = cmp_region)
  link_regions    = sorted(link_regions, key = cmp_region)
  # Notice that we negate start, larges start first and ties resolved with smallest end.
  # This way be can pop values of the regions in the order they occur...

  # Now we create two stacks to keep track of open regions
  syntax_regions_stack  = []
  link_regions_stack    = []

  # Open close link regions, quite simple
  def open_link_region(region):
    start, end, data = region
    # href isn't fully qualified, set it under the tree
    if "href" in data and not _http_pattern.match(data["href"]):
      href = treecfg.virtroot + "/" + treecfg.tree + "/" + data["href"]
    # If no href make one to a search for the string
    if "href" not in data:
      href = treecfg.virtroot + "/search?q=" + cgi.escape(src(start,end)) + "&tree=" + treecfg.tree
    # Return an link with attributes a specified in data
    return "<a href=\"%s\" %s>" % (href, " ".join(("%s=\"%s\"" % (key, val) for key, val in data.items())))
  def close_link_region(region):
    return "</a>"

  # Functions for opening the stack of syntax regions
  # this essential amounts to a span with a set of classes
  def open_syntax_regions():
    if len(syntax_regions_stack) > 0:
      return "<span class=\"%s\">" % " ".join((data for start, end, data in syntax_regions_stack))
    return ""
  def close_syntax_regions():
    if len(syntax_regions_stack) > 0:
      return "</span>"
    return ""
  
  lines          = []
  offset         = 0
  line_number    = 0
  while offset < len(source):
    # Start a new line
    line_number += 1
    line = ""
    # Open all tags on the stack
    for region in link_regions_stack:
      line += open_link_region(region)
    # We open syntax regions after tags, because they can be opened and closed
    # without any effect, ie. inserting <b></b> has no effect...
    line += open_syntax_regions()
    
    # Append to line while we're still one it
    while offset < line_map[line_number]:
      # Find next offset as smallest candidate offset
      # Notice that we never go longer than to end of line
      next = line_map[line_number]
      # Next offset can be the next start of something
      if len(syntax_regions) > 0:
        next = min(next, syntax_regions[-1][0])
      if len(link_regions) > 0:
        next = min(next, link_regions[-1][0])
      # Next offset can be the end of something we've opened
      # notice, stack structure and sorting ensure that we only need test top
      if len(syntax_regions_stack) > 0:
        next = min(next, syntax_regions_stack[-1][1])
      if len(link_regions_stack) > 0:
        next = min(next, link_regions_stack[-1][1])
      
      # Output the source text from last offset to next
      if next < line_map[line_number]:
        line += cgi.escape(src(offset,next))
      else:
        # Throw away newline if at end of line
        line += cgi.escape(src(offset,next - 1))
      offset = next
      
      # Close syntax regions, modify stack and open them again
      # this makes sense even if there's not change to the stack
      # as we can't have span tags crossing link tags
      line += close_syntax_regions()
      while len(syntax_regions_stack) > 0 and syntax_regions_stack[-1][1] <= next:
        syntax_regions_stack.pop()
      while len(syntax_regions) > 0 and syntax_regions[-1][0] <= next:
        region = syntax_regions.pop()
        # Search for the right place in the stack to insert this
        # The stack is ordered s.t. we have longest end at the bottom (with respect to pop())
        for i in xrange(0, len(syntax_regions_stack) + 1):
          if len(syntax_regions_stack) == i or syntax_regions_stack[i][1] < region[1]:
            break
        syntax_regions_stack.insert(i, region)
      # Don't open the tags if at end of line
      if next < line_map[line_number]:
        line += open_syntax_regions()
      
      # Close and pop links that end here
      while len(link_regions_stack) > 0 and link_regions_stack[-1][1] <= next:
        line += close_link_region(link_regions_stack.pop())
      # Close remaining if at end of line
      if next < line_map[line_number]:
        for region in reversed(link_regions_stack):
          line += close_link_region(region)
      # Open and pop/push regions that start here
      while len(link_regions) > 0 and link_regions[-1][0] <= next:
        region = link_regions.pop()
        # If the region doesn't end before the top of the stack, we have
        # overlapping regions, this isn't good, so we discard this region
        if len(link_regions_stack) > 0 and link_regions_stack[-1][1] < region[1]:
          print "Error: Link region overlap"
          print "'%s' %r" % (source[region[0]:region[1]], region)
          print "'%s' %r" % (source[link_regions_stack[-1][0]:link_regions_stack[-1][1]], link_regions_stack[-1])
          print "   IN %s" % filepath
          print "------------------------------"
          continue  # Okay so skip it
        # Don't open if at end of line
        if next < line_map[line_number]:
          line += open_link_region(region)
        link_regions_stack.append(region)

    # Okay let's pop line annotations of the line_notes stack
    notes = []
    while len(line_notes) > 0 and line_notes[-1][0] == line_number:
      notes.append(line_notes.pop())

    lines.append((line_number, line, notes))
  # Return all lines of the file, as we're done
  return lines


def build_sections(treecfg, filepath, _zipper):
  """ Build sections for the sidebar """
  elements = [x for x in _zipper("get_sidebar_links")]
  if len(elements) == 0:
    return []
  
  containers = {}
  for e in elements:
    containers.setdefault(len(e) > 4 and e[4] or None, []).append(e)

  # Sort the containers by their location
  # Global scope goes last, and scopes declared outside of this file goes
  # before everything else
  clocs = { None: 2 ** 32 }
  for e in elements:
    if e[0] in containers:
      clocs[e[0]] = int(e[1])
  contKeys = containers.keys()
  contKeys.sort(lambda x, y: cmp(clocs.get(x, 0), clocs.get(y, 0)))

  sections = []
  for cont in contKeys:
    section = cont or ""
    items = []
    containers[cont].sort(lambda x, y: cmp(x[0], y[0]))
    for e in containers[cont]:
      img = (len(e) > 3 and e[3] or "page_white_code")
      title = len(e) > 2 and e[2] or e[0]
      if len(e) > 5 and e[5]:
        path = e[5]
      else:
        path = filepath.replace(treecfg.sourcedir + '/', '')
      items.append((img, cgi.escape(title), path, e[1]))
    sections.append((section, items))
  return sections



_revision = {}
def get_revision(treecfg):
  """ Get the revision for this tree """
  global _revision
  if _revision.get(treecfg.tree, None) is None:
    try:
      revision_command = treecfg.getOption('revision')
      revision_command = revision_command.replace('$source', treecfg.sourcedir)
      revision_process = subprocess.Popen([revision_command], stdout=subprocess.PIPE, shell=True)
      _revision[treecfg.tree] = revision_process.stdout.readline().strip()
    except:
      print '\033[93mError: %s\033[0m' % sys.exc_info()[1]
      _revision[treecfg.tree] = ""
  return _revision[treecfg.tree]


# HTML-ifier map
# The keys are the endings of files to match
# First set of values are {funcname, [funclist]} dicts
# funclist is the lists of functions to apply, as a (plugin name, func) tuple

htmlifier_map = {}
ending_iterator = []
inhibit_sidebar = {}

def build_htmlifier_map(plugins):
  # This looks like it would be smart :)
  global htmlifier_map, ending_iterator, inhibit_sidebar
  htmlifier_map = {}
  ending_iterator = []
  inhibit_sidebar = {}
  def add_to_map(ending, hmap, pluginname, append):
    for x in ['get_sidebar_links', 'get_link_regions', 'get_line_annotations',
        'get_syntax_regions']:
      if x not in hmap:
        continue
      details = htmlifier_map[ending].setdefault(x, [None])
      if append:
        details.append((pluginname, hmap[x]))
      else:
        details[0] = (pluginname, hmap[x])

    if 'get_inhibit_sidebar' in hmap and hmap['get_inhibit_sidebar'] is True:
      inhibit_sidebar[ending] = True

  # Add/append details for each map
  for plug in plugins:
    plug_map = plug.get_htmlifiers()
    for ending in plug_map:
      if ending not in htmlifier_map:
        ending_iterator.append(ending)
        htmlifier_map[ending] = {}
      nosquash = 'no-override' in plug_map[ending]
      add_to_map(ending, plug_map[ending], plug.__name__, nosquash)
  # Sort the endings by maximum length, so that we can just find the first one
  # in the list
  ending_iterator.sort(lambda x, y: cmp(len(y), len(x)))

def make_html(dxrconfig, srcpath, dstfile, treecfg, blob, conn = None, dbpath=None):
  # Match the file in srcpath
  result_map = {}
  signalStop = False
  inhibit = False

  for end in ending_iterator:
    if srcpath.endswith(end):
      for func in htmlifier_map[end]:
        reslist = result_map.setdefault(func, [None])
        flist = htmlifier_map[end][func]
        reslist.extend(flist[1:])
        if flist[0] is not None:
          reslist[0] = flist[0]
          signalStop = True
      if end in inhibit_sidebar:
        inhibit = True
    if signalStop:
      break

  if dbpath is None:
    dbpath = srcpath

  def _zipper(func):
    """ Returns all contents from all plugins. """
    if func not in result_map:
      return []
    return itertools.chain(*[
                             f(blob.get(name, None), srcpath, treecfg, conn, dbpath)
                             for name, f in result_map[func]]
    )
  build_html(dxrconfig, treecfg, srcpath, dstfile, _zipper)
