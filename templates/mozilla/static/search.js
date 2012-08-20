(function(){

// TODO Migrate this to use jinja.js, so we can place a template file in static/
//      and use that template on the server using an include statement and on
//      client side.
var result_template = ""
 + "<div class=\"result\">"
 + "<div class=\"path\""
 + " style=\"background-image: url('{{wwwroot}}/static/icons/{{icon}}.png')\""
 + " >{{path_line}}</div>"
 + "{{formatted_lines}}"
 + "</div>";

var lines_template = ""
 + "<a class=\"snippet\" "
 + "   href=\"{{wwwroot}}/{{tree}}/{{path}}#l{{line_number}}\">"
 + "  <div class=\"line-numbers\">"
 + "    <pre><span class=\"ln\">{{line_number}}</span></pre>"
 + "  </div>"
 + "  <div class=\"file-lines\"><pre><code>{{line}}</code></pre></div>"
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
  // Fillout wwwroot and tree
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
      pathline += "<a href=\"" + href + "\" ";
      if(j + 1 < folders.length){
        pathline += "data-path=\"" + p + "/\"";
      }
      pathline += ">" + folder;
      if(j + 1 < folders.length){
        pathline += "/";
      }
      pathline += "</a>";
    }
    retval += format_template(result_tmpl, {
      formatted_lines:    lines,
      path_line:          pathline,
      icon:               data["results"][i].icon,
      path:               data["results"][i].path
    });
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


// Things to do:
// - initSearch: Load query from q to state.query
// - Include json2.js
// - Added icons to git
// - Make the no-results page non-select using background-image
// - Adapt fetch_results to use state
// - Update advanced search fields on write in q
// - Update q on write in advanced search fields
// - Start timer for fetch results on changes to query, reset offset here
// - Read query from querystring in file when going to direct result
//   and allow a quick extra enter to search without redirect!

/** Initialize live search, etc. */
function initSearch(){
  // Get the query as passed in the text field
  var q = document.getElementById("query");
  state.query = q.value;

  // Since we have javascript support let's hide paging links
  var pagelinks = document.getElementById("result-page-switch");
  pagelinks.style.display = 'none';

  // Display the fetcher thing with visibility hidden
  var fetcher = document.getElementById("fetch-results");
  fetcher.style.display     = 'block';
  fetcher.style.visibility  = 'hidden';

  // Fetch results, if any, on scroll to bottom of page
  window.addEventListener('scroll', function(e){
    if(atPageBottom() && !state.eof) fetch_results();
  }, false); 
  
  // Fields, and list of params used in advanced search
  var fields = document.querySelectorAll("#advanced-search input[type=text]");
  var params = [];
  for(var i = 0; i < fields.length; i++){
    if(fields[i].dataset.param)
      params.push(fields[i].dataset.param);
  }

  // Timer for when to fetch results during live-search
  var timer   = null;
  var timeout = 300;  // use 300 ms

  // Update advanced search fields on change in q
  q.addEventListener('keyup', function(e){
    // Don't do anything if query didn't change
    if(state.query == q.value) return;
    // Reset the state
    state.query   = q.value;
    state.offset  = 0;
    state.eof     = false;
    state.changed = true;
    // Update advanced fields
    var query = parseQuery(q.value, params);
    // For each field, set it to the params
    for(var i = 0; i < fields.length; i++){
      // If it doesn't have a param, it's the terms
      if(fields[i].dataset.param)
        fields[i].value = query.args[fields[i].dataset.param].join(" ");
      else
        fields[i].value = query.terms.join(" ");
    }
    // Reset the timer
    if(timer) clearTimeout(timer);
    setTimeout(fetch_results, timeout);
  }, false);

  // Update query on change in any advanced search field
  for(var i = 0; i < fields.length; i++){
    fields[i].addEventListener('keyup', function(e){
      // Don't do anything if query didn't change
      if(state.query == buildQueryFromAdvanced()) return;
      // Reset the state
      state.query   = buildQueryFromAdvanced();
      state.offset  = 0;
      state.eof     = false;
      state.changed = true;
      // Update q
      q.value = state.query;
      // Reset the timer
      if(timer) clearTimeout(timer);
      setTimeout(fetch_results, timeout);
    }, false);
  }

  // Fetch results if a bottom of page initially
  // this is necessary, otherwise one can't scroll
  if(atPageBottom() && !state.eof) fetch_results();
}

/** Parse query to dictionary with params
 * parameter arguments not in params will be considered terms
 * keys in args are not prefixed with the param, but those left in
 * terms are, also phrases are considered keys in terms, and they
 * keep the quotation */
function parseQuery(q, params){
  // Terms and arguments in the query
  var terms = [];
  var args = {};

  // Build regular expression
  var regexp = "";
  for(var i = 0; i < params.length; i++){
    var param = params[i];
    regexp += "(" + param + ":[^ ]+)|";
    // Add empty list for each parameter
    args[param] = [];
  }
  regexp += "(\"[^\"]+\")|([^ ]+)|([ ]+)";
  var r = regexp;
  regexp = new RegExp(regexp);

  // While there's text to parse, get the next match
  var m;
  while(m = regexp.exec(q)){
    // Length of token read, -1 for unknown
    var len = -1;
    for(var i = 0; i < params.length; i++){
      var param = params[i];
      var arg   = m[i + 1];
      // Arg is in fact defined we got it
      if(arg){
        // Store the argument stop
        args[param].push(arg.substr(param.length + 1));
        len = arg.length;
        break;
      }
    }
    // If we didn't get an argument, it might be a phrase
    if(len < 0 && m[params.length + 1]){
      // Leave the quotes on, and consider it a term
      terms.push(m[params.length + 1]);
      len = m[params.length + 1].length;
    }
    // It can also be a term
    if(len < 0 && m[params.length + 2]){
      terms.push(m[params.length + 2]);
      len = m[params.length + 2].length;
    }
    // It can also be whitespace
    if(len < 0 && m[params.length + 3])
      len = m[params.length + 3].length;
    // Worst case we didn't get it right
    if(len < 0){
      len = 1;
      // Log and error for debuggin
      if(console && console.log)
        console.log("Failed to parse query '" + q + "'");
      return {};
    }
    // Update q before we repeat
    q = q.substr(len);
  }
  // Return the values we've found, and be done with it
  return {
    terms:  terms,
    args:   args
  };
}

/** Build a query from advanced search */
function buildQueryFromAdvanced(){
  var query = "";
  var fields = document.querySelectorAll("#advanced-search input[type=text]");
  for(var i = 0; i < fields.length; i++){
    var field = fields[i];
    if(field.dataset.param && field.value != "")
      query += field.dataset.param + ":";
    if(field.value != "")
      query += field.value + " ";
  }
  return query;
}

// Current request
var request = null;
// Clear contents of results on set
var clear_on_set = false;

/** Fetch results, using current state */
function fetch_results(){
  // Stop if we're at end, nothing more to do
  if(state.eof && !state.changed) return;
  
  // Only request results if no pending request is in progress
  if(request && !state.changed) return;

  // Abort request if in progress
  if(request){
    // Clear event handler
    request.onreadystatechange = null;
    request.abort();
  }

  // Show the fetcher line at the bottom
  var fetcher = document.getElementById("fetch-results");
  fetcher.style.visibility = "visible";

  // Create request
  request = new XMLHttpRequest();
  request.onreadystatechange = function(){
    if(request.readyState == 4 && request.status == 200){
      // Get error and no result pages
      var noresults = document.getElementById("no-results");
      var error     = document.getElementById("expr-error");
      // Hide these pages
      noresults.style.display = 'none';
      error.style.display     = 'none';
      // Display a nice tip, in case there was an error
      dxr.setTip("Displaying live search results as you type:");
      // Get data
      var data = JSON.parse(request.responseText);
      // Update state, if it wasn't changed
      if(!state.changed){
        state.eof     = data["results"].length == 0;
        state.offset += data["results"].length;
      }
      var results = document.getElementById("results");
      // Clear results if necessary
      if(clear_on_set) results.innerHTML = "";
      results.innerHTML += format_results(data);
      if(!data["error"] && results.innerHTML == "")
        noresults.style.display = "block";
      if(data["error"] && results.innerHTML == ""){
        error.style.display = "block";
        dxr.setTip(data["error"]);
      }
      request = null;
    }else if(request.readyState == 4){
      // Something failed, who cares try again :)
      request = null;
      fetch_results();
    }
    // Hide fetcher if finished request
    if(request == null){
      fetcher.style.visibility = "hidden";
      // Fetch results if there's no scrollbar initially
      if(atPageBottom()) fetch_results();
    }
  }

  // Clear on set if this is a new state
  clear_on_set = state.changed;
  // Set state unchanged
  state.changed = false;

  // parameters for request
  var params = {
    q:              state.query,
    tree:           tree,
    limit:          state.limit,
    offset:         state.offset,
    redirect:       'false',
    format:         'json'
  };

  // Start a new request
  request.open("GET", createSearchUrl(params), true);
  request.send();
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
  // Attach event handler on results, so we don't have to worry about what
  // happens when we update the contents of results.
  document.getElementById("results").addEventListener('click', function (e){
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
  }, false);
}

function initAdvancedSearch(){
  // Subscribe to advanced-search submit
  var as = document.getElementById("advanced-search");
  as.addEventListener('submit', function(e){
    // Change document location
    document.location = createSearchUrl({
      q:    buildQueryFromAdvanced(),
      tree: tree
    });
    e.preventDefault();
    return false;
  }, true);
}


/** Subscribe to events */
window.addEventListener('load', function(){
  initSearch();
  initMenu();
  initAdvancedSearch();
}, false);

}());
