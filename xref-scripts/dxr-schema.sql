PRAGMA synchronous=off;
PRAGMA page_size=4096;
PRAGMA count_changes=off;

-- Scope definitions
DROP TABLE IF EXISTS scopes;
CREATE TABLE scopes (
  scopeid INTEGER NOT NULL, -- An ID for the scope, used in other tables. All
                            -- entries in this table will have strictly
                            -- positive values; negative values for scopes are
                            -- special values
  sname VARCHAR(256),       -- The name of the scope
  sloc VARCHAR(256),        -- The file:loc[:col] of the canonical declaration
  PRIMARY KEY(scopeid)
);

-- Types
DROP TABLE IF EXISTS types;
CREATE TABLE types (
  tid       INTEGER NOT NULL,      -- The unique ID for this type
  scopeid   INTEGER NOT NULL,      -- The scope of this type
  tname     VARCHAR(256) NOT NULL, -- The simple name of this type
  tqualname VARCHAR(256) NOT NULL, -- The fully-qualified name of this type
  tloc      VARCHAR(256) NOT NULL, -- The location of the type
  tkind     VARCHAR(32),           -- The kind of the type (e.g., syntax)
  PRIMARY KEY(tid),
  UNIQUE(tqualname, tloc)
);

-- Table impl: all type hierarchy implementation info (e.g., every concrete class for a base class or interface) 
-- tbname: Type Base Name (FK-types.tname), tbloc: Type Base DECL Location
-- tcname: Type Concrete Name (FK-types.tname), tcloc: Type Concrete DECL Location 
-- direct: Used to recreate inheritance hierarchy [1=direct base, -1=non-direct base]
create table impl (tbname TEXT, tbloc TEXT, tcname TEXT, tcloc TEXT, direct INTEGER, PRIMARY KEY(tbname, tbloc, tcname, tcloc));

DROP TABLE IF EXISTS impl;
CREATE TABLE impl (
  tbase    INTEGER NOT NULL, -- The tid of the base type
  tderived INTEGER NOT NULL, -- The tid of the derived type
  inhtype  VARCHAR(32),      -- The type of the inheritance
                             -- NULL: indirect (needed for SQL queries)
  PRIMARY KEY(tbase, tderived)
);

-- Functions
CREATE TABLE functions (
  funcid    INTEGER NOT NULL,      -- A unique ID for the function. As functions
                                   -- are themselves scopes, this is also a
                                   -- usable scope ID.
  scopeid   INTEGER NOT NULL,      -- The scope in which this function is
                                   -- defined
  fname     VARCHAR(256) NOT NULL, -- The short name of the function
  flongname VARCHAR(512) NOT NULL, -- A fully-qualified name for the function
                                   -- This should include argument types
  floc      VARCHAR(256),          -- file:line[:col] for the definition of this
                                   -- function
  modifiers VARCHAR(256),          -- Modifiers (e.g., private) for the function
  PRIMARY KEY(funcid),
  UNIQUE(scopeid, flongname, floc)
);

-- Variables
DROP TABLE IF EXISTS variables;
CREATE TABLE variables (
  varid     INTEGER NOT NULL,      -- A unique ID among variables
  scopeid   INTEGER NOT NULL,      -- The scope of the variable
  vname     VARCHAR(256) NOT NULL, -- The name of the variable
  vloc      VARCHAR(256),          -- The file:line[:col] of the variable
  vtype     VARCHAR(256),          -- The full type of the variable
  modifiers VARCHAR(256),          -- Any modifiers in declaration
  PRIMARY KEY(varid),
  UNIQUE(vname, vloc, vtype)
);

DROP TABLE IF EXISTS refs;
CREATE TABLE refs (
  refid  INTEGER NOT NULL,      -- The ID of the identifier being referenced
                                -- This can be variables, functions, types, ...
  refloc VARCHAR(256) NOT NULL, -- The file where the reference is located
  extent VARCHAR(30) NOT NULL,  -- The extent (start:end) of the reference
  PRIMARY KEY(refid, refloc)
);
