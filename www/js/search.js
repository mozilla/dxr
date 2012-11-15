function getSearchUrlBase(tree, noredirect) {
  // Figure out the right path separator to use with virtroot
  sep = virtroot[virtroot.length - 1] === '/' ? '' : '/';
  var url = virtroot + sep + 'search.cgi?tree=' + tree;
  var date = new Date ();

  url += "&request_time=" + date.getTime ();

  if (noredirect == true) {
    url += "&noredirect=1"
  }

  return url;
}

function doSearch(id) {
  var f = document.getElementById(id);
  var args = f.string.value.split(/ +/);
  var string = "";

  var url = getSearchUrlBase (f.tree.value, false);

  for (var i = 0; i < args.length; i++) {
    var arg = args[i];

    if (/^path:.+/.exec(arg))
      url += "&path=" + encodeURIComponent(/^path:(.+)/.exec(arg).slice(1,2));
    else if (/^ext:.+/.exec(arg))
      url += "&ext=" + encodeURIComponent(/^ext:(.+)/.exec(arg).slice(1,2));
    else if (/^type:.+/.exec(arg))
      url += "&type=" + encodeURIComponent(/^type:(.+)/.exec(arg).slice(1,2));
    else if (/^member:.+/.exec(arg))
      url += "&member=" + encodeURIComponent(/^member:(.+)/.exec(arg).slice(1,2));
    else if (/^derived:.+/.exec(arg))
      url += "&derived=" + encodeURIComponent(/^derived:(.+)/.exec(arg).slice(1,2));
    else if (/^callers:.+/.exec(arg))
      url += "&callers=" + encodeURIComponent(/^callers:(.+)/.exec(arg).slice(1,2));
    else if (/^macro:.+/.exec(arg))
      url += "&macro=" + encodeURIComponent(/^macro:(.+)/.exec(arg).slice(1,2));
    else if (/^warnings:.*/.exec(arg)) {
      var warnings = /^warnings:(.*)/.exec(arg).slice(1,2);
      
      // see if user did warnings:<nothing>, meaning "show all warnings"
      if (warnings == '') 
          warnings = '*';

      url += "&warnings=" + encodeURIComponent(warnings);
    } else {
      string += arg + " ";
      continue;
    }
  }

  if (string.length > 0) {
    string = string.substring(0, string.length-1);
    if (/^\/.+\/$/.exec(string)) {
      string = string.substring(1, string.length-1);
      url += "&regexp=on";
    }
    url += "&string=" + encodeURIComponent(string);
  }

  window.location = url;
  return false;
}

function checkShowHintBox(form_id, div_id, link_id) {
  var url = window.location.href;
  var pattern = /string=([^&#]+)/;
  var match = url.match (pattern);
  var search = RegExp.$1;

  if (search.length > 0) {
    showHintBox(form_id, div_id, link_id, search);
  }
}


function showHintBox(form_id, id, link_id, string) {
  var form = document.getElementById(form_id)
  var div = document.getElementById(id);
  var link = document.getElementById(link_id);
  var url = getSearchUrlBase(form.tree.value, true);

  url += "&string=" + encodeURIComponent(string);

  link.textContent = string;
  link.href= url
  div.style.display = "block";
}

function hideHintBox(id) {
  var div = document.getElementById(id);
  div.style.display='none'
}
