#!/usr/bin/env python2
import sys

class JsonOutput:
  need_separator = False
  outfd = sys.stdout

  def __init__(self, outfd):
    self.outfd = outfd

  def open(self):
    if self.need_separator is True:
      self.outfd.write(',')

    self.outfd.write('{')
    self.need_separator = False

  def close(self):
    self.outfd.write('}')
    self.need_separator = True

  def open_list(self):
    if self.need_separator is True:
      self.outfd.write(',')

    self.outfd.write('[')
    self.need_separator = False

  def close_list(self):
    self.outfd.write(']')
    self.need_separator = True

  def key(self, key):
    if self.need_separator is True:
      self.outfd.write(',')

    if key is not None:
      self.outfd.write('"')
      self.outfd.write(key)
      self.outfd.write('":')

    self.need_separator = False

  def key_value(self, key, value, quote_value):
    self.key(key)

    if quote_value is True:
      self.outfd.write('"')

    self.outfd.write(value)

    if quote_value is True:
      self.outfd.write('"')

    self.need_separator = True

  def key_dict(self, key, nested_values):
    self.key(key)
    self.open()

    for subkey in nested_values.keys():
      self.add(subkey, nested_values[subkey])

    self.close()
    self.need_separator = True

  def key_list(self, key, values):
    self.key(key)
    self.open_list()

    for subvalue in values:
      self.add(None, subvalue)

    self.close_list()
    self.need_separator = True

  def add(self, key, value):
    if isinstance(value, dict):
      self.key_dict(key, value)
    elif isinstance(value, list):
      self.key_list(key, value)
    elif isinstance(value, int):
      self.key_value(key, str(value), False)
    else:
      self.key_value(key, str(value), True)

#  def print_str(self):
#    return '{' + self.content + '}'

#if __name__ == '__main__':
#  json = JsonOutput()
#
#  json.add('foo', 'bar')
#  json.add('age', 666)
#  json.add('hash', { 'aa': 'bb', 'cc': 'dd', 'zz': [ 1, 3, 5]})
#  json.add('list', [1, 2, 3])
#  json.add('mixed', [ {'Foo': 'bar', 'Tu': 'ruru' }, { 'lala': 'whee', 'pi': 3 } ])
#
#  print json.print_str();
