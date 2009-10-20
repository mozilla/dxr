/**
 * Dumps the tree of the ast rooted at the given point.
 */
function dump_ast(ast, prefix) {
	if (ast == null)
		return;
	if (!prefix)
		prefix = "";
	let str = prefix + "+ ";
	for (let key in ast) {
		if (key == 'column' || key == 'line' || key == 'kids')
			continue;
		let val = (key == 'op' ? decode_op(ast[key]) :
				key == 'type' ? decode_type(ast[key]) : ast[key]);
		str += key + ": " + val + "; ";
	}
	str += ast.line + ":" + ast.column;
	_print(str);
	prefix += " ";
	for each (let kid in ast.kids) {
		dump_ast(kid, prefix);
	}
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
