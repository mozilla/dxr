#!/usr/bin/env python2

class JsonOutput:
  need_separator = False
  content = ''

  def open(self):
    self.content += '{'
    self.need_separator = False

  def close(self):
    self.content += '}'
    self.need_separator = True

  def open_list(self):
    self.content += '['
    self.need_separator = False

  def close_list(self):
    self.content += ']'
    self.need_separator = True

  def key_value(self, key, value, quote_value):
    if self.need_separator is True:
      self.content += ','

    if key is not None:
      self.content += '"' + key + '"'
      self.content += ' : '

    if quote_value is True:
      self.content += '"' + value + '"'
    else:
      self.content += value

    self.need_separator = True

  def key_dict(self, key, nested_values):
    if self.need_separator is True:
      self.content += ','

    if key is not None:
      self.content += '"' + key + '"'
      self.content += ' : '

    self.open()

    for subkey in nested_values.keys():
      self.add(subkey, nested_values[subkey])

    self.close()
    self.need_separator = True

  def key_list(self, key, values):
    if self.need_separator is True:
      self.content += ','

    self.content += '"' + key + '"'
    self.content += ' : '

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

  def print_str(self):
    return '{' + self.content + '}'

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
