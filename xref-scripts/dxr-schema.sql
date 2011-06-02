PRAGMA synchronous=off;
PRAGMA page_size=4096;
PRAGMA count_changes=off;

drop table if exists types;
drop table if exists members;
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

-- Table members: all type members (data and methods) for classes/structs in types, with DECL and (sometimes) DEF 
-- mtname: Type Name (FK-types.tname)
-- mtloc: Type DECL Location
-- mname: Member Name
-- mshortname: Member Name without any (args) --> 'foo(x)' becomes 'foo' 
-- mdecl: Member Declaration Location
-- mdef: Member Definition Location
-- mvalue: if the member has a value (e.g., enum members), this is the value.
-- maccess: visibility of member - public, protected, private
-- mstatic: is this a static member
create table members (mtname TEXT, mtloc TEXT, mname TEXT, mshortname TEXT, mdecl TEXT, mdef TEXT, mvalue TEXT, maccess TEXT, mstatic INTEGER, PRIMARY KEY(mtname, mtloc, mname));

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

-- Table stmts: all statement info collected from process_function bodies
-- vfuncname: the name of the function in which this var occurs
-- vfuncloc: the location of the containing func definition
-- vname: the name of a variable
-- vshortname: Member Name without any (args) --> 'foo(x)' becomes 'foo' 
-- vlocf: the variable's location - file
-- vlocl: the variable's locaiton - line number
-- vlocc: the variable's location - column (not guaranteed to be accurate, just "larger" or "smaller" than others in the same line)
-- vtype: the type of the variable
-- vtloc: the location of the type's declaration (column is thrown away to match types->tname)
-- vmember: the name of the type this variable is a member of (optional)
-- vmemberloc: the decl location of the type this variable is a member of (optional)
-- visFunc: the variable is being used as a function call
-- visDecl: the variable is being used as part of a declaration
-- vdeclloc: where the variable was declared
-- NOTE: this key is longer than I want it to be, but due to templated functions, the signature of the func can vary with T
create table stmts(vfuncname TEXT, vfuncloc TEXT, vname TEXT, vshortname TEXT, vlocf TEXT, vlocl INTEGER, vlocc INTEGER, vtype TEXT, vtloc TEXT, vmember TEXT, vmemberloc TEXT, visFcall INTEGER, visDecl INTEGER, vdeclloc TEXT, PRIMARY KEY(vfuncname, vfuncloc, vname, vlocf, vlocl, vlocc, vtype));

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
