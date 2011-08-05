#!/usr/bin/env python

import sys
sys.path.append('..')

import ConfigParser
import imp, dxr

# Read in the configuration for the test
tests = ConfigParser.ConfigParser()
tests.read('tests.ini')
testname = sys.argv[1]

# Get the database data for the tree
dxrcfg = dxr.load_config(tests.get(testname, 'dxrconfig'))
if len(dxrcfg.trees) != 1:
  raise Exception('Database can only have one tree')
tree = dxrcfg.trees[0]
big_blob = dxr.load_big_blob(tree)
# For the purposes of language data, dxr.languages.language_data too
big_blob['dxr.language_data'] = dxr.languages.language_data

# Load the checker data
load_data = open(tests.get(testname, 'checkdb'))
check_blob = eval(load_data.read())
load_data.close()


errors = []

def verifyDatabase(output, standard, should_be_present, string):
  for tablename, table in standard.iteritems():
    sub_present = should_be_present
    if isinstance(tablename, str) and tablename[0] == '~':
      tablename = tablename[1]
      sub_present = True
    if tablename not in output:
      if not sub_present:
        continue # Expected (maybe)
      errors.append('%s%s not found in output' % (string, tablename))
      continue
    
    outtable = output[tablename]
    if isinstance(table, dict):
      if not isinstance(outtable, dict):
        errors.append('%s%s not a dictionary' % (string, tablename))
        continue
      verifyDatabase(output[tablename], table, sub_present,
        string + str(tablename) + '.')
    elif isinstance(table, list):
      raise Exception("Finish me")
    else:
      if not sub_present:
        errors.append('%s%s is found' % (string, tablename))
      elif outtable != table:
        errors.append('%s%s is different: %s versus %s' % (
          string, tablename, repr(table), repr(outtable)))

verifyDatabase(big_blob, check_blob, True, '')
if len(errors) == 0:
  print 'TEST-PASS | %s' % testname
else:
  for error in errors:
    print 'TEST-FAIL | %s | %s' % (testname, error)
