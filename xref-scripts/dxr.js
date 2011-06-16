/* Notes:
   ------
* process_function()
- gives a member's definition (mdef) IF the normalized loc is rooted in something other than /dist/include

* process_type() (actually, print_members() called via process_type)
- gives a member's declaration (mdecl) IF loc is normalized and not rooted in /dist/include
- NOTE: process_function/print_members will give the same loc if the member is defined/declared in the same place, for example:

nsAccessible.h 138: static PRUint32 State(nsIAccessible *aAcc) { PRUint32 state = 0; if (aAcc) aAcc->GetFinalState(&state, nsnull); return state; }
nsAccessible process_function() mtname=nsAccessible mname=State(nsIAccessible*) loc=/home/dave/mozilla-central/src/accessible/src/base/nsAccessible.h:138
nsAccessible print_members() mtname=nsAccessible mname=State(nsIAccessible*) loc=/home/dave/mozilla-central/src/accessible/src/base/nsAccessible.h:138

- NOTE: data members will have nothing in process_function, and only appear in print_members(), for example:

253: PRInt32 mAccChildCount; // protected data member
nsAccessible print_members() mtname=nsAccessible mname=mAccChildCount loc=/home/dave/mozilla-central/src/accessible/src/base/nsAccessible.h:253

*/

// Change this to your src root
// TODO: get this working with this.arguments
var srcroot = "/src/dxr/";
var srcRegex = new RegExp("^" + srcroot);

var sql = [];

function process_decl (d) {
  // skip things like /home/dave/dxr/tools/gcc-dehydra/installed/include/c++/4.3.0/exception
  if (!srcRegex.test(d.loc.file))
    return;

  // Skip things we don't care about
  if ( (/:?:?operator.*$/.exec(d.name)) ||      /* overloaded operators */
       (/^D_[0-9]+$/.exec(d.name))      ||      /* gcc temporaries */
       (/^_ZTV.*$/.exec(d.name))        ||      /* vtable vars */
       (/.*COMTypeInfo.*/.exec(d.name)) ||      /* ignore COMTypeInfo<int> */
       ('this' == d.name)          ||
       (/^__built_in.*$/.exec(d.name)) )        /* gcc built-ins */
    return;

  if (d.isFunction) {
    // Treat the decl of a func like one of the statements in the func so we can link params
    var vfuncname = d.name;
    fix_path(d.loc);
    var vfuncloc = d.loc.file + ":" + d.loc.line.toString();

    // Treat the actual func decl as a statement so we can easily linkify it
    var vtype = '';
    var vname = d.name;

    if (/::/.exec(vname)) {
      var parts = parse_name(d);
      vtype = parts.mtname || vtype;
      vname = parts.mname || vname;
    }

    var vshortname = vname.replace(/\(.*$/, '');
    var vlocf = d.loc.file;
    var vlocl = d.loc.line;
    var vlocc = d.loc.column;
    var vtloc = '';

    if (d.memberOf && d.memberOf.loc) {
      fix_path(d.memberOf.loc);
      vtloc = d.memberOf.loc.file + ":" + d.memberOf.loc.line.toString();
    }

    sql.push (insert_stmt("stmts", ['vfuncname','vfuncloc','vname','vshortname','vlocf','vlocl','vlocc','vtype','vtloc','visFcall','visDecl'],
                          [vfuncname, vfuncloc, vname, vshortname, vlocf, vlocl, vlocc, vtype, vtloc,-1,1]));

    if (!d.parameters)
      return;

    // Keep track of all params in the function
    for(var i = 0; i < d.parameters.length; i++) {
      vname = d.parameters[i].name;

      // we'll skip |this| and treat it as a keyword instead
      if ('this' == vname)
        continue;

      vshortname = vname.replace(/\(.*$/, '');  // XXX: will vname not always be the same in this case?
      vlocf = d.loc.file;
      vlocl = d.loc.line;
      d.loc.column++ // col is never accurate, but indicates "further"
      vlocc = d.loc.column;
      vtype = '';
      vtloc = '';
      if (d.parameters[i].type) {
        vtype = d.parameters[i].type.name;
        vtloc = d.parameters[i].type.loc ? d.parameters[i].type.loc.file + ":" + d.parameters[i].type.loc.line.toString() : '';
      }

      sql.push (insert_stmt("stmts", ['vfuncname','vfuncloc','vname','vshortname','vlocf','vlocl','vlocc','vtype','vtloc', 'visFcall', 'visDecl'],
                            [vfuncname, vfuncloc, vname, vshortname, vlocf, vlocl, vlocc, vtype, vtloc, -1, 1]));
    }
  }
}


// DECLs
function process_type (c) {
  //TODO - what to do about other types?
  if (c.typedef)
    process_typedef(c);
  else if (/class|struct/.exec(c.kind))
    process_RegularType(c);
  else if (c.kind == 'enum')
    process_EnumType(c);
  // TODO: what about other types?

  function process_typedef (c) {
    if (srcRegex.test(c.loc.file) || /^[^\/]+\.cpp$/.exec(c.loc.file) || /dist\/include/.exec(c.loc.file)) {
      // Normalize path and throw away column info -- we just care about file + line for types.
      fix_path(c.loc);
      var tloc = c.loc.file + ":" + c.loc.line.toString();
      var ttypedefname = c.typedef.name || '';
      var ttypedefloc = '';
      if (c.typedef.loc) {
        var vloc = c.typedef.loc;
        fix_path(vloc);
        ttypedefloc = vloc.file + ":" + vloc.line.toString();
      }

      var ttemplate = '';
      if (c.template)
        ttemplate = c.template.name;

      var tignore = 0;

      sql.push(insert_stmt("types", ['tname','tloc','ttypedefname','ttypedefloc','tkind','ttemplate','tignore','tmodule'],
                           [c.name, tloc, ttypedefname, ttypedefloc, 'typedef', ttemplate, tignore, 'fixme']));
    }
  }

  function process_EnumType (c) {
    if (!c.name || c.name.toString() == 'undefined')
      return;

    if (srcRegex.test(c.loc.file) || /^[^\/]+\.cpp$/.exec(c.loc.file) || /dist\/include/.exec(c.loc.file)) {
      // Normalize path and throw away column info -- we just care about file + line for types.
      fix_path(c.loc);
      var tloc = c.loc.file + ":" + c.loc.line.toString();

      // 'fixme' will be corrected in post-processing.  Can't do it here, because I need to follow
      // symlinks to get full paths for some files.
      sql.push(insert_stmt("types", ['tname','tloc','tkind','tmodule'],
                           [c.name, tloc, c.kind, 'fixme']));

      if (c.members) {
        for (var i = 0; i < c.members.length; i++) {
          // XXX: use tloc for mtloc, mdecl, mdef, since they are essentially the same thing.
          var mshortname = c.members[i].name.replace(/\(.*$/, '');
          var mstatic = c.members[i].isStatic ? 1 : -1;
          var maccess = c.members[i].access || '';
          sql.push(insert_stmt("members", ['mtname','mtloc','mname','mshortname','mdecl','mdef','mvalue','maccess','mstatic'], [c.name,tloc,c.members[i].name,mshortname,tloc,tloc,c.members[i].value,maccess,mstatic]));
        }
      }
    }
  }

  function process_RegularType (c) {
    if (!c.name || c.name.toString() == 'undefined')
      return;

    // Various internal types are uninteresting for autocomplete and such
    var tignore = 0;
    if (/.*COMTypeInfo.*/.exec(c.name))
      return;

    // Lots of types are really just instances of a handful of templates
    // for example nsCOMPtr.  Keep track of the underlying template type
    var ttemplate = '';
    if (c.template)
      ttemplate = c.template.name;

    // If this type is a typedef for something else, get that info too
    var ttypedefname = '';
    var ttypedefloc = '';
    if (c.typedef) {
      ttypedefname = c.typedef.name;
      fix_path(c.typedef.loc);
      // Throw away column info for types.
      ttypedefloc = c.typedef.loc.file + ":" + c.typedef.loc.line.toString();
    }

    // Only add types when seen within source (i.e., ignore all type
    // info when used vs. declared, since we want source locations).
    // NOTE: this also kills off dist/include/foo/nsIFoo.h autogenerated from idl.
    // Mapping back to the idl is likely better anyhow (which MXR does now).
    // NOTE2: there is one more case we care about: sometimes .cpp files are linked
    // into the objdir, and linked locally (e.g., xpcom/glue), and in such cases
    // loc will be a filename with no path.  These are useful to have after post-processing.
    if (srcRegex.test(c.loc.file) || /^[^\/]+\.cpp$/.exec(c.loc.file) || /dist\/include/.exec(c.loc.file)) {
      // Normalize path and throw away column info -- we just care about file + line for types.
      fix_path(c.loc);
      var tloc = c.loc.file + ":" + c.loc.line.toString();

      // 'fixme' will be corrected in post-processing.  Can't do it here, because I need to follow
      // symlinks to get full paths for some files.
      sql.push(insert_stmt("types", ['tname','tloc','ttypedefname','ttypedefloc','tkind','ttemplate','tignore','tmodule'],
                         [c.name, tloc, ttypedefname, ttypedefloc, c.kind, ttemplate, tignore, 'fixme']));

      if (c.members)
        print_members(c, c.members);

      if (c.bases)
        print_all_bases(c, c.bases, true);
    }
  }
}

// Def
function process_function(decl, body) {
  // Only worry about members in the source tree (e.g., ignore /usr/... or /dist/include)
  if (!/.*\/dist\/include.*/.exec(decl.loc.file) && srcRegex.test(decl.loc.file)) {
    fix_path(decl.loc);
    var floc = decl.loc.file + ":" + decl.loc.line.toString();

    if (decl.isStatic && !decl.memberOf) {
      // file-scope static
//      sql.push(insert_stmt("funcs", ['fname','floc'], [decl.name, floc]));
      sql.push(insert_stmt("members", ['mtname','mtloc','mname','mshortname','mdecl','mvalue','maccess','mstatic'], ['[File Scope Static]',decl.loc.file,decl.name,decl.shortname,floc,'','','1']));
    } else { // regular member in the src
      var m = parse_name(decl);
      var mtloc = 'no_loc'; // XXX: does this case really matter (i.e., won't memberOf.loc always exist)?
      if (decl.memberOf && decl.memberOf.loc) {
        fix_path(decl.memberOf.loc)
        mtloc = decl.memberOf.loc.file + ":" + decl.memberOf.loc.line.toString();
      }

      var update = "update or abort members set mdef=" + quote(floc);
      update += " where mtname=" + quote(m.mtname) + " and mtloc=" + quote(mtloc) + " and mname=" + quote(m.mname) + ";";

      sql.push(update);
    }

    function processStatements(stmts) {

      function processVariable(s, /* optional */ loc) {
        // if name is undef, skip this
        if (!s.name)
          return;

        // TODO: should I figure out what is going on here?  Sometimes type is null...
        if (!s.type)
          return;

        // Skip gcc temporaries
        if (s.isArtificial)
          return;

        // if loc is defined (e.g., we're in an .assign statement[], use that instead).
        var vloc = loc || stmts.loc;

        if (!vloc)
          return;

        var vname = s.name;

        // Ignore statements and other things we can't easily link in the source.
        if ( (/:?:?operator/.exec(vname))    ||      /* overloaded operators */
             (/^D_[0-9]+$/.exec(vname))      ||      /* gcc temporaries */
             (/^_ZTV.*$/.exec(vname))        ||      /* vtable vars */
             (/.*COMTypeInfo.*/.exec(vname)) ||      /* ignore COMTypeInfo<int> */
             ('this' == vname)          ||
             (/^__built_in.*$/.exec(vname)) )        /* gcc built-ins */
          return;

        var vtype = '';
        var vtloc = '';
        var vmember = '';
        var vmemberloc = '';
        var vdeclloc = '';

        if (s.type && s.type.loc)
          fix_path(s.type.loc);

        // Special case these smart pointer types: nsCOMPtr, nsRefPtr, nsMaybeWeakPtr, and nsAutoPtr.
        // This is a hack, and very Mozilla specific, but lets us treat these as if they were regular
        // pointer types.
        if ((/^nsCOMPtr</.exec(s.type.name) ||
             /^nsRefPtr</.exec(s.type.name) ||
             /^nsAutoPtr</.exec(s.type.name) ||
             /^nsMaybeWeakPtr</.exec(s.type.name)) && s.type.template) {
          // Use T in nsCOMPtr<T>.
          vtype = s.type.template.arguments[0].name + "*";  // it's really a pointer, so add *
          vtloc = s.type.template.arguments[0].loc;
          // Increase the column, since we'll hit this spot multiple times otherwise
          // (e.g., once for nsCOMPtr and one for internal type.)  This prevents primary key dupes.
          vloc.column++;
        } else if (/::/.exec(s.name)) {
          var parts = parse_name(s);
          vtype = s.type.name;
          vtloc = s.type.loc;
          if (s.memberOf && s.memberOf.loc) {
            fix_path(s.memberOf.loc);
            vmember = s.memberOf.name;
            vmemberloc = s.memberOf.loc.file + ":" + s.memberOf.loc.line.toString();
          }
          vname = parts.mname ? parts.mname : vname;
        } else {
          if (s.type.isPointer) {
            vtype = s.type.type.name;
            vtloc = s.type.type.loc;
          } else {
            vtype = s.type.name;
            vtloc = s.type.loc;
          }
        }

        if (s.fieldOf && !vtloc)
          vtloc = s.fieldOf.type.loc;

        // TODO: why are these null sometimes?
        //      if (vloc) {
        fix_path(vloc);
        var vlocf = vloc.file;
        var vlocl = vloc.line;
        var vlocc = vloc.column;

        // There may be no type, so no vtloc
        vtype = vtype || '';
        if (vtloc) {
          fix_path(vtloc);
          vtloc = vtloc.file + ":" + vtloc.line.toString();
        }

        if (s.loc) {
          fix_path(s.loc);
          vdeclloc = s.loc.file + ":" + s.loc.line.toString();
        }

        var vfuncloc = decl.loc.file + ":" + decl.loc.line.toString();
        var vshortname = s.shortName; //vname.replace(/\(.*$/, '');
        var visFcall = s.isFcall ? 1 : -1;

        sql.push (insert_stmt("stmts", ['vfuncname','vfuncloc','vname','vshortname','vlocf','vlocl','vlocc','vtype','vtloc','vmember','vmemberloc','visFcall','vdeclloc'],
                              [decl.name, vfuncloc, vname, vshortname, vlocf, vlocl, vlocc, vtype, vtloc, vmember, vmemberloc, visFcall, vdeclloc]));

        // Deal with args to functions called by this var (i.e., function call, get a and b for g(a, b))
        if (s.arguments) {
          vloc.column += vname.length;
          for (var k = 0; k < s.arguments.length; k++) {
            vloc.column += k + 1; // just to indicate "further"
            processVariable(s.arguments[k], vloc);
          }
        }

        // Deal with any .assign variables (e.g., y = x ? a : b);
        if (s.assign) {
          vloc.column += vname.length;
          for (var k = 0; k < s.assign.length; k++) {
            vloc.column += k + 1; // just to indicate "further"
            processVariable(s.assign[k], vloc);
          }
        }
      }

      for(var j = 0; j < stmts.statements.length; j++) {
        var s = stmts.statements[j];
        // advance the column on this line by one to indicate we're "further" right/down
        if (stmts.loc)
          stmts.loc.column += j;
        processVariable(s);
      }
    }

    for (var i = 0; i < body.length; i++) {
      processStatements(body[i]);
    }
  }
}

function input_end() {
  // This assumes |sort -u| will be called to get INSERT and UPDATES in right order
  write_file (sys.aux_base_name + ".sql", sql.join("\n") + "\n");
}

function print_all_bases(t, bases, direct) {
  // Keep track of whether this is a direct child of the base vs. many levels deep
  var directBase = direct ? 1 : -1;

  for (var i = 0; i < bases.length; i++) {
    var tbloc = 'no_loc';
    if (bases[i].type.loc) { // XXX: why would this not exist?
      fix_path(bases[i].type.loc);
      tbloc = bases[i].type.loc.file + ":" + bases[i].type.loc.line.toString();
    }

    var tcloc = 'no_loc';
    if (t.loc) { // XXX: why would this not exist?
      fix_path(t.loc);
      tcloc = t.loc.file + ":" + t.loc.line.toString();
    }

    sql.push (insert_stmt("impl", ['tbname','tbloc','tcname','tcloc','direct'],
                                  [bases[i].type.name,tbloc,t.name,tcloc,directBase]));
    if (bases[i].type.bases) {
      // pass t instead of base[i].name so as to flatten the inheritance tree for t
      print_all_bases(t, bases[i].type.bases, false);
    }
  }
}

function print_members(t, members) {
  for (var i = 0; i < members.length; i++) {
    var m = parse_name(members[i]);
    // TODO: should I just use t.loc here instead?
    fix_path(members[i].memberOf.loc);
    var tloc = members[i].memberOf.loc.file + ":" + members[i].memberOf.loc.line.toString();

    if (!/.*\/dist\/include.*/.exec(members[i].loc.file) && srcRegex.test(members[i].loc.file)) {
      // if this is static, ignore the reported decl in the compilation unit.
      // .isStatic will only be reported in the containing compilation unit.
//      if (!members[i].isStatic) {
        fix_path(members[i].loc);
        var loc = members[i].loc.file + ":" + members[i].loc.line.toString();
        var mvalue = members[i].value || ''; // enum members have a value
      var mstatic = members[i].isStatic ? 1 : -1;
        if (!members[i].isFunction || (members[i].isFunction && members[i].isExtern)) {
          // This is being seen via an #include vs. being done here in full, so just get decl loc
          var mshortname = m.mname.replace(/\(.*$/, '');
          sql.push(insert_stmt("members", ['mtname','mtloc','mname','mshortname','mdecl','mvalue','maccess','mstatic'], [m.mtname,tloc,m.mname,mshortname,loc,mvalue,members[i].access,mstatic]));
        } else {
          // This is an implementation, not a decl loc, update def (we'll get decl elsewhere)
          var update = "update or abort members set mdef=" + quote(loc);
          update += " where mtname=" + quote(m.mtname) + " and mtloc=" + quote(tloc) + " and mname=" + quote(m.mname) + ";";
          sql.push(update);
        }
//      }
    }
  }
}

function parse_name(c) {
  var result = {};

  // TODO: not working yet, but need to move this way...
  if (c.memberOf) {
    // Try and do this using member type info if possible
    result.mtname = c.memberOf.name;
    result.mname = c.name.replace(c.memberOf.name, '');
    result.mname = result.mname.replace(/^::/, '');      
  } else {

    // Fallback to regex used to split type::member (if only it were that simple!)
    var m = /^(?:[a-zA-Z0-9_]* )?(?:(.*)::)?([^:]+(\(.*\)( .*)?)?)$/.exec(c.name).slice(1, 3);
    result.mtname = m[0];
    result.mname = m[1];

  }

  return result;
}

function fix_path(loc) {
  // loc is {file: 'some/path', line: #, column: #}.  Normalize paths as follows:
  // from: /home/dave/gcc-dehydra/installed/bin/../lib/gcc/x86_64-unknown-linux-gnu/4.3.0/../../../../include/c++/4.3.0/exception:59
  // to:   /home/dave/gcc-dehydra/installed/include/c++/4.3.0/exception:59

  if (!loc)
    return;

  //ignore first slash
  var parts = loc.file.split("/").reverse();
  var fixed;
  var skip = 0;

  for (var i = 0; i < parts.length; i++) {
    if (parts[i] == "..") {
      skip++;
      continue;
    }

    if (skip == 0) {
      if (i == 0)
        fixed = parts[i];
      else
        fixed = parts[i] + "/" + fixed;
    } else {
      skip--;
    }
  }
  loc.file = fixed;
}

function insert_stmt(table, cols, vals) {
  var stmt = "insert or abort into " + table;
  if (cols) stmt += " " + build_list(cols);
  stmt += " values" + build_list(vals) + ";";
  return stmt;
}

function build_list(a) {
  var l = "(";
  for (var i = 0; i < a.length; i++) {
    l += quote(a[i]);
    if (i < a.length - 1)
      l += ",";
  }
  l += ")";
  return l;
}

function quote(s) {
  return "'" + s + "'";
}
