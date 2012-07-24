(function(){

var result_template = ""
 + "<div class='result'>"
 + "<a class='path' href='{{wwwroot}}/{{tree}}/{{path}}'>{{path}}</a><br>"
 + "{{formatted_lines}}"
 + "</div>";

var lines_template = ""
 + "<a class='snippet' href='{{wwwroot}}/{{tree}}/{{path}}#l{{line_number}}'>"
 + "  <div class='line-numbers'>"
 + "    <pre><span class='ln'>{{line_number}}</span></pre>"
 + "  </div>"
 + "  <div class='file-lines'><pre><code>{{line}}</code></pre></div>"
 + "</a>";

/** Format a template and return it */
function format_template(template, vars){
  for(var k in vars){
    template = template.replace(new RegExp("\\{\\{" + k + "\\}\\}", "g"), vars[k]);
  }
  return template;
}

/** Format results */
function format_results(data){
  // Fillout wwwroot, tree, path and friends
  var result_tmpl = format_template(result_template, data);
  var lines_tmpl = format_template(lines_template, data);
  // For each result
  var retval = ""
  for(var i = 0; i < data["results"].length; i++){
    var lines = "";
    for(var j = 0; j < data["results"][i].lines.length; j++){
      lines += format_template(lines_tmpl, data["results"][i].lines[j]);
    }
    retval += format_template(format_template(result_tmpl, {formatted_lines: lines}), data["results"][i]);
  }
  return retval;
}

var current_offset = null;
var req = null;
var end_of_results = false;
/** Fetch results, parse offset from querystring */
function fetch_results(){
  if(end_of_results) return;
  // Only request results if no pending request is in progress
  if(req != null) return;
  document.getElementById("fetch-results").style.display = "block";
  // Create request
  req = new XMLHttpRequest();
  req.onreadystatechange = function(){
    if(req.readyState == 4 && req.status == 200){
      data = JSON.parse(req.responseText);
      end_of_results = data["results"].length == 0;
      document.getElementById("results").innerHTML += format_results(data);
      req = null;
    }else if(req.readyState == 4){
      // Something failed, who cares try again :)
      req = null;
      fetch_results();
    }
    if(req == null)
      document.getElementById("fetch-results").style.display = "none";
    // Fetch results if there's no scrollbar initially
    if(document.documentElement.clientHeight == document.documentElement.scrollHeight)
      fetch_results();
  }
  var params = ["format=json", "redirect=false"];
  var offset = current_offset || 0;
  var limit = 100;
  var items = window.location.search.substr(1).split("&");
  for(var i = 0; i < items.length; i++){
    var keyvalue = items[i].split("=");
    key = keyvalue[0]
    if(key == "offset" && current_offset == null)
      offset = parseInt(keyvalue[1]);
    if(key == "limit")
      limit = parseInt(keyvalue[1]);
    if(key == "q")
      params.push(items[i]);
    if(key == "tree")
      params.push(items[i]);
  }
  current_offset = offset + limit;
  params.push("offset=" + current_offset);
  params.push("limit=" + limit);
  req.open("GET", wwwroot + "/search?" + params.join("&"), true);
  req.send();
}

/** Subscribe to events */
window.addEventListener('load', function(){
  window.addEventListener('scroll', function(e){
    // Find scroll top and test if we're at the bottom
    // http://stackoverflow.com/questions/10059888/detect-when-scroll-reaches-the-bottom-of-the-page-without-jquery
    var scrollTop = Math.max(document.documentElement.scrollTop, document.body.scrollTop);
    if((scrollTop + document.documentElement.clientHeight) >= document.documentElement.scrollHeight){
      fetch_results();
    }
  }, false);
  // Fetch results if there's no scrollbar initially
  if(document.documentElement.clientHeight == document.documentElement.scrollHeight)
    fetch_results();
  // Subscribe to advanced-search submit
  document.getElementById("advanced-search").addEventListener('submit', function(e){
    // Build the query
    var query = "";
    var fields = document.querySelectorAll("#advanced-search input[type=text]");
    for(var i = 0; i < fields.length; i++){
      var field = fields[i];
      if(field.dataset.param && field.value != "")
        query += field.dataset.param + ":";
      if(field.value != "")
        query += field.value + " ";
    }
    // Change document location
    document.location = wwwroot + "/search?q=" + escape(query) + "&tree=" + tree;
    e.preventDefault();
    return false;
  }, true);
}, false);

}());
