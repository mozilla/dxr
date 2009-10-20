dojo.require("dijit.TooltipDialog");
dojo.require("dijit.layout.TabContainer");
dojo.require("dojo.dnd.Moveable");

// note: virtroot, tree are defined in the .html file

function showPopup(node) {
  var name = node.innerHTML;
  var type = node.className;
  var line = node.parentNode.id.replace('l', '');
  var file = location.pathname.replace(virtroot + '/' + tree + '/', '').replace('.html', '');
  var url = virtroot + "/getinfo.cgi?virtroot=" + virtroot + "&tree=" + tree

  // put back the tooltip connector image and remove old highlight (if any)
  dojo.query(".dijitTooltipConnector").style("display", "inline");
  dojo.query(".sidebar-highlighted").removeClass("sidebar-highlighted");
  dojo.query(".highlighted").removeClass("highlighted");

  if (type == 's' || type == 's-fuzzy')  // statements have matching line number
    url += "&type=" + type + "&name=" + name + "&file=" + file  + "&line=" + node.getAttribute("line").replace('l','');
  else
    url += "&type=" + type + "&name=" + name;

  var ttd = dijit.byId("ttd");
  var e = dojo.connect(ttd, "onDownloadEnd", function () {
    var ttd_dnd = new dojo.dnd.Moveable('ttd', {handle: 'titlebar'});
    var ofm = dojo.connect(ttd_dnd, "onFirstMove", function(mover) {
      // If the user drags the dialog away from the link, remove the connector
      var s = mover.node.style;
      var xy = dojo.coords('ttd');
      dojo.style("ttd", {
        position: "absolute",
        top: xy.y + "px",
        left: xy.x  + "px"
      });

      dojo.query(".dijitTooltipConnector").style("display", "none");
      dojo.disconnect(ofm);
    });

    dojo.disconnect(e);
  });
  ttd.attr("href", url);

  dijit.popup.open({
    popup: ttd,
    around: node,
    onCancel: function(){
      dijit.popup.close(ttd);
      dojo.query(".highlighted").removeClass("highlighted");
    }
  });
  location.hash = line + '/' + name;
  dojo.addClass(node, "highlighted");
}

function init() {
  if (!location.hash) {
    dojo.byId('search-box').focus();
    return;
  }

  // hash may have line number, or line number + name separated by /
  var parts = location.hash.split('#')[1].split('/');

  if (parts[0]) {
    var l;
    // Deal with #l323 vs. #323
    if (/^l\d+/(parts[0]))
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
          setTimeout(function() { showPopup(children[i]); }, 0);
          break;
        }
      }
    } else {
      dojo.addClass(l, 'highlighted');
    }
  }
}

dojo.addOnLoad(function() {
  dojo.connect(dojo.body(), "onclick", function(e) {
    if (e.target.nodeName == 'A') {
      var link = e.target;

      if (link.getAttribute("aria-haspopup")) {
        e.preventDefault();
        showPopup(link);
      } else if (link.className == 'sidebarlink') {
        // Clicked outline link in sidebar, highlight link + line, close popup (if open)
        dojo.query(".sidebar-highlighted").removeClass("sidebar-highlighted");
        dojo.query(".highlighted").removeClass("highlighted");
        dojo.addClass(link, "sidebar-highlighted");
        dijit.popup.close(dijit.byId("ttd"));
        dojo.addClass(dojo.byId(link.href.split('#')[1]), 'highlighted');
      } else if (link.href && link.href.split('#')[0] == location.href.split('#')[0]) {
        // Link in same file, remove connector in popup, highlight line
        dojo.query(".highlighted").removeClass("highlighted");
        dojo.addClass(dojo.byId(link.href.split('#')[1]), 'highlighted');
        dojo.query(".dijitTooltipConnector").style("display", "none");
      }
    }
  });

  init();
});
