include("beautify.js");

function process_js(ast) {
  _print('// process_js');
  _print(js_beautify(uneval(ast))
    .replace(/op: (\d+),/g,
        function (hit, group1) {
          return 'op: ' + decode_op(group1) + '(' + group1 + '),'
        })
    .replace(/type: (\d+),/g,
        function (hit, group1) {
          return 'type: ' + decode_type(group1) + '(' + group1 + '),'
        })
    .replace(/{/g, '<span>{')
    .replace(/}/g, '}</span>'));
}

var global = this;
var optable = null, toktable;
function decode_op(opcode) {
  if (!optable) {
    optable = [];
      for (let key in global) {
	if (key.indexOf("JSOP_") == 0) {
	  optable[global[key]] = key;
	}
      }
  }
  if (opcode in optable)
    return optable[opcode];
  return opcode;
}

function decode_type(opcode) {
  if (!toktable) {
    toktable = [];
    for (let key in global) {
      if (key.indexOf("TOK_") == 0) {
	toktable[global[key]] = key;
      }
    }
  }
  if (opcode in toktable)
    return toktable[opcode];
  return opcode;
}
