dojo.require("dojo.data.ItemFileReadStore");
dojo.require("dijit.tree.ForestStoreModel");
dojo.require("dojox.layout.ContentPane");
dojo.require("dijit.Tree");
dojo.require("dojo.fx");

// note: virtroot, tree, and this.ranges are defined in the .html file

var infoDiv,
    currentRequest,
    currentLine,
    signature,
    maincontent,
    sep = '/',
    signatureVisible = false,
    styleRule = -1;

function isChar(c) {
  return 'A' <= c && c <= 'z'
}

function getWordAtOffset(text,offset) {
  if (text.length <= offset)
    return;

  var preoffset = offset;
  var postoffset = offset;
  while(preoffset && isChar(text[preoffset-1])) preoffset--;
  while(postoffset < text.length && isChar(text[postoffset])) postoffset++;

  return text.substring(preoffset, postoffset);
}

function getSearchURL(term) {
  return virtroot + '/search.cgi?tree=' + tree + '&string=' + encodeURIComponent(term);
}

function closeInfo() {
  if (!infoDiv) {
    return;
  }

  infoDiv.style.display = 'none';
  infoDiv.innerHTML = '';
}

function showInfoDiv(anchor_node, search_term, content, offset) {
  if (!infoDiv) {
    infoDiv = document.createElement('div');
    infoDiv.id = "infoBox";
    infoDiv.style.left = "3px";

    var parent = document.getElementById('code');
    parent.appendChild(infoDiv);
  }

  if (offset != -1)
    infoDiv.style.top = offset + "px";
  else
    infoDiv.style.top = (anchor_node.offsetTop + anchor_node.offsetHeight) + "px";
  div_content = '';

  if (search_term != null) {
    div_content += '<p>Search for "<a href="' + getSearchURL(search_term) + '">' + search_term + '</a>"...</p>';
  }

  if (content != null) {
    div_content += content;
  }

  infoDiv.innerHTML = div_content;
  infoDiv.style.display = 'block';
}

function toggleSubList(elem) {
  var child = elem.nextSibling;

  if (child.style.display == 'none') {
    child.style.display = 'block';
  } else {
    child.style.display = 'none';
  }
}

function jsonToList(content) {
  str = '<ul>';

  for (var pos in content) {
    var child = content[pos];

    str += '<li';

    if (child['url']) {
      str += '><a href="' + child['url'] + '">';
    } else {
      str += ' class="listHeader" onclick="toggleSubList(this);">';
    }

    if (child['icon']) {
      str += '<p class="' + child['icon'] + '">';
    } else {
      str += '<p>';
    }

    str += child['label'];

    /* Indicate this is a list header */
    if (!child['url']) {
      str += ':';
    }

    str += '</p>';

    if (child['url']) {
      str += '</a>';
    }

    str += '</li>';

    if (child['children']) {
      str += jsonToList(child['children']);
    }
  }
  
  str += '</ul>';
  return str;
}

function jsonToHtml(content) {
  str = '<div id="infoHeader"><p>' + content['label'] + '</p></div>';

  if (content['children']) {
    str += jsonToList(content['children']);
  }
  
  return str;
}

function asyncRequestFinished() {
  if (req.readyState == 4 && req.status == 200) {
    if (req.responseText[0] == '<') {
      // embedded HTML response
      showInfoDiv(req.anchor_node, req.anchor_node.innerHTML, req.responseText, -1);
      currentRequest = null;
    } else {
      data = eval("(" + req.responseText + ")");
      showInfoDiv(req.anchor_node, req.anchor_node.innerHTML, jsonToHtml(data), - 1);
    }
  }
}

function asyncRequest(url, anchor_node) {
  if (currentRequest) {
    currentRequest.abort();
    currentRequest = null;
  }

  req = new XMLHttpRequest();
  req.onreadystatechange = asyncRequestFinished;
  req.anchor_node = anchor_node;

  try {
    req.open("GET", url, true);
    req.send(null);
    currentRequest = req;
  } catch (e) {
    showInfoDiv(anchor_node, null, "Could not retrieve reference data", -1);
  }
}

function queryInfo(node) {
  var name = node.textContent;
  var file = location.pathname.replace(virtroot + '/' + tree + '/', '').replace('.html', '');
  var url = virtroot + sep + "getinfo.cgi?virtroot=" + virtroot;
  url += "&tree=" + tree;
  url += "&type=" + node.className + "&name=" + name;
  var attrs = node.attributes;
  for (var i = 0; i < attrs.length; i++) {
    var aname = attrs[i].name;
    var value = attrs[i].value;
    if (aname == 'class' || aname == 'aria-haspopup' || aname == 'href')
      continue;
    url += '&' + aname + '=' + encodeURIComponent(value);
  }

  showInfoDiv (node, node.innerHTML, "Loading...", -1);
  asyncRequest(url, node);
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

function isEqualOrDescendant(parent, child) {
     var elem = child;

     while (elem != null) {
         if (elem == parent) {
             return true;
         }

         elem = elem.parentNode;
     }

     return false;
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
  });

  dojo.connect(dojo.body(), "onclick", function(e) {
    var target = e.target;

    if (infoDiv != null &&
        infoDiv.style.display == 'block' &&
        !isEqualOrDescendant(infoDiv, target)) {
      closeInfo();
      e.preventDefault();
      return;
    }

    if ((target.nodeName == 'DIV' && target.id == 'code') ||
        (target.nodeName == 'SPAN' && target.className != 'k' && target.className != 'p')) {
      var s = window.getSelection();

      if (s.anchorNode) {
        word = getWordAtOffset(s.anchorNode.nodeValue, s.focusOffset);

        if (word.length > 0)
          showInfoDiv(target, word, null, e.layerY + 15);
        return;
      }
    }

    while (target.nodeName === 'SPAN') target = target.parentNode;
    if (target.nodeName === 'A' && e.button == 0) {
      var link = target;

      if (link.getAttribute("aria-haspopup")) {
        queryInfo(link);
        e.preventDefault();
      } else if (link.className == 'sidebarlink') {
        // Clicked outline link in sidebar, highlight link + line, close info (if open)
        link.scrollIntoView();
        dojo.query(".sidebar-highlighted").removeClass("sidebar-highlighted");
        dojo.addClass(link, "sidebar-highlighted");
        closeInfo();
        // Remove signature if visible, or it will cover this
        hideSignature();
      }
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

function paneVisibility() {
  var img = document.getElementById(paneVisibility.img_id);
  var pane = document.getElementById(paneVisibility.pane_id);

  if (paneVisibility.visible == true) {
    pane.style.display = 'block';
    img.src = '/images/icons/bullet_toggle_minus.png';
    img.title = 'Hide type list';
  } else {
    pane.style.display = 'none';
    img.src = '/images/icons/bullet_toggle_plus.png';
    img.title = 'Show type list';
  }

  dijit.byId('bc').resize();
}

function toggleLeftPaneVisibility() {
  paneVisibility.visible = !paneVisibility.visible;
  paneVisibility();
}

function initLeftPane(img_id, pane_id, visible) {
  paneVisibility.img_id = img_id;
  paneVisibility.pane_id = pane_id;
  paneVisibility.visible = visible;

  paneVisibility();
}
