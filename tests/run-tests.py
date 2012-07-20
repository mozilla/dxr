#!/usr/bin/env python2

import sys, subprocess, os

# Make sure we're running the tests
if __name__ != '__main__':
  print >> sys.stderr, "run-tests-py is a standalone script, not a library!"
  sys.exit(1)
root = os.path.dirname(os.path.realpath(__file__)) + "/.."

# Fetch list of tests
tests = [d for d in os.listdir(root + "/tests") if os.path.isdir(root + "/tests/" + d)]

# Read parameters
tests_requested = []
for arg in sys.argv[1:]:
  if not arg.startswith("-"):
    if arg in tests:
      tests_requested.append(test)
    else:
      print >> sys.stderr, "%s is not a test!"
  if arg == "--list-tests":
    for test in tests:
      print test
    sys.exit(0)

if tests_requested == []:
  tests_requested = tests

# Show a tiny hint
if "-h" in sys.argv or "--help" in sys.argv:
  print "run-tests.py [--list-tests] [test]"

# Run tests
failed = []
for test in tests_requested:
  print ""
  print " ------------------ Running %s ------------------" % test
  testdir = root + "/tests/" + test
  testscript = testdir + "/run-" + test
  # Print if test script is missing
  if not os.path.isfile(testscript):
    print >> sys.stderr, "test script from %s is missing" % test
    failed.append(test)
    continue
  # Run test
  retval = subprocess.call(testscript, stdout = sys.stdout, stderr = sys.stderr, cwd = testdir)
  if retval != 0:
    failed.append(test)

# Print summary
print ""
print " ------------------ Summary ------------------"
for test in tests_requested:
  print "%-25s %s" % (test + ":", "failed!" if test in failed else "passed")

# Exit 1 if we failed
sys.exit(1 if len(failed) > 0 else 0)

