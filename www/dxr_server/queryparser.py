"""
  Module for parsing search queries and representing them as a list of free text
  keywords and named parameters.
"""

import re

# List of parameters to isolate in the search query, ie. path:mypath
_parameters = ("path", "ext", "type", "type-ref", "function", "function-ref",
"var", "var-ref", "macro", "macro-ref", "calls", "called-by", "warning",
"bases", "derived", "member")

# Pattern recognizing a parameter and a argument, a phrase or a keyword
_pat = r"((?P<param>%s):(?P<arg>[^ ]+))|(\"(?P<phrase>[^\"]+)\")|(?P<keyword>[^\"]+)" % "|".join(_parameters)
_pat = re.compile(_pat)

class Query:
  """ Query object, constructor will parse any search query """
  def __init__(self, querystr):
    self.params = {}
    for param in _parameters:
      self.params[param] = []
    self.keywords = []
    self.phrases = []
    # We basically iterate over the set of matches left to right
    for token in (match.groupdict() for match in _pat.finditer(querystr)):
      if token["param"] and token["arg"]:
        self.params[token["param"]].append(token["arg"])
      if token["phrase"]:
        self.phrases.append(token["phrase"])
      if token["keyword"]:
        self.keywords.append(token["keyword"])

