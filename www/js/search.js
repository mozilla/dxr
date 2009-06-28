function doSearch(id) {
  var f = document.getElementById(id);
  var treename = this.tree || document.getElementById('trees').value;
  var args = f.string.value.split(/ +/);
  var string = "";
  var url = virtroot + '/search.cgi?tree=' + treename;

  for (var i = 0; i < args.length; i++) {
    var arg = args[i];

    if (/^path:.+/(arg))
      url += "&path=" + encodeURIComponent(/^path:(.+)/.exec(arg).slice(1,2));
    else if (/^ext:.+/(arg))
      url += "&ext=" + encodeURIComponent(/^ext:(.+)/.exec(arg).slice(1,2));
    else if (/^type:.+/(arg))
      url += "&type=" + encodeURIComponent(/^type:(.+)/.exec(arg).slice(1,2));
    else if (/^member:.+/(arg))
      url += "&member=" + encodeURIComponent(/^member:(.+)/.exec(arg).slice(1,2));
    else if (/^derived:.+/(arg))
      url += "&derived=" + encodeURIComponent(/^derived:(.+)/.exec(arg).slice(1,2));
    else if (/^callers:.+/(arg))
      url += "&callers=" + encodeURIComponent(/^callers:(.+)/.exec(arg).slice(1,2));
    else if (/^macro:.+/(arg))
      url += "&macro=" + encodeURIComponent(/^macro:(.+)/.exec(arg).slice(1,2));
    else {
      string += arg + " ";
      continue;
    }
  }

  if (string.length > 0) {
    string = string.substring(0, string.length-1);
    if (/^\/.+\/$/(string)) {
      string = string.substring(1, string.length-1);
      url += "&regexp=on";
    }
    url += "&string=" + encodeURIComponent(string);
  }

  url = url.replace(/\&/g, '&amp;');
  window.location = url;
  return false;
}
