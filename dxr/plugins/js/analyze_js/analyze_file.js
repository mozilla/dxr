"use strict";
const esprima = require('esprima');
const fs = require('fs');
const path = require('path');

let nextSymId, fileIndex, outLines;

// Write s out to the assigned temp file.
function emit(s) {
  outLines.push(s);
}

// Return whether loc1 begins before loc2.
function locBefore(loc1, loc2) {
  return loc1.start.line < loc2.start.line ||
         (loc1.start.line == loc2.start.line && loc1.start.column < loc2.start.column);
}

// Return string repr of location with given name.
function locstr(loc, name) {
  return `${loc.start.line}:${loc.start.column}-${loc.start.column + name.length}`;
}

// Return whether the name could be a valid symbol.
function nameValid(name) {
  return name.indexOf(" ") == -1 &&
         name.indexOf("\n") == -1 &&
         name.indexOf("\r") == -1 &&
         name.indexOf("\0") == -1 &&
         name.indexOf("\\") == -1 &&
         name.indexOf('"') == -1;
}

// Fix the location attribute of the expr's member property, and return it.
function memberPropLoc(expr) {
  const idLoc = expr.loc;
  idLoc.start.line = idLoc.end.line;
  idLoc.start.column = idLoc.end.column - expr.property.name.length;
  return idLoc;
}


// A JS symbol with given name and source location.
function JSSymbol(name, loc) {
  this.name = name;
  this.loc = loc;
  // A tree-unique id for this symbol from the path and its number in the file.
  this.id = fileIndex + "-" + nextSymId++;
}


const Analyzer = {
  // Map name -> JSSymbol for each symbol used/defined in the current scope.
  symbols: new Map(),
  // Stack of symbols, where top of stack is symbol map of current scope.
  symbolTableStack: [],

  // The name of the "this" object in the current scope.
  nameForThis: null,

  // Enter a scope.
  enter() {
    this.symbolTableStack.push(this.symbols);
    this.symbols = new Map();
  },

  // Leave a scope. Do not exit() on global scope.
  exit() {
    const old = this.symbols;
    this.symbols = this.symbolTableStack.pop();
    return old;
  },

  // Return whether the analyzer is currently at global scope.
  isToplevel() {
    return this.symbolTableStack.length == 0;
  },

  // Enter a new scope, call f, then exit the scope.
  scoped(f) {
    this.enter();
    f();
    this.exit();
  },

  // Save nameForThis, set to newName, call f, then reset it.
  withNameForThis(newName, f) {
    const oldNameForThis = this.nameForThis;
    this.nameForThis = newName;
    f();
    this.nameForThis = oldNameForThis;
  },

  // Return the JSSymbol of the given name accessible from the current scope,
  // undefined if not found.
  findSymbol(name) {
    let sym = this.symbols.get(name);
    if (!sym) {
      for (let i = this.symbolTableStack.length - 1; i >= 0; i--) {
        sym = this.symbolTableStack[i].get(name);
        if (sym) {
          break;
        }
      }
    }
    return sym;
  },

  // Emit lines for a property definition in global scope.
  defPropGlobal(name, loc) {
    if (!nameValid(name)) {
      return;
    }
    emit(JSON.stringify({loc: locstr(loc, name), type: 'prop', kind: "def", name, sym: `#${name}`}));
  },

  // Emit lines for a property usage in global scope.
  usePropGlobal(name, loc) {
    if (!nameValid(name)) {
      return;
    }
    emit(JSON.stringify({loc: locstr(loc, name), kind: "use", name, type: "prop", sym: `#${name}`}));
  },

  // Define a qualified property.
  defProp(name, qualname, loc) {
    if (!nameValid(name)) {
      return;
    }
    emit(JSON.stringify({loc: locstr(loc, name), kind: "def", type: "prop", name, sym: qualname}));
  },

  // Use a qualified property.
  useProp(name, qualname, loc) {
    if (!nameValid(name)) {
      return;
    }
    emit(JSON.stringify({loc: locstr(loc, name), kind: "use", type: "prop", name, sym: qualname}));
  },

  // Emit lines for a variable definition.
  defVar(name, loc) {
    if (!nameValid(name)) {
      return;
    }
    if (this.isToplevel()) {
      this.defPropGlobal(name, loc);
      return;
    }
    const sym = new JSSymbol(name, loc);
    this.symbols.set(name, sym);

    emit(JSON.stringify({loc: locstr(loc, name), kind: "def", type: "var", name, sym: sym.id}));
  },

  // Emit lines for a variable usage.
  useVar(name, loc) {
    if (!nameValid(name)) {
      return;
    }
    const sym = this.findSymbol(name);
    if (!sym) {
      this.usePropGlobal(name, loc);
    } else {
      emit(JSON.stringify({loc: locstr(loc, name), kind: "use", name, type: "prop", sym: sym.id}));
    }
  },

  // Analyze every statement of the program body.
  program(prog) {
    for (const stmt of prog.body) {
      this.statement(stmt);
    }
  },

  // Analyze a statement, dispatching based on its type.
  statement(stmt) {
    switch (stmt.type) {
    case "EmptyStatement":
    case "BreakStatement":
    case "ContinueStatement":
    case "DebuggerStatement":
      break;

    case "BlockStatement":
      this.scoped(() => {
        for (const stmt2 of stmt.body) {
          this.statement(stmt2);
        }
      });
      break;

    case "ExpressionStatement":
      this.expression(stmt.expression);
      break;

    case "IfStatement":
      this.expression(stmt.test);
      this.statement(stmt.consequent);
      this.maybeStatement(stmt.alternate);
      break;

    case "LabeledStatement":
      this.statement(stmt.body);
      break;

    case "WithStatement":
      this.expression(stmt.object);
      this.statement(stmt.body);
      break;

    case "SwitchStatement":
      this.expression(stmt.discriminant);
      for (const scase of stmt.cases) {
        this.switchCase(scase);
      }
      break;

    case "ReturnStatement":
      this.maybeExpression(stmt.argument);
      break;

    case "ThrowStatement":
      this.expression(stmt.argument);
      break;

    case "TryStatement":
      this.statement(stmt.block);
      for (const guarded of stmt.guardedHandlers) {
        this.catchClause(guarded);
      }
      if (stmt.handler) {
        this.catchClause(stmt.handler);
      }
      this.maybeStatement(stmt.finalizer);
      break;

    case "WhileStatement":
      this.expression(stmt.test);
      this.statement(stmt.body);
      break;

    case "DoWhileStatement":
      this.statement(stmt.body);
      this.expression(stmt.test);
      break;

    case "ForStatement":
      this.scoped(() => {
        if (stmt.init && stmt.init.type == "VariableDeclaration") {
          this.variableDeclaration(stmt.init);
        } else if (stmt.init) {
          this.expression(stmt.init);
        }
        this.maybeExpression(stmt.test);
        this.maybeExpression(stmt.update);
        this.statement(stmt.body);
      });
      break;

    case "ForInStatement":
    case "ForOfStatement":
      this.scoped(() => {
        if (stmt.left && stmt.left.type == "VariableDeclaration") {
          this.variableDeclaration(stmt.left);
        } else {
          this.expression(stmt.left);
        }
        this.expression(stmt.right);
        this.statement(stmt.body);
      });
      break;

    case "LetStatement":
      this.scoped(() => {
        for (const decl of stmt.head) {
          this.variableDeclarator(decl);
        }
        this.statement(stmt.body);
      });
      break;

    case "FunctionDeclaration":
      this.defVar(stmt.id.name, stmt.id.loc);
      this.withNameForThis(stmt.id.name, () => {
        this.scoped(() => {
          for (let i = 0; i < stmt.params.length; i++) {
            this.pattern(stmt.params[i]);
            this.maybeExpression(stmt.defaults[i]);
          }
          if (stmt.rest) {
            this.defVar(stmt.rest.name, stmt.rest.loc);
          }
          if (stmt.body.type == "BlockStatement") {
            this.statement(stmt.body);
          } else {
            this.expression(stmt.body);
          }
        });
      });
      break;

    case "VariableDeclaration":
      this.variableDeclaration(stmt);
      break;

    case "ClassDeclaration":
      this.defVar(stmt.id.name, stmt.id.loc);
      this.withNameForThis(stmt.id.name, () => {
        this.scoped(() => {
          if (stmt.superClass) {
            this.expression(stmt.superClass);
          }
          this.expression(stmt.body);
        });
      });
      break;

    case "ClassMethod":
      this.expression(stmt.body);
      break;

    case "MethodDefinition":
      this.expression(stmt.key);
      this.expression(stmt.value);
      break;

    case "ExportNamedDeclaration":
      this.statement(stmt.declaration)
      break;

    default:
      console.warn(`In ${fileIndex}, Unexpected statement: ${stmt.type} ${JSON.stringify(stmt)}`);
      break;
    }
  },

  // Handle one or more variable declarations.
  variableDeclaration(decl) {
    for (const d of decl.declarations) {
      this.variableDeclarator(d);
    }
  },

  // Handle a single variable declaration.
  variableDeclarator(decl) {
    this.pattern(decl.id);
    // If the declaration is an object, then the LHS of the declaration is
    // "this" for the duration of the object initializer.
    if (decl.id.type == "Identifier" && decl.init && decl.init.type == "ObjectExpression") {
      this.withNameForThis(decl.id.name, () => {
        this.maybeExpression(decl.init);
      });
    } else {
      this.maybeExpression(decl.init);
    }
  },

  // If the optional statement is defined, then handle it.
  maybeStatement(stmt) {
    if (stmt) {
      this.statement(stmt);
    }
  },

  // If the optional expression is defined, then handle it.
  maybeExpression(expr) {
    if (expr) {
      this.expression(expr);
    }
  },

  switchCase(scase) {
    if (scase.test) {
      this.expression(scase.test);
    }
    for (const stmt of scase.consequent) {
      this.statement(stmt);
    }
  },

  catchClause(clause) {
    this.pattern(clause.param);
    if (clause.guard) {
      this.expression(clause.guard);
    }
    this.statement(clause.body);
  },

  // Handle an expression by dispatching based on its type.
  expression(expr) {
    if (!expr) console.warn(Error().stack);

    switch (expr.type) {
    case "Identifier":
      this.useVar(expr.name, expr.loc);
      break;

    case "Literal":
    case "Super":
      break;

    case "TaggedTemplate":
    case "TaggedTemplateExpression":
    case "ThisExpression":
      // TODO
      break;

    case "TemplateLiteral":
      if (expr.elemnts) {
        for (const elt of expr.elements) {
          this.expression(elt);
        }
      }
      break;

    case "ArrayExpression":
    case "ArrayPattern":
      for (const elt of expr.elements) {
        this.maybeExpression(elt);
      }
      break;

    case "ObjectExpression":
    case "ObjectPattern":
      for (const prop of expr.properties) {
        let name;

        if (prop.key) {
          let loc;
          if (prop.key.type == "Identifier") {
            name = prop.key.name;
            loc = prop.key.loc;
          } else if (prop.key.type == "Literal" && typeof(prop.key.value) == "string") {
            name = prop.key.value;
            loc = prop.key.loc;
            loc.start.column++;
          }
          let qualname = `##${name}`;
          if (this.nameForThis) {
            qualname = `${this.nameForThis}#${name}`;
          }
          if (name) {
            this.defProp(name, qualname, prop.key.loc);
          }
        }

        this.expression(prop.value);
      }
      break;

    case "FunctionExpression":
    case "ArrowFunctionExpression":
      this.scoped(() => {
        const name = expr.id ? expr.id.name : "";
        const loc = expr.id ? expr.id.loc : expr.loc;
        if (expr.type == "FunctionExpression" && name) {
          this.defVar(name, loc);
        }
        for (let i = 0; i < expr.params.length; i++) {
          this.pattern(expr.params[i]);
          this.maybeExpression(expr.defaults[i]);
        }
        if (expr.rest) {
          this.defVar(expr.rest.name, expr.rest.loc);
        }
        if (expr.body.type == "BlockStatement") {
          this.statement(expr.body);
        } else {
          this.expression(expr.body);
        }
      });
      break;

    case "SequenceExpression":
      for (const elt of expr.expressions) {
        this.expression(elt);
      }
      break;

    case "UnaryExpression":
    case "UpdateExpression":
      this.expression(expr.argument);
      break;

    // We have to repeat this case expression because it can appear as the
    // 'value' of an ObjectPattern which is otherwise an expression.
    case "AssignmentPattern":
      this.expression(expr.left);
      this.expression(expr.right);
      break;

    case "AssignmentExpression": {
      // For assignments we evaluate the RHS first because in a block such as
      // 1. let foo = 3;
      // 2. foo = foo + 1;
      // The foo on RHS of line 2 refers to foo of line 1.
      let newNameForThis = this.nameForThis;
      if (expr.left.type == "MemberExpression" && !expr.left.computed) {
        if (expr.left.property.name == "prototype" &&
            expr.left.object.type == "Identifier") {
          newNameForThis = expr.left.object.name;
        }
        if (expr.left.object.type == "ThisExpression") {
          newNameForThis = expr.left.property.name;
        }
      }
      this.withNameForThis(newNameForThis, () => {
        this.expression(expr.right);
      });

      if (expr.left.type == "Identifier") {
        this.defVar(expr.left.name, expr.left.loc);
      } else if (expr.left.type == "MemberExpression" && !expr.left.computed) {
        this.expression(expr.left.object);

        let qualname = `##${expr.left.property.name}`;
        if (expr.left.object.type == "ThisExpression" && this.nameForThis) {
          qualname = `${this.nameForThis}#${expr.left.property.name}`;
        } else if (expr.left.object.type == "Identifier") {
          qualname = `${expr.left.object.name}#${expr.left.property.name}`;
        }
        this.defProp(expr.left.property.name, qualname, memberPropLoc(expr.left));
      } else {
        this.expression(expr.left);
      }
      break;
    }

    case "BinaryExpression":
    case "LogicalExpression":
      this.expression(expr.left);
      this.expression(expr.right);
      break;

    case "ConditionalExpression":
      this.expression(expr.test);
      this.expression(expr.consequent);
      this.expression(expr.alternate);
      break;

    case "NewExpression":
    case "CallExpression":
      this.expression(expr.callee);
      for (const arg of expr.arguments) {
        this.expression(arg);
      }
      break;

    case "MemberExpression":
      this.expression(expr.object);
      if (expr.computed) {
        this.expression(expr.property);
      } else {
        let qualname = `##${expr.property.name}`;
        if (expr.object.type == "ThisExpression" && this.nameForThis) {
          qualname = `${this.nameForThis}#${expr.property.name}`;
        } else if (expr.object.type == "Identifier") {
          qualname = `${expr.object.name}#${expr.property.name}`;
        }

        this.useProp(expr.property.name, qualname, memberPropLoc(expr));
      }
      break;

    case "ClassBody":
      for (const stmt of expr.body) {
        this.statement(stmt);
      }
      break;

    case "YieldExpression":
    case "SpreadElement":
    case "RestElement":
      this.maybeExpression(expr.argument);
      break;

    case "SpreadExpression":
      this.expression(expr.expression);
      break;

    case "ComprehensionExpression":
    case "GeneratorExpression":
      this.scoped(() => {
        const before = locBefore(expr.body.loc, expr.blocks[0].loc);
        if (before) {
          this.expression(expr.body);
        }
        for (const block of expr.blocks) {
          this.comprehensionBlock(block);
        }
        this.maybeExpression(expr.filter);
        if (!before) {
          this.expression(expr.body);
        }
      });
      break;

    case "ClassExpression":
      this.scoped(() => {
        if (expr.superClass) {
          this.expression(expr.superClass);
        }
        if (expr.body.type == "BlockStatement") {
          this.statement(expr.body);
        } else {
          this.expression(expr.body);
        }
      });
      break;

    case "MetaProperty":
      // Not sure what this is!
      break;

    default:
      console.warn(Error().stack);
      console.warn(`In ${fileIndex}, Unexpected expression ${expr.type}: ${JSON.stringify(expr)}`);
      break;
    }
  },

  comprehensionBlock(block) {
    switch (block.type) {
    case "ComprehensionBlock":
      this.pattern(block.left);
      this.expression(block.right);
      break;

    case "ComprehensionIf":
      this.expression(block.test);
      break;
    }
  },

  // Handle a pattern-matching assignment by dispatching on type.
  pattern(pat) {
    if (!pat) {
      console.warn(Error().stack);
    }

    switch (pat.type) {
    case "Identifier":
      this.defVar(pat.name, pat.loc);
      break;

    case "ObjectPattern":
      for (const prop of pat.properties) {
        this.pattern(prop.value);
      }
      break;

    case "ArrayPattern":
      for (const e of pat.elements) {
        if (e) {
          this.pattern(e);
        }
      }
      break;

    case "SpreadExpression":
      this.pattern(pat.expression);
      break;

    case "RestElement":
      this.pattern(pat.argument);
      break;

    case "AssignmentPattern":
      this.expression(pat.left);
      this.expression(pat.right);
      break;

    default:
      console.warn(`In ${fileIndex}, Unexpected pattern: ${pat.type} ${JSON.stringify(pat)}`);
      break;
    }
  }
};

// Attempt to comment out some mozilla-specific preprocessor headers.
function preprocess(lines, comment)
{
  let substitution = false;
  const preprocessedLines = [];
  const branches = [true];
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    if (substitution) {
      line = line.replace(/@(\w+)@/, "''");
    }
    const tline = line.trim();
    if (tline.startsWith("#ifdef") || tline.startsWith("#ifndef") || tline.startsWith("#if ")) {
      preprocessedLines.push(comment(tline));
      branches.push(branches[branches.length-1]);
    } else if (tline.startsWith("#else") ||
               tline.startsWith("#elif") ||
               tline.startsWith("#elifdef") ||
               tline.startsWith("#elifndef")) {
      preprocessedLines.push(comment(tline));
      branches.pop();
      branches.push(false);
    } else if (tline.startsWith("#endif")) {
      preprocessedLines.push(comment(tline));
      branches.pop();
    } else if (!branches[branches.length-1]) {
      preprocessedLines.push(comment(tline));
    } else if (tline.startsWith("#include")) {
      /*
      let match = tline.match(/#include "?([A-Za-z0-9_.-]+)"?/);
      if (!match) {
        throw new Error(`Invalid include directive: ${filename}:${i+1}`);
      }
      let incfile = match[1];
      preprocessedLines.push(`PREPROCESSOR_INCLUDE("${incfile}");`);
      */
      preprocessedLines.push(comment(tline));
    } else if (tline.startsWith("#filter substitution")) {
      preprocessedLines.push(comment(tline));
      substitution = true;
    } else if (tline.startsWith("#filter")) {
      preprocessedLines.push(comment(tline));
    } else if (tline.startsWith("#expand")) {
      preprocessedLines.push(line.substring(String("#expand ").length));
    } else if (tline.startsWith("#")) {
      preprocessedLines.push(comment(tline));
    } else {
      preprocessedLines.push(line);
    }
  }

  return preprocessedLines.join('\n');
}

function analyzeJS(filepath, relpath, tempFilepath)
{
  fileIndex = relpath;
  nextSymId = 0;
  outLines = [];
  let text = String(fs.readFileSync(filepath));

  // Remove the things esprima considers line break characters but DXR doesn't.
  // This makes esprima's position reporting match DXR's so we don't try to
  // reach past the last line of the file when computing chars-from-BOF offsets.
  // We replace them with things that aren't line breaks but have equal length
  // so the computed positions work out and so tokenization doesn't change.
  // Then the user is still presented with the original file, but the offsets
  // of needles and refs are correct.
  text = text.replace(/[\u2028\u2029]/g, ' ');

  const lines = text.split('\n');
  // With files this large we currently risk running out of memory in the
  // indexer, so we skip them. TODO: fix the issue and disable this check.
  if (lines.length >= 100000) {
    console.warn(`Skipping ${filepath} because length of ${lines.length} exceeds limit.`);
    return;
  }
  try {
    const ast = esprima.parse(preprocess(lines, line => "//" + line),
                              {loc: true,
                               source: path.basename(filepath),
                               line: 1,
                               tolerant: true,
                               sourceType: "script"});
    if (ast) {
      Analyzer.program(ast);
    }
  } catch (e) {
    console.error(fileIndex, e.name, e.message);
  }
  fs.writeFileSync(tempFilepath, outLines.join('\n'));
}

module.exports = analyzeJS;

