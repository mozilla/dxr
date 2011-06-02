PRAGMA synchronous=off;
PRAGMA page_size=4096;
PRAGMA count_changes=off;

drop table if exists types;
drop table if exists impl;
drop table if exists callers;
drop table if exists warnings;

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

-- Types are a subtype of scopes
-- Table types: all named structs and classes defined in the mozilla source tree
-- tname: Type Name
-- tloc: Type DECL Location
-- ttypedefname: if this type is a typedef of some other type, this is the real type name
-- ttypedefloc: if this type is a typedef of some other type, this is the real type loc
-- tkind: Type Kind (e.g., class, struct, interface)
-- tmodule: Type Module
-- tignore: mark internal types that are not interesting to moz devs [1 = true, 0 = false]
-- ttemplate: If this is a template instance, the name of the template (nsCOMPtr<nsFoo> --> nsCOMPtr)
create table types(tname TEXT, tloc TEXT, ttypedefname TEXT, ttypedefloc TEXT, tkind TEXT, ttemplate TEXT, tmodule TEXT, tignore INTEGER, PRIMARY KEY(tname, tloc));

-- Table impl: all type hierarchy implementation info (e.g., every concrete class for a base class or interface) 
-- tbname: Type Base Name (FK-types.tname), tbloc: Type Base DECL Location
-- tcname: Type Concrete Name (FK-types.tname), tcloc: Type Concrete DECL Location 
-- direct: Used to recreate inheritance hierarchy [1=direct base, -1=non-direct base]
create table impl (tbname TEXT, tbloc TEXT, tcname TEXT, tcloc TEXT, direct INTEGER, PRIMARY KEY(tbname, tbloc, tcname, tcloc));

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

DROP TABLE IF EXISTS variable_refs;
CREATE TABLE variable_refs (
  varid INTEGER NOT NULL,      -- The ID of the variable being referenced
  reff  VARCHAR(256) NOT NULL, -- The file where the reference is located
  refl  INTEGER NOT NULL,      -- The line of the reference
  refc  INTEGER NOT NULL,      -- The column of the reference
  PRIMARY KEY(varid, reff, refl, refc)
);

-- Table macros: all macros defined in translation units
-- mname: the name of the macro
-- mshortname: name with no (args)
-- mvalue: the value of the macro
create table macros(mname TEXT, mshortname TEXT, mvalue TEXT, PRIMARY KEY(mshortname, mvalue));

-- Table warnings: all GCC file warnings for the build
-- wfile: the file that produced the warning
-- wloc: the line number
-- wmsg: the warning message
create table warnings(wid INTEGER, wfile TEXT, wloc INTEGER, wmsg TEXT, PRIMARY KEY(wfile, wloc, wmsg));
