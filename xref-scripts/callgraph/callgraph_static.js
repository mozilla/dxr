require({ after_gcc_pass: "cfg" });
include('gcc_util.js');
include('gcc_print.js');
include('unstable/lazy_types.js');
include('unstable/dehydra_types.js');

let DEBUG = false;

let edges = [];
let virtuals = [];

function input_end() {
  let serial = serialize_edges(edges);
  serial += serialize_virtuals(virtuals);
  write_file(sys.aux_base_name + ".cg.sql", serial);
}

function serialize_edges(edges) {
  // array of edges, each edge looks like so:
  // { caller: { fn: "fn", rt: "rt", loc: "file" },
  //   callee: { fn: "fn", rt: "rt", loc: "file" } }
  // serialize two nodes and an edge using sql INSERT statements.
  let serial = "";
  for each (edge in edges) {
    serial += push_node(edge.caller);
    serial += push_node(edge.callee);
    serial += push_edge(edge);
    serial += '\n';
  }
  return serial;
}

function serialize_virtuals(virtuals) {
  let serial = "";
  for each (tuple in virtuals) {
    serial += 'INSERT INTO implementors (implementor, interface, method, loc) VALUES ("' +
                serialize_class(tuple.implementor) + '", "' +
                serialize_class(tuple.interface) + '", "' +
                serialize_method(tuple.implementor) + '", "' +
                tuple.interface.loc +
              '");\n';
  }
  return serial;
}

function serialize_full_method(method) {
  return method.rt + " " + serialize_class(method) + "::" + serialize_method(method);
}

function serialize_method(method) {
  return method.method + "(" + method.params.join(",") + ")";
}

function serialize_class(method) {
  return (method.ns ? (method.ns + "::") : "") +
         (method.class ? method.class : "");
}

function serialize_boolean(bool) {
  return bool ? "1" : "0";
}

function ensure_string(str) {
  return (str || '');
}

function push_node(node) {
  return 'INSERT INTO node (name, returnType, namespace, type, shortName, isPtr, isVirtual, loc) VALUES ("' +
           serialize_full_method(node) + '", "' +
           ensure_string(node.rt) + '", "' +
           ensure_string(node.ns) + '", "' +
           ensure_string(node.class) + '", "' +
           ensure_string(node.method) + '", ' +
           serialize_boolean(node.isPtr) + ', ' +
           serialize_boolean(node.isVirtual) + ', "' +
           node.loc +
         '");\n';
}

function push_edge(edge) {
  return 'INSERT INTO edge (caller, callee) VALUES (' +
           '(SELECT id FROM node WHERE name = "' + serialize_full_method(edge.caller) +
             '" AND loc = "' + edge.caller.loc + '"), ' +
           '(SELECT id FROM node WHERE name = "' + serialize_full_method(edge.callee) +
             '" AND loc = "' + edge.callee.loc + '")' +
         ');\n';
}

function process_tree_type(t) {
  // scan the class, and its bases, for virtual functions
  if (!COMPLETE_TYPE_P(t))
    return;

  // check if we have a class or struct
  let kind = class_key_or_enum_as_string(t);
  if (kind != "class" && kind != "struct")
    return;

  // for each member method...
  for (let func = TYPE_METHODS(t); func; func = TREE_CHAIN(func)) {
    if (TREE_CODE(func) != FUNCTION_DECL)
      continue;

    if (DECL_ARTIFICIAL(func)) continue;
    if (DECL_CLONED_FUNCTION_P(func)) continue;
    if (TREE_CODE(func) == TEMPLATE_DECL) continue;

    if (DECL_PURE_VIRTUAL_P(func) || !DECL_VIRTUAL_P(func))
      continue;

    // ignore destructors here?

    // have a class method. pull the namespace and class names.
    let implementor = get_names(func);
    debug_print("impl: " + serialize_full_method(implementor));

    // have a nonpure virtual member function...
    // which could potentially be implemented by this class.
    // scan subclasses to find which ones declare it.
    process_subclasses(t, implementor);
  }
}

function get_names(decl) {
  // for a class, names.class and names.method will be defined.
  // for a function, names.method will be defined.
  // for either, names.ns may be defined depending on whether the context is a namespace.
  // for a fnptr, there will be no namespace, class name, or method name -
  // just a return type and params.
  let names = {};

  let fn = TREE_CODE(TREE_TYPE(decl)) == FUNCTION_TYPE ||
           TREE_CODE(TREE_TYPE(decl)) == METHOD_TYPE;
  if (!fn)
    throw new Error("decl is not a function!");

  // check if we have a function pointer.
  let fnptr = TREE_CODE(decl) == POINTER_TYPE;
  if (fnptr)
    names.isPtr = true;

  // return type name
  names.rt = type_string(TREE_TYPE(TREE_TYPE(decl)));

  // XXX ptr to member?
  // see http://tuvix.apple.com/documentation/DeveloperTools/gcc-4.2.1/gccint/Expression-trees.html PTRMEM_CST

  // namespace and class name. but if this is a fnptr, there is no context to be had...
  if (!fnptr) {
    // we have a function or method.
    let context = DECL_CONTEXT(decl);
    if (context) {
      // resolve the file loc to a unique absolute path, with no symlinks.
      // use the context here since the declaration will be unique.
      names.loc = location_string(context);

      let have_class = TYPE_P(context);
      if (have_class)
        context = TYPE_NAME(context);

      let array = context.toCString().split("::");
      if (array.length == 0)
        throw new Error("no context!");

      if (have_class) {
        // have a class or struct. last element in the array is the class name,
        // and everything before are the namespaces.
        names.class = array.pop();
        if (names.class.length == 0)
          throw new Error("no class name!");
      }
      if (array.length > 0) {
        // the rest are namespaces.
        names.ns = array.join("::");
      }
    } else {
      // resolve the file loc to a unique absolute path, with no symlinks.
      // have no context, so use what we've got
      names.loc = location_string(decl);
    }

    // XXX for has_this: DECL_NONSTATIC_MEMBER_FUNCTION_P
    // XXX for class ctx (incl enum/union/struct) see gcc_compat.js:class_key_or_enum_as_string(t)

    // method name
    let name = DECL_NAME(decl);
    if (name) {
      // if we have a cloned constructor/destructor (e.g. __comp_ctor/
      // __comp_dtor), pull the original name
      if (DECL_LANG_SPECIFIC(decl) && DECL_CONSTRUCTOR_P(decl)) {
        names.method = names.class;
      } else if (DECL_LANG_SPECIFIC(decl) && DECL_DESTRUCTOR_P(decl)) {
        names.method = "~" + names.class;
      } else if (DECL_LANG_SPECIFIC(decl) && IDENTIFIER_OPNAME_P(name) && IDENTIFIER_TYPENAME_P(name)) {
        // type-conversion operator, e.g. |operator T*|. gcc assigns a random name
        // along the lines of |operator 11|, so come up with something more useful.
        names.method = "operator " + type_string(TREE_TYPE(name));
      } else {
        // usual case.
        names.method = IDENTIFIER_POINTER(name);
      }

      if (DECL_VIRTUAL_P(decl))
        names.isVirtual = true;

      //names.push(DECL_UID(decl)); // UID of method
    }

    if (!names.loc)
      throw new Error("should have a loc by now!");

  } else {
    // provide something sensible for fnptrs.
    names.method = "(*)";
    names.loc = "";
  }

  // parameter type names
  let type = TREE_TYPE(decl);
  let args = TYPE_ARG_TYPES(type);
  if (TREE_CODE(type) == METHOD_TYPE) {
    // skip |this|
    args = TREE_CHAIN(args);
  }

  names.params = [ type_string(TREE_VALUE(pt))
                   for (pt in flatten_chain(args))
                     if (TREE_CODE(TREE_VALUE(pt)) != VOID_TYPE) ];

  return names;
}

function location_string(decl) {
  let loc = location_of(decl);
  if (loc == UNKNOWN_LOCATION)
    throw new Error("unknown location");

  if (LOC_IS_BUILTIN(loc))
    return "<built-in>";

  let path = loc.file;
  try {
    return resolve_path(path);
  } catch(e) {
    if (e.message.indexOf("No such file or directory")) {
      // this can occur if people use the #line directive to artificially override
      // the source file name in gcc. in such cases, there's nothing we can really
      // do, and it's their fault if the filename clashes with something.
      return path;
    }

    // something else happened - rethrow
    throw new Error(e);
  }
}

function process_subclasses(c, implementor) {
  let bases = [ BINFO_TYPE(base_binfo)
                for each (base_binfo in
                          VEC_iterate(BINFO_BASE_BINFOS(TYPE_BINFO(c)))) ];

  for each (base in bases) {
    // for each member method...
    for (let func = TYPE_METHODS(base); func; func = TREE_CHAIN(func)) {
      if (TREE_CODE(func) != FUNCTION_DECL)
        continue;

      if (DECL_ARTIFICIAL(func)) continue;
      if (DECL_CLONED_FUNCTION_P(func)) continue;
      if (TREE_CODE(func) == TEMPLATE_DECL) continue;

      if (!DECL_VIRTUAL_P(func))
        continue;

      // have a class method. pull the namespace and class names.
      let iface = get_names(func);
      debug_print("iface: " + serialize_full_method(iface));

      if (method_signatures_match(implementor, iface)) {
        let v = { "implementor": implementor, "interface": iface };
        virtuals.push(v);
      }
    }

    // scan subclass bases as well
    process_subclasses(base, implementor);
  }
}

function method_signatures_match(m1, m2) {
  return m1.method == m2.method &&
         m1.params.join(",") == m2.params.join(",") &&
         m1.rt == m2.rt;
}

function process_tree(fn) {
  debug_print("CALLER:      " + serialize_full_method(get_names(fn)));

  let cfg = function_decl_cfg(fn);
  for (let bb in cfg_bb_iterator(cfg)) {
    for (let isn in bb_isn_iterator(bb)) {
      walk_tree(isn, function(t, stack) {
        if (TREE_CODE(t) != CALL_EXPR)
          return;

        let callee = resolve_function_decl(t);
        if (!callee)
          throw new Error("unresolvable function " + expr_display(t));

        debug_print("  callee:    " + serialize_full_method(get_names(callee)));

        // serialize the edge
        let edge = { caller: {}, callee: {} };
        edge.caller = get_names(fn);
        edge.callee = get_names(callee);
        edges.push(edge);
      });
    }
  }
}

function resolve_function_decl(expr) {
  let r = CALL_EXPR_FN(expr);
  switch (TREE_CODE(r)) {
  case OBJ_TYPE_REF:
    return resolve_virtual_fun_from_obj_type_ref(r);
  case FUNCTION_DECL:
  case ADDR_EXPR:
    return call_function_decl(expr);
  case VAR_DECL:
  case PARM_DECL:
    // have a function pointer. the VAR_DECL holds the fnptr, but we're interested in the type.
    return TREE_TYPE(r);
  default:
    throw new Error("resolve_function_decl: unresolvable decl with TREE_CODE " + TREE_CODE(r));
  }
}

function debug_print(str) {
  if (DEBUG)
    print(str);
}

