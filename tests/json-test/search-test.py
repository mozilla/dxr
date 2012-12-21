#!/usr/bin/env python2

import sys, urllib2, json, traceback

def search(query):
  url = "http://localhost:3571/search?format=json&tree=HelloWorld&q=%s&redirect=false" % query
  data = urllib2.urlopen(url).read()
  return json.loads(data)

failed = False

def test(query, paths):
  global failed
  print "Testing %s for %r" % (query, paths)
  try:
    res = search(query)
    rpaths = [result["path"] for result in res["results"]]
    for path in paths:
      if path not in rpaths:
        failed = True
        print >> sys.stderr, "Did not find %s in results for %s " % (path, query)
  except:
    print >> sys.stderr, "Test for %r in %s failed!" % (paths, query)
    print >> sys.stderr, traceback.format_exc()
    failed = True

test("main", ["main.c", "makefile"])
test("ext:h", ["BitField.h", "hello.h"])
test("ext:h", ["BitField.h", "hello.h"])
test("function:main", ["main.c"])
test("function:getHello", ["hello.h"])

# These are known failures. Fix them: bug 823777.
#test("callers:getHello", ["main.c"])
#test("called-by:main", ["hello.h"])

test("member:BitField", ["BitField.h"])

if failed:
  sys.exit(1)
