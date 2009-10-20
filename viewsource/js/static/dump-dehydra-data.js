include('./beautify.js');

function process_type(c)
{
  if (typeof process_type.counter == 'undefined')
    process_type.counter = 0;

  process_type.counter++;
  print("// BEGIN: process_type\nPARAM: c\n" + prettyPrint('processtype' + process_type.counter, c) + "\n// END: process_type\n\n");
}

function process_var(v)
{
  if (typeof process_var.counter == 'undefined')
    process_var.counter = 0;

  process_var.counter++;

  print("// BEGIN: process_var\nPARAM: v\n" + prettyPrint('processvar' + process_var.counter, v) + "\n// END: process_var\n\n");
}

function process_decl(v)
{
  if (typeof process_decl.counter == 'undefined')
    process_decl.counter = 0;

  process_decl.counter++;

  print("// BEGIN: process_decl\nPARAM: v\n" + prettyPrint('processdecl' + process_decl.counter, v) + "\n// END: process_decl\n\n");
}

function process_function(f, stmts)
{
  if (typeof process_function.counter == 'undefined')
    process_function.counter = 0;

  process_function.counter++;

  print("// BEGIN: process_function\nPARAM: f\n" + prettyPrint('processfunction' + process_function.counter, f) + "\n// PARAM: stmts\n" + prettyPrint('processfunctionstmts' + process_function.counter, stmts) + "\n// END: process_function\n\n");
}

function prettyPrint(prefix, o)
{
  return js_beautify(uneval(o))
    .replace(/(type: #(\d+)=)/g, '<dfn id="' + prefix + '-$2">$1</dfn>')
    .replace(/(#(\d+)=)/g, '<a name="' + prefix + '-$2">$1</a>')
    .replace(/(#(\d+))#/g, '"<a href="#' + prefix + '-$2">See Type $1</a>"')
    .replace(/{/g, '<span>{')
    .replace(/}/g, '}</span>');
}
