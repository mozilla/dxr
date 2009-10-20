#!/usr/bin/env python

import cgi
import os, tempfile, re
import subprocess
import sys, ConfigParser

form = cgi.FieldStorage()

# The code itself
code = ''
if form.has_key('code'):
  code = form['code'].value

# Type of code, one of 'js' or 'c++'
type = ''
if form.has_key('type'):
  type = form['type'].value

fshortwchar = False
if form.has_key('fshortwchar') and form['fshortwchar'].value == 'true':
  fshortwchar = True

text = ''

config = ConfigParser.ConfigParser()
config.read('./viewsource.config')

cxx = config.get('Tools', 'cxx')
dehydra = config.get('Tools', 'dehydra')
jshydra = config.get('Tools', 'jshydra')
cxxflags = '-fplugin=%s -fplugin-arg=./js/static/dump-dehydra-data.js' % (dehydra,) 

# Add -fshort-wchar flag if chosen
if type == 'c++' and fshortwchar:
  cxxflags = '-fshort-wchar ' + cxxflags

try:
  tmp = tempfile.NamedTemporaryFile(mode='w+t', suffix='.cpp')
  tmp.writelines([code,'\n'])
  tmp.seek(0)

  # Figure out which tool to use
  buildcmd = ''
  if type == 'c++':
    buildcmd = '%(cxx)s %(cxxflags)s -c %(filename)s -o /dev/null' % {'cxx': cxx, 'cxxflags': cxxflags, 'filename': tmp.name}
  else:
    buildcmd = '%(jshydra)s ./js/static/ast.js %(filename)s' % {'jshydra': jshydra, 'filename': tmp.name}
  stdout = subprocess.Popen(buildcmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
  text = stdout.read()
finally:
  tmp.close()

if text == '':
  text = 'There was a problem analyzing your code. No Output.'

print 'Content-Type: text/plain\n'
print text

