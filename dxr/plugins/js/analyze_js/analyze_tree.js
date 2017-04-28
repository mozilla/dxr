"use strict";
const path = require("path");
const fs = require('fs');

const walk = require("walk");
const minimatch = require("minimatch");

const analyzeFile = require("./analyze_file.js");

// First arg is 'node', then 'analyze_tree.js', then the source tree root.
const treeRoot = process.argv[2];
// Where to put the json analysis dumps.
const tempRoot = process.argv[3];
// Patterns for files to ignore.
const ignores = process.argv.slice(4);

// Ensure that the folder dir exists.
function ensurePath(dir) {
  let reconstruct = "";
  for (const portion of dir.split('/')) {
    reconstruct += portion + '/';
    try {
      fs.statSync(reconstruct);
    } catch (e) {
      fs.mkdirSync(reconstruct);
    }
  }
}

// Return whether to ignore the path.
function reduceIgnores(path, initial) {
  initial = initial || false;
  return ignores.reduce((disallow, glob) => disallow || minimatch(path, glob), initial);
}

function main() {
  let done = false;
    // Walk the tree, call analyzeFile on all the .js files.
  const walker = walk.walk(treeRoot);
    // Map path segment -> whether to ignore.
  const dirCache = new Map();
  function testSegments(path) {
    let reconstruct = "";
    for (const portion of path.split('/')) {
      reconstruct += portion + '/';
      if (dirCache.get(reconstruct) === undefined) {
        dirCache.set(reconstruct, reduceIgnores(reconstruct));
      } else if (dirCache.get(reconstruct) === true) {
        dirCache.set(path, true);
        break;
      }
    }
    return dirCache.get(path);
  }
  walker.on("file", (root, stat, next) => {
    const fullPath = path.join(root, stat.name);
    const pathSegment = path.relative(treeRoot, root);
        // Test each ignore pattern against the path, and make sure it ends in .js.
    const disallow = (reduceIgnores(fullPath, !/jsm?$/.test(stat.name))
                        || testSegments(pathSegment));
    if (!disallow) {
      const tempPath = path.join(tempRoot, pathSegment);
      ensurePath(tempPath);
      analyzeFile(fullPath,
                  path.join(pathSegment, stat.name),
                  path.join(tempPath, stat.name + '.data'));
    }
    next();
  });

  walker.on('end', () => done = true);

    // Do not exit until we are done.
  function wait() {
    if (!done) {
      setTimeout(wait, 100);
    }
  }
  wait();
}

main();
