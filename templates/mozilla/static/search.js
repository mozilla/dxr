(function(){

var result_template = ""
 + "<div class='result'>"
 + "<div class='path'"
 + " style=\"background-image: url('{{wwwroot}}/static/icons/{{icon}}.png')\""
 + " >{{path}}</div>"
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
    // Yes, the ugly path hack
    var folders = data["results"][i].path.split('/');
    var pathline = ""
    for(var j = 0; j < folders.length; j++){
      var folder = folders[j];
      var p = folders.slice(0, j + 1).join('/');
      var href = wwwroot + '/' + tree + '/' + p;
      pathline += "<a href='" + href + "' ";
      if(j + 1 < folders.length){
        pathline += "data-path='" + p + "/'";
      }
      pathline += ">" + folder;
      if(j + 1 < folders.length){
        pathline += "/";
      }
      pathline += "</a>";
    }
    data["results"][i].path = pathline;
    retval += format_template(
                format_template(result_tmpl, {formatted_lines: lines}),
                data["results"][i]
              );
  }
  return retval;
}

/* Check if we've scrolled to bottom of the page
 * Find scroll top and test if we're at the bottom
 * http://stackoverflow.com/questions/10059888/ */
function atPageBottom(){
  var scrollTop = Math.max(document.documentElement.scrollTop,
                           document.body.scrollTop);
  scrollTop += document.documentElement.clientHeight;
  return scrollTop >= document.documentElement.scrollHeight;
}

/** Initialize automatic fetching of results */
function initFetchResults(){
  window.addEventListener('scroll', function(e){
    if(atPageBottom()) fetch_results();
  }, false);

  // Fetch results if at bottom initially
  if(atPageBottom()) fetch_results();
}

var current_offset = null;
var req = null;
var end_of_results = false;
/** Fetch results, parse offset from querystring */
function fetch_results(){
  if(end_of_results) return;
  // Only request results if no pending request is in progress
  if(req != null) return;
  document.getElementById("fetch-results").style.visibility = "visible";
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
      document.getElementById("fetch-results").style.visibility = "hidden";
    // Fetch results if there's no scrollbar initially
    if(atPageBottom())
      fetch_results();
  }

  // Parse querystring
  var params = parseQuerystring();

  // Set default limit
  if(params.limit){
    params.limit = parseInt(params.limit);
  }else{
    params.limit = 100;
  }

  // Update current offset
  if(current_offset == null){
    if(params.offset){
      current_offset = parseInt(params.offset);
    }else{
      current_offset = 0;
    }
  }
  current_offset += params.limit;
  params.offset = current_offset;

  // Set format and redirect
  params.format    = "json";
  params.redirect  = "false";

  // Set the request
  req.open("GET", createSearchUrl(params), true);
  req.send();
}

/** Parse querystring */
function parseQuerystring(){
  var params = {};
  var items = window.location.search.substr(1).split("&");
  for(var i = 0; i < items.length; i++){
    var keyvalue = items[i].split("=");
    params[decodeURIComponent(keyvalue[0])] = decodeURIComponent(keyvalue[1]);
  }
  return params;
}

/** Create search URL from search parameters as querystring */
function createSearchUrl(params){
  var elements = []
  for(var key in params){
    var k = encodeURIComponent(key);
    var v = encodeURIComponent(params[key]);
    elements.push(k + "=" + v);
  }
  return wwwroot + "/search?" + elements.join("&");
}


/** Initialize the context menu */
function initMenu(){
  // Show menu when path link is clicked
  function showMenu(e){
    // Okay, get the path
    var path = e.target.dataset.path;
  
    // Don't show menu if file name part was clicked
    // as we didn't stop default user will jump to this page
    if(!path) return;

    // Parse querystring so we can make some urls
    var params = parseQuerystring();
    var query = params.q;

    // Create url to limit search
    params.q = query + " path:" + path;
    var limit_url = createSearchUrl(params);

    // Create url to exclude path from search
    params.q = query + " -path:" + path;
    var exclude_url = createSearchUrl(params);

    // Populate menu with links
    menu.populate([
      {
        icon:   'goto_folder',
        href:    wwwroot + "/" + tree + "/" + path,
        title:  "Browse the \"" + path + "\" folder",
        text:   "Browser folder contents"
      },
      {
        icon:   'path_search',
        href:   limit_url,
        title:  "Only show results from \"" + path + "\"",
        text:   "Limit search to folder"
      },
      {
        icon:   'exclude_path',
        href:   exclude_url,
        title:  "Exclude results located in \"" + path + "\"",
        text:   "Exclude folder from search"
      }
    ]);
    // Launch menu
    menu.launch(e.target);
    // Stop event propagation
    e.preventDefault();
    e.stopPropagation();
  }
  // Add event listener to all relevant links
  //var as = document.querySelectorAll("div.path a");
  //for(var i = 0; i < as.length; i++){
  //  as[i].addEventListener('click', showMenu, false);
  //}
  document.getElementById("results").addEventListener('click', showMenu, false);
}

function initAdvancedSearch(){
  // Subscribe to advanced-search submit
  var as = document.getElementById("advanced-search");
  as.addEventListener('submit', function(e){
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
    document.location = createSearchUrl({
      q:    query,
      tree: tree
    });
    e.preventDefault();
    return false;
  }, true);
}



/** Subscribe to events */
window.addEventListener('load', function(){
  initFetchResults();
  initMenu();
  initAdvancedSearch();
}, false);


}());
