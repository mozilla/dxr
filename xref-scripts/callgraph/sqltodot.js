let Ci = Components.interfaces;
let Cc = Components.classes;

parseDB(arguments[0], arguments[1], arguments[2]);

function parseDB(inFile, outFile, prefix) {
  let edges = [];

  let ss = Cc["@mozilla.org/storage/service;1"].getService(Ci.mozIStorageService);
  let db = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsILocalFile);
  db.initWithPath(inFile);

  let conn = ss.openDatabase(db);
  let edge = conn.createStatement("SELECT * FROM edge");
  while (edge.executeStep()) {
    let caller = edge.row.caller;
    let callee = edge.row.callee;

    let nodeCaller = conn.createStatement("SELECT name, loc FROM node WHERE id = :id");
    nodeCaller.params.id = caller;
    nodeCaller.executeStep();

    let nodeCallee = conn.createStatement("SELECT name, loc FROM node WHERE id = :id");
    nodeCallee.params.id = callee;
    nodeCallee.executeStep();

    let edgeStr = '"' + nodeCaller.row.name + '\\n(' + strip(nodeCaller.row.loc, prefix) + ')" -> "' +
                        nodeCallee.row.name + '\\n(' + strip(nodeCallee.row.loc, prefix) + ')";';
    edges.push(edgeStr);
  }

  let dot = "digraph callgraph {\n";
  for each (edge in edges) {
    dot += "  " + edge + "\n";
  }
  dot += "}\n";

  let dotFile = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsILocalFile);
  dotFile.initWithPath(outFile);
  var stream = Cc["@mozilla.org/network/file-output-stream;1"].createInstance(Ci.nsIFileOutputStream);
  stream.init(dotFile, -1, -1, 0);
  stream.write(dot, dot.length);
  stream.close();
}

function strip(path, prefix) {
  if (path.substr(0, prefix.length) == prefix)
    return path.substr(prefix.length, path.length - prefix.length);
  return path;
}
