CREATE TABLE node(
  id INTEGER PRIMARY KEY,
  name TEXT,
  returnType TEXT,
  namespace TEXT,
  type TEXT,
  shortName TEXT,
  isPtr INTEGER,
  isVirtual INTEGER,
  loc TEXT,
  UNIQUE (name, loc) ON CONFLICT IGNORE
);

CREATE TABLE edge(
  caller INTEGER REFERENCES node,
  callee INTEGER REFERENCES node,
  PRIMARY KEY(caller, callee) ON CONFLICT IGNORE
);
-- XXX don't ignore duplicate edges? postprocess to add a count to the edge?

CREATE TABLE implementors(
  implementor TEXT,
  interface TEXT,
  method TEXT,
  loc TEXT,
  id INTEGER PRIMARY KEY,
  UNIQUE (implementor, interface, method, loc) ON CONFLICT IGNORE
);

