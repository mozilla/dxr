"""
  Module for parsing search queries and representing them as a list of free text
  keywords and named parameters.
"""

import re

pat = re.compile("([\\\"\\' ]+)")

def parse_query(query):
  fts_query = ""
  keywords = []
  phrases = []
  params = {}
  phrase = None
  isword = True
  for word in pat.split(query):
    if isword:
      if len(word) == 0:
        pass
      elif phrase:
        fts_query += " " + word + " "
        phrase.append(word)
      elif ":" in word:
        key, val = word.split(":", 1)
        params.setdefault(key, []).append(val)
      else:
        fts_query += " " + word + " "
        keywords.append(word)
    else:
      # Yes, if you use " inside ' or V.V. it won't work as expected, sorry
      # don't do that...
      # Okay for future reference clean up this parsing. And support more
      # features, take a look at the enhanced FTS query syntax for sqlite
      # thought this might require that we compile sqlite ourselves.
      # At least it not mainstream anywhere now.
      if "'" in word or '"' in word:
        fts_query += " ' "
        if phrase:
          phrases.append(phrase)
          phrase = None
        else:
          phrase = []
    isword = not isword
  if phrase:
    phrases.append(phrase)
  return {"keywords":   keywords,
          "phrases":    phrases,
          "parameters": params,
          "fts_query":  fts_query.replace("'", "\"")}
