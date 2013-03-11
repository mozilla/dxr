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
 + "   href=\"{{wwwroot}}/{{tree}}/source/{{path}}#l{{line_number}}\">"
 + "  <div class=\"line-numbers\">"
 + "    <pre><span class=\"ln\">{{line_number}}</span></pre>"
 + "  </div>"
 + "  <div class=\"file-lines\"><pre><code>{{line}}</code></pre></div>"
 + "</a>";

/** Format a template and return it */
function format_template(template, vars){
  for(var k in vars){
    var value = vars[k].toString().replace(new RegExp("\\$", "g"), "$$$$");
    template = template.replace(new RegExp("\\{\\{" + k + "\\}\\}", "g"), value);
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
      var href = wwwroot + '/' + dxr.tree() + '/source/' + p;
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


/** Initialize incremental search, etc. */
function initIncrementalSearch(){
  // Get the query as passed in the text field
  var q = document.getElementById("query");
  state.query = q.value;

  // Since we have javascript support let's hide paging links
  var pagelinks = document.getElementById("result-page-switch");
  if(pagelinks){
    // If we're in the search.html template, we hide the foot
    // If not we'll do this in fetch_results, when we got something
    var foot = document.getElementById("foot");
    foot.style.display        = 'none';
    // Display the fetcher thing with visibility hidden
    var fetcher = document.getElementById("fetch-results");
    fetcher.style.display     = 'block';
    fetcher.style.visibility  = 'hidden';
  }

  // Fetch results, if any, on scroll to bottom of page
  window.addEventListener('scroll', function(e){
    if(atPageBottom() && !state.eof) fetch_results(true);
  }, false); 

  // Update advanced search fields on change in q
  q.addEventListener('input', function(e){
    // Don't do anything if query didn't change
    if(state.query == q.value) return;
    // Reset the state
    state.query   = q.value;
    state.offset  = 0;
    state.eof     = false;
    state.changed = true;
    // Dispatch dxr-state-changed
    window.dispatchEvent(
      new CustomEvent( 'dxr-state-changed', {
        detail: {}
      })
    );
  }, false);

  // Set fetch results time when state is changed
  window.addEventListener('dxr-state-changed', setFetchResultsTimer);

  document.getElementById("tree").addEventListener('change', function(){
    state.query   = q.value;
    state.offset  = 0;
    state.eof     = false;
    state.changed = true;
    // Dispatch dxr-state-changed
    window.dispatchEvent(
      new CustomEvent( 'dxr-state-changed', {
        detail: {}
      })
    );
  }, false);

  // Fetch results if a bottom of page initially
  // this is necessary, otherwise one can't scroll
  if(atPageBottom() && !state.eof) fetch_results(true);
}


/** Set fetch results timer  */
var _fetch_results_timer = null;
function setFetchResultsTimer(){
  var timeout = 300;  // use 300 ms
  // Reset the timer
  if(_fetch_results_timer) clearTimeout(_fetch_results_timer);
  _fetch_results_timer = setTimeout(fetch_results, timeout);
}



// Current request
var request = null;
// Clear contents of results on set
var clear_on_set = false;

/** Fetch results, using current state */
function fetch_results(display_fetcher){

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
  if(display_fetcher){
    fetcher.style.visibility = 'visible';
    fetcher.style.display    = 'block';
    // Hide footer
    var foot = document.getElementById("foot");
    foot.style.display       = 'none';
  }

  // Create request
  request = new XMLHttpRequest();
  request.onreadystatechange = function(){
    if(request.readyState == 4 && request.status == 200){
      // Get data
      var data = JSON.parse(request.responseText);
      // Update state, if it wasn't changed
      if(!state.changed){
        state.eof     = data["results"].length == 0;
        state.offset += data["results"].length;
      }
      // Display a nice tip
      dxr.setTip("Incremental search results in " + data["time"].toFixed(3) + "s");
      var content = document.getElementById("content");
      // Clear results if necessary
      if(clear_on_set && !data["error"]){
        content.innerHTML = "";
        // Scroll to top of page
        window.scroll(0, 0);

        // Hide foot, set fetcher hidden
        var foot = document.getElementById("foot");
        foot.style.display       = 'none';
        fetcher.style.display    = 'block';
        fetcher.style.visibility = 'hidden';
      }
      content.innerHTML += format_results(data);
      // Set error as tip
      if(data["error"])
        dxr.setErrorTip(data["error"]);
      request = null;
    }else if(request.readyState == 4){
      // Something failed, who cares try again :)
      request = null;
      fetch_results();
    }
    // Hide fetcher if finished request
    if(request == null){
      fetcher.style.display    = 'block';
      fetcher.style.visibility = 'hidden';
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
    tree:           dxr.tree(),
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
window.createSearchUrl = createSearchUrl;  // used in advanced-search.js


/** Initialize the context menu */
function initMenu(){
  // Show menu when path link is clicked
  // Attach event handler on results, so we don't have to worry about what
  // happens when we update the contents of results.
  document.getElementById("content").addEventListener('click', function (e){
    // Ensure that we're in a 
    if(!e.target.parentNode 
       || !e.target.parentNode.classList.contains('path')) return;

    // Okay, get the path
    var path = e.target.dataset.path;
  
    // Don't show menu if file name part was clicked
    // as we didn't stop default user will jump to this page
    if(!path) return;

    // Parse querystring so we can make some urls
    var params = {
      tree:           dxr.tree(),
      limit:          state.limit,
      redirect:       'false'
    };

    // Create url to limit search
    params.q = state.query + " path:" + path;
    var limit_url = createSearchUrl(params);

    // Create url to exclude path from search
    params.q = state.query + " -path:" + path;
    var exclude_url = createSearchUrl(params);

    // Populate menu with links
    menu.populate([
      {
        icon:   'goto_folder',
        href:    wwwroot + "/" + dxr.tree() + "/" + path,
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

/** Subscribe to events */
window.addEventListener('load', function(){
  initIncrementalSearch();
  initMenu();
}, false);


}());
