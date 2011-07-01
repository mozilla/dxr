dojo.require("dojo.data.ItemFileReadStore");
dojo.require("dijit.tree.ForestStoreModel");
dojo.require("dojox.layout.ContentPane");
dojo.require("dijit.Tree");
dojo.require("dojo.fx");

// note: virtroot, tree, and this.ranges are defined in the .html file

var infoDiv,
    infoDivID = 0,
    currentLine,
    signature,
    maincontent,
    sep = '/',
    signatureVisible = false;

function closeInfo() {
  if (!infoDiv) {
    return;
  }
  dojo.query(".highlighted").removeClass("highlighted");
  dojo.fx.wipeOut({ node: infoDiv.id,
                    duration: 500,
                  }).play();
  infoDiv = null;
}

function showInfo(node) {
  var name = node.textContent;
  var line = node.parentNode.id.replace('l', '');
  var file = location.pathname.replace(virtroot + '/' + tree + '/', '').replace('.html', '');
  var url = virtroot + sep + "getinfo.cgi?virtroot=" + virtroot;
  url += "&tree=" + tree + "&div=" + infoDivID++;
  url += "&type=" + node.className + "&name=" + name;
  var attrs = node.attributes;
  for (var i = 0; i < attrs.length; i++) {
    var aname = attrs[i].name;
    var value = attrs[i].value;
    if (aname == 'class' || aname == 'aria-haspopup' || aname == 'href')
      continue;
    url += '&' + aname + '=' + encodeURIComponent(value);
  }

  if (infoDiv) {
    closeInfo();
  }

  var id = 'info-div-' + infoDivID;
  infoDiv = new dojox.layout.ContentPane({
              id: id,
              style: "margin:0; padding:0; white-space: normal !important;"
  });
  var lineDiv = node.parentNode;
  while (lineDiv.nodeName != 'DIV') lineDiv = lineDiv.parentNode;
  infoDiv.placeAt(lineDiv, "after");
  infoDiv.attr('href', url); //"/dxr/getinfo2.cgi?tree-id=" + ); // /dxr/info-test.html?id=" + infoDivID);
  location.hash = line + '/' + name;
  dojo.addClass(node, 'highlighted');

  // TODO: this needs to happen in an onLoad or onDownloadEnd event vs. here...
  dojo.fx.wipeIn({node: infoDiv.id, duration: 500}).play();
}

function init() {
  signature = dojo.byId('signature');
  maincontent = dojo.byId('maincontent');
  signatureVisible = false;

  if (!location.hash) {
    dojo.byId('search-box').focus();
    return;
  }

  // hash may have line number, or line number + name separated by /
  var parts = location.hash.split('#')[1].split('/');
  if (parts[0]) {
    var l;
    // Deal with #l323 vs. #323
    if (/^l\d+/.exec(parts[0]))
      l = dojo.byId(parts[0]);
    else
      l = dojo.byId('l' + parts[0]);
    l.scrollIntoView();

    if (parts[1] && l.hasChildNodes()) {
      var children = l.childNodes;
      for (var i = 0; i < children.length; i++) {
        // TODO: what about case of multiple items in line with same name?
        if (children[i].innerHTML == parts[1]) {
          // XXX: what's up with this, dojo?
          setTimeout(function() { showInfo(children[i]); }, 0);
          break;
        }
      }
    } else {
      dojo.addClass(l, 'highlighted');
    }
  }

  // Figure out the right path separator to use with virtroot
  sep = virtroot[virtroot.length - 1] === '/' ? '' : '/';
}

// Given a line number, try to find the ID for the containing function in the sidebar.
function findSidebarItem(line) {
  var ranges = this.ranges;
  if (!ranges || !ranges.length) {
    return;
  }

  var l=0, r=ranges.length - 1, c;
  while(l < r) {
    c = Math.ceil((l + r) / 2);
    if (line < ranges[c].start) { 
      r = c - 1; 
    } else {
      l = c;
    }
  }

  if (ranges[l].start <= line && line <= ranges[l].end) { 
    return ranges[l];
  }

  return null;
}

// See if this is a line div, e.g., <div id="l567">
function isLineDiv(node) {
  return (node.nodeName === 'DIV' && /l\d+/.exec(node.id));
}

function hideSignature() {
  dojo.fadeOut({node: signature}).play();
  signatureVisible = false;	
}

function showSignature() {
  if (!currentLine) {
    return;
  }

  var sidebarItem = findSidebarItem(currentLine);
  if (!sidebarItem) {
    if (signatureVisible) {
      hideSignature();
    }
    return;
  }

  if (!signatureVisible) {
    dojo.fadeIn({node: signature}).play();
    signatureVisible = true;
  }

  signature.innerHTML = sidebarItem.loc + ' ' + sidebarItem.sig;
  dojo.style(signature, { top: maincontent.scrollTop + "px"});
}

function hoverLine(node) {
  // Indicate the current source line
  dojo.query(".lni").removeClass("lni");
  dojo.addClass(node, "lni");

  // Try to indicate in the sidebar where we are now (e.g., which function).
  dojo.query(".sidebar-highlighted").removeClass("sidebar-highlighted");
  currentLine = node.id.replace('l', '');

  var sidebarItem = findSidebarItem(currentLine);
  if (!sidebarItem) {
    return;
  }
 
  var sb = dojo.byId(sidebarItem.sid);
  if (sb) {
    sb.scrollIntoView();
    dojo.addClass(sb, 'sidebar-highlighted');
  }
}

function buildTree(items, id) {
  var store = new dojo.data.ItemFileReadStore({
    data: { label: 'label',
            items: [items] }
  });

  var treeModel = new dijit.tree.ForestStoreModel({
    store: store
  });

  var treeControl = new dijit.Tree({
    model: treeModel,
    showRoot: false,
      onClick: function(item, node) { if (item.url) {
        window.location = item.url; } },
    getIconClass: function(item, opened) { return item.icon || 'icon-type'; }
/*,
            _createTreeNode: function(args) {
//                if (!once) { alert(args.label); once = true; }
                var tnode = new dijit._TreeNode(args);
                tnode.labelNode.innerHTML = args.label;
                return tnode;
            }
*/
  },id);
}

dojo.addOnLoad(function() {
  // TODO: deal with sidebar being absent
  var maincontent = dojo.byId('maincontent');

  dojo.connect(maincontent, "onmouseout", function(e) {
    hideSignature();
  });

  dojo.connect(maincontent, "onmouseover", function(e) {
    showSignature();

    var node = e.target;
    var parentID = node.parentNode.id;

    // Indicate which line we're hovering
    if (isLineDiv(node)) {
      hoverLine(node);
    } else if (isLineDiv(node.parentNode)) {
      hoverLine(node.parentNode); 
    }

    // Build an HREF url for anchor links dynamically.
    if (e.target.nodeName === 'A') { 
      if (node.getAttribute('href')) {
        return; // If the link already has an href, bail, otherwise build one
      }

      var url = location.href.replace(location.hash, '');
      var name = node.innerHTML;
      var line = parentID.replace('l', '');

      node.setAttribute('href', url + '#' + line + '/' + name);
    }
  });

  dojo.connect(dojo.body(), "onclick", function(e) {
    if (e.target.nodeName === 'A') {
      var link = e.target;

      if (link.getAttribute("aria-haspopup")) {
        showInfo(link);
        e.preventDefault();
      } else if (link.className == 'sidebarlink') {
        // Clicked outline link in sidebar, highlight link + line, close info (if open)
	link.scrollIntoView();
        dojo.query(".sidebar-highlighted").removeClass("sidebar-highlighted");
        dojo.query(".highlighted").removeClass("highlighted");
        dojo.addClass(link, "sidebar-highlighted");
        closeInfo();
        dojo.addClass(dojo.byId(link.href.split('#')[1]), 'highlighted');
	// Remove signature if visible, or it will cover this
        hideSignature();	
      } else if (link.href && link.href.split('#')[0] == location.href.split('#')[0]) {
        // Link in same file, remove connector in popup, highlight line
        dojo.query(".highlighted").removeClass("highlighted");
        dojo.addClass(dojo.byId(link.href.split('#')[1]), 'highlighted');
      }
    } else if (isLineDiv(e.target)) {
        closeInfo();
    }
  });

  dojo.connect(dojo.body(), "onkeypress", function(e) {
    if (e.keyCode == dojo.keys.ESCAPE) {
      closeInfo();
      dojo.stopEvent(e);
    }
  });

  init();
});
