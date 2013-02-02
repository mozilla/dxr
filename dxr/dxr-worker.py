#!/usr/bin/env python2
# This is sitting in the package folder just to make it easy to find. It's
# nearly impossible to figure out where the commandline scripts of a
# distribution went in all situations (setup.py develop, setup.py install,
# etc.). Ultimately, this will become a proper module and be called via
# multiprocessing. For now, it has a hyphen in its name to make it obvious that
# it's not to be imported.

import dxr
import dxr.utils
import dxr.plugins
import os, sys
import getopt
import jinja2
import json
import codecs
import cgi
import datetime
from itertools import chain

def main(argv):
    # Options to read
    configfile  = None
    tree        = None
    start       = None    # database file id to start from
    end         = None    # database file id to end at

    # Parse arguments
    try:
        params = ["help", "file=", "tree=", "start=", "end="]
        options, args = getopt.getopt(argv, "hf:s:e:t:", params)
    except getopt.GetoptError:
        print >> sys.stderr, "Failed to parse options"
        print_usage()
        sys.exit(1)
    for arg, opt in options:
        if arg in ('-f', '--file'):
            if configfile:
                print >> sys.stderr, "Only one config file can be provided!"
                sys.exit(1)
            configfile = opt
        if arg in ('-h', '--help'):
            print_help()
            sys.exit(0)
        if arg in ('-t', '--tree'):
            if tree:
                print >> sys.stderr, "Only one tree can be provided!"
                sys.exit(1)
            tree = opt
        if arg in ('-s', '--start'):
            if start:
                print >> sys.stderr, "Only one start offset can be provided"
            start = int(opt)
        if arg in ('-e', '--end'):
            if end:
                print >> sys.stderr, "Only one end offset can be provided"
            end = int(opt)

    # Load configuration file
    config = dxr.utils.Config(configfile)

    # Find the tree
    for t in config.trees:
        if t.name == tree:
            tree = t
            break
    else:
        print sys.stderr, "You must provide a valid tree with --tree TREE"
        sys.exit(1)

    # Connect to database
    conn = dxr.utils.connect_database(tree)

    # Okay let's build the html
    build_html(tree, conn, start, end)

    # Close the database connection
    conn.commit()
    conn.close()


def print_usage():
    print "Usage: dxr-worker.py -f FILE -t TREE -s START -e END"


def print_help():
    print_usage()
    print """Options:
    -h, --help                          Show help information
    -f, --file      FILE                Configuration files
    -t, --tree      TREE                Tree to generate files for
    -s, --start     START               Start from file id START
    -e, --end       END                 End at file id END"""


def build_html(tree, conn, start, end):
    """ Build HTML for file ids from start to end """
    # Load htmlifier plugins
    plugins = dxr.plugins.load_htmlifiers(tree)
    for plugin in plugins:
        plugin.load(tree, conn)
    # Build sql statement and arguments
    sql = """
    SELECT
        path, icon, trg_index.text
        FROM trg_index, files
      WHERE trg_index.id = files.id
    """
    if start and end:
        sql += " AND trg_index.id >= ? AND trg_index.id <= ?"
        args = [start, end]
    elif start:
        sql += " AND trg_index.id >= ?"
        args = [start]
    elif end:
        sql += " AND trg_index.id <= ? "
        args = [end]
    else:
        args = []
    # Log a little information, at almost no overhead
    count = 0
    started = datetime.datetime.now()
    # Fetch each document one by one 
    for path, icon, text in conn.execute(sql, args):
        dst_path = os.path.join(tree.target_folder, path + ".html")
        # Give warning before overwriting the file
        if os.path.exists(dst_path):
            msg = "File '%s' already exists and will be overwritten!"
            print >> sys.stderr, msg % path
        print "Building: %s" % path
        htmlify(tree, conn, icon, path, text, dst_path, plugins)
        count += 1
    # Write time information
    time = datetime.datetime.now() - started
    print "Finished %s files in %s" % (count, time)
    

def htmlify(tree, conn, icon, path, text, dst_path, plugins):
    """ Build HTML for path, text save it to dst_path """
    # Create htmlifiers for this source
    htmlifiers = []
    for plugin in plugins:
        htmlifier = plugin.htmlify(path, text)
        if htmlifier:
            htmlifiers.append(htmlifier)
    # Load template
    env = dxr.utils.load_template_env(tree.config.temp_folder,
                                      tree.config.template_folder)
    tmpl = env.get_template('file.html')
    arguments = {
        # Set common template variables
        'wwwroot':        tree.config.wwwroot,
        'tree':           tree.name,
        'trees':          [t.name for t in tree.config.trees],
        'config':         tree.config.template_parameters,
        'generated_date': tree.config.generated_date,
        # Set file template variables
        'icon':           icon,
        'path':           path,
        'name':           os.path.basename(path),
        'lines':          build_lines(tree, conn, path, text, htmlifiers),
        'sections':       build_sections(tree, conn, path, text, htmlifiers)
    }
    # Fill-in variables and dump to file with utf-8 encoding
    tmpl.stream(**arguments).dump(dst_path, encoding = 'utf-8')



def build_lines(tree, conn, path, text, htmlifiers):
    """ Build lines for template """
    # Empty files, have no lines
    if len(text) == 0:
        return []

    # Get a decoder
    decoder = codecs.getdecoder("utf-8")
    # Let's defined a simple way to fetch and decode a slice of source
    def src(start, end = None):
        if isinstance(start, tuple):
            start, end = start[:2]
        return decoder(text[start:end], errors = 'replace')[0]
    # We shall decode on-the-fly because we need ascii offsets to do the rendering
    # of regions correctly. But before we stuff anything into the template engine
    # we must ensure that it's correct utf-8 encoded string
    # Yes, we just have to hope that plugin designer don't give us a region that
    # splits a unicode character in two. But what else can we do?
    # (Unless we want to make plugins deal with this mess)

    # Build a line map over the source (without exploding it all over the place!)
    line_map = [0]
    offset = text.find("\n", 0) + 1
    while offset > 0:
        line_map.append(offset)
        offset = text.find("\n", offset) + 1
    # If we don't have a line ending at the end improvise one
    if not text.endswith("\n"):
        line_map.append(len(text))

    # So, we have a minor issue with writing out the main body. Some of our
    # information is (line, col) information and others is file offset. Also,
    # we don't necessarily have the information in sorted order.

    regions = chain(*(htmlifier.regions()     for htmlifier in htmlifiers))
    refs    = chain(*(htmlifier.refs()        for htmlifier in htmlifiers))
    notes   = chain(*(htmlifier.annotations() for htmlifier in htmlifiers))

    # Quickly sort the line annotations in reverse order
    # so we can view it as a stack we just pop annotations off as we generate lines
    notes   = sorted(notes, reverse = True)

    # start and end, may be either a number (extent) or a tuple of (line, col)
    # we shall normalize this, and sort according to extent
    # This is the fastest way to apply everything...
    def normalize(region):
        start, end, data = region
        if end < start:
            # Regions like this happens when you implement your own operator, ie. &=
            # apparently the cxx-lang plugin doesn't provide and end for these
            # operators. Why don't know, also I don't know if it can supply this...
            # It's a ref regions...
            # TODO Make a NaziHtmlifierConsumer to complain about stuff like this
            return (start, start + 1, data)
        if isinstance(start, tuple):
            line1, col1 = start
            line2, col2 = end
            start = line_map[line1 - 1] + col1 - 1
            end   = line_map[line2 - 1] + col2 - 1
            return start, end, data
        return region
    # Add sanitizer to remove regions that have None as offsets
    # They are just stupid and shouldn't be there in the first place!
    sane    = lambda (start, end, data): start is not None and end is not None
    regions = (normalize(region) for region in regions if sane(region))
    refs    = (normalize(region) for region in refs    if sane(region))
    # That's it we've normalized this mess, so let's just sort it too
    order   = lambda (start, end, data): (- start, end, data)
    regions = sorted(regions, key = order)
    refs    = sorted(refs,    key = order)
    # Notice that we negate start, larges start first and ties resolved with
    # smallest end. This way be can pop values of the regions in the order
    # they occur...

    # Now we create two stacks to keep track of open regions
    regions_stack = []
    refs_stack    = []

    # Open/close refs, quite simple
    def open_ref(ref):
        start, end, menu = ref
        # JSON dump the menu and escape it for quotes, etc
        menu = cgi.escape(json.dumps(menu), True)
        return "<a data-menu=\"%s\">" % menu
    def close_ref(ref):
        return "</a>"

    # Functions for opening the stack of syntax regions
    # this essential amounts to a span with a set of classes
    def open_regions():
        if len(regions_stack) > 0:
            classes = (data for start, end, data in regions_stack)
            return "<span class=\"%s\">" % " ".join(classes)
        return ""
    def close_regions():
        if len(regions_stack) > 0:
            return "</span>"
        return ""
    
    lines          = []
    offset         = 0
    line_number    = 0
    while offset < len(text):
        # Start a new line
        line_number += 1
        line = ""
        # Open all refs on the stack
        for ref in refs_stack:
            line += open_ref(ref)
        # We open regions after refs, because they can be opened and closed
        # without any effect, ie. inserting <b></b> has no effect...
        line += open_regions()
        
        # Append to line while we're still one it
        while offset < line_map[line_number]:
            # Find next offset as smallest candidate offset
            # Notice that we never go longer than to end of line
            next = line_map[line_number]
            # Next offset can be the next start of something
            if len(regions) > 0:
                next = min(next, regions[-1][0])
            if len(refs) > 0:
                next = min(next, refs[-1][0])
            # Next offset can be the end of something we've opened
            # notice, stack structure and sorting ensure that we only need test top
            if len(regions_stack) > 0:
                next = min(next, regions_stack[-1][1])
            if len(refs_stack) > 0:
                next = min(next, refs_stack[-1][1])

            # Output the source text from last offset to next
            if next < line_map[line_number]:
                line += cgi.escape(src(offset, next))
            else:
                # Throw away newline if at end of line
                line += cgi.escape(src(offset, next - 1))
            offset = next
            
            # Close regions, modify stack and open them again
            # this makes sense even if there's not change to the stack
            # as we can't have syntax tags crossing refs tags
            line += close_regions()
            while len(regions_stack) > 0 and regions_stack[-1][1] <= next:
                regions_stack.pop()
            while len(regions) > 0 and regions[-1][0] <= next:
                region = regions.pop()
                # Search for the right place in the stack to insert this
                # The stack is ordered s.t. we have longest end at the bottom
                # (with respect to pop())
                for i in xrange(0, len(regions_stack) + 1):
                    if len(regions_stack) == i or regions_stack[i][1] < region[1]:
                        break
                regions_stack.insert(i, region)
            # Open regions, if not at end of line
            if next < line_map[line_number]:
                line += open_regions()
            
            # Close and pop refs that end here
            while len(refs_stack) > 0 and refs_stack[-1][1] <= next:
                line += close_ref(refs_stack.pop())
            # Close remaining if at end of line
            if next < line_map[line_number]:
                for ref in reversed(refs_stack):
                    line += close_ref(ref)
            # Open and pop/push refs that start here
            while len(refs) > 0 and refs[-1][0] <= next:
                ref = refs.pop()
                # If the ref doesn't end before the top of the stack, we have
                # overlapping regions, this isn't good, so we discard this ref
                if len(refs_stack) > 0 and refs_stack[-1][1] < ref[1]:
                    stack_src = text[refs_stack[-1][0]:refs_stack[-1][1]]
                    print >> sys.stderr, "Error: Ref region overlap"
                    print >> sys.stderr, "   > '%s' %r" % (text[ref[0]:ref[1]], ref)
                    print >> sys.stderr, "   > '%s' %r" % (stack_src, refs_stack[-1])
                    print >> sys.stderr, "   > IN %s" % path
                    continue  # Okay so skip it
                # Open ref, if not at end of line
                if next < line_map[line_number]:
                    line += open_ref(ref)
                refs_stack.append(ref)

        # Okay let's pop line annotations of the notes stack
        current_notes = []
        while len(notes) > 0 and notes[-1][0] == line_number:
            current_notes.append(notes.pop()[1])

        lines.append((line_number, line, current_notes))
    # Return all lines of the file, as we're done
    return lines


def build_sections(tree, conn, path, text, htmlifiers):
    """ Build navigation sections for template """
    # Chain links from different htmlifiers
    links = chain(*(htmlifier.links() for htmlifier in htmlifiers))
    # Sort by importance (resolve tries by section name)
    links = sorted(links, key = lambda section: (section[0], section[1]))
    # Return list of section and items (without importance)
    return [(section, list(items)) for importance, section, items in links]


if __name__ == '__main__':
    main(sys.argv[1:])
