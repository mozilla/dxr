// Parse commands from query string into search commands
function parseQS(id) {
  var qs = window.location.search.substring(1).replace(/\&amp;/g, '&').split('&');
  var search="";
  var string;
  var regexp = false;

  for (var i = 0; i < qs.length; i++) {
    var pair = qs[i].split("=");
    var s = decodeURIComponent(pair[1]);
    switch (pair[0]) {
      case "string":
        string = s;
        break;
      case "regexp":
        regexp = true;
        break;
      case "path":
        search += "path:" + s + " ";
        break;
      case "ext":
        search += "ext:" + s + " ";
        break;
      case "type":
        search += "type:" + s + " ";
        break;
      case "member":
        search += "member:" + s + " ";
        break;
      case "callers":
        search += "callers:" + s + " ";
        break;
      case "warnings":
        search += "warnings:" + s + " ";
        break;
      case "macro":
        search += "macro:" + s + " ";
        break;
      case "derived":
        search += "derived:" + s + " ";
        break;
    }
  }
  if (string) {
    if (regexp)
     search = "/" + string + "/ " + search;
    else
     search = string + " " + search;
  }
  if (/ $/(search))
    search = search.substring(0, search.length - 1);
  var sb = document.getElementById(id);
  sb.value = search;
  sb.focus();
}
