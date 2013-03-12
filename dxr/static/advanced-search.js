(function(){


var regexpParser = /^regexp:(.)(?:(?!\1).)+\1/;

/** Parse query to dictionary with params
 * parameter arguments not in params will be considered terms
 * keys in args are not prefixed with the param, but those left in
 * terms are, also phrases are considered keys in terms, and they
 * keep the quotation */
function parseQuery(q, params){
  // Terms and arguments in the query
  var terms = [];
  var args = {};

  // Remove regexp if there it needs special care
  var idx = params.indexOf("regexp");
  var hasRegExp = false;
  if(idx != -1){
    // Clone
    params = params.slice();
    // Remove regexp
    params.splice(hasRegExp, 1);
    hasRegExp = true;
    args.regexp = [];
  }

  // Build regular expression
  var regexp = "^";
  for(var i = 0; i < params.length; i++){
    var param = params[i];
    regexp += "(" + param + ":(?:\"[^\"]+\"|[^ ]+))|";
    // Add empty list for each parameter
    args[param] = [];
  }
  regexp += "(\"[^\"]+\")|([^ ]+)|([ ]+)";
  regexp = new RegExp(regexp);

  // While there's text to parse, get the next match
  var m;
  while(m = regexp.exec(q)){
    // Length of token read, -1 for unknown
    var len = -1;
    // Attempt to read a regular expression
    var r = regexpParser.exec(q);
    if(hasRegExp && r){
      // Check for a match
      if(r[0]){
        args.regexp.push(r[0].substr(7));
        len = r[0].length;
      }
    }

    // Attempt to read one of the params
    for(var i = 0; i < params.length; i++){
      if(len != -1) break;
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
    var arg = m[params.length + 1]
    if(len < 0 && arg){
      // Leave the quotes on, and consider it a term
      terms.push(arg);
      len = arg.length;
    }
    // It can also be a term
    arg = m[params.length + 2]
    if(len < 0 && arg){
      terms.push(arg);
      len = arg.length;
    }
    // It can also be whitespace
    arg = m[params.length + 3]
    if(len < 0 && arg)
      len = arg.length;
    // Worst case we didn't get it right
    if(len < 0){
      len = 1;
      // Log and error for debuggin
      if(console && console.log)
        console.log("Failed to parse query '" + q + "'");
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
  var query = [];
  var fields = document.querySelectorAll("#advanced-search input[type=text]");
  for(var i = 0; i < fields.length; i++){
    var field = fields[i];
    var param = field.dataset.param;
    var v = field.value;
    var r;
    // Magic to handle regular expressions
    if(param == "regexp"){
      var regexpFieldParser = /\s*((\S)(?:(?!\2).)+\2)|\s*(\S.*?)\s*$/g;
      while((r = regexpFieldParser.exec(v))){
        if(r[1])
          query.push(param + ":" + r[1]);
        else if(r[3]){
          // Regular expressions should be wrapped with same start and end letter.
          // We use # if none is specified.
          query.push(param + ":#" + r[3] + "#");
        }
      }
      continue;
    }
    // All whitespace outside of quotes gets eaten
    var fieldParser = /"[^"]+"|\S+/g;
    while((r = fieldParser.exec(v))){
      if(param)
        query.push(param + ":" + r[0]);
      else
        query.push(r[0]);
    }
  }
  // Notice whitespace normalization 
  return query.join(" ");
}




/** Initialize the advanced search panel */
function initAdvancedSearch(){
  // Subscribe to advanced-search submit
  var as = document.getElementById("advanced-search");
  as.addEventListener('submit', function(e){
    // Change document location
    document.location = createSearchUrl(dxr.tree(), {
      q:    buildQueryFromAdvanced()
    });
    e.preventDefault();
    return false;
  }, true);

  // Update query on change in any advanced search field
  var fields = document.querySelectorAll("#advanced-search input[type=text]");
  var q = document.getElementById("query");
  for(var i = 0; i < fields.length; i++){
    fields[i].addEventListener('input', function(e){
      // Don't do anything if query didn't change
      if(state.query == buildQueryFromAdvanced()) return;
      // Reset the state
      state.query   = buildQueryFromAdvanced();
      state.offset  = 0;
      state.eof     = false;
      state.changed = true;
      // Update q
      q.value = state.query;
      // Dispatch dxr-state-changed
      window.dispatchEvent(
        new CustomEvent('dxr-state-changed', {
          detail: {
            // Indicate that this change originates from advanced fields
            // Only used in anonymous event for 'dxr-state-changed'
            advancedFields: true
          }
        })
      );
    }, false);
  }

  // Update advanced fields imidiately
  updateAdvancedFields();

  // Update advanced fields
  window.addEventListener('dxr-state-changed', function(e){
    // If this came from advanced fields update, don't update advanced fields
    if(!e.details || !e.details.advancedFields)
      updateAdvancedFields();
  }, false);
}

/** Update advanced fields to match content of q */
function updateAdvancedFields(){
  var q = document.getElementById("query");
  // If only inconsequential things like whitespace have changed, don't modify
  // the advanced fields.  This avoids trailing whitespace getting eaten and
  // the regexp field from behaving oddly when it doesn't yet have matching
  // beginning and ending delimiters.
  if (q.value == buildQueryFromAdvanced())
    return;
  var fields = document.querySelectorAll("#advanced-search input[type=text]");
  var params = [];
  for(var i = 0; i < fields.length; i++){
    if(fields[i].dataset.param)
      params.push(fields[i].dataset.param);
  }
  var query = parseQuery(q.value, params);
  // For each field, set it to the params
  for(var i = 0; i < fields.length; i++){
    // If it doesn't have a param, it's the terms
    if(fields[i].dataset.param)
      fields[i].value = query.args[fields[i].dataset.param].join(" ");
    else
      fields[i].value = query.terms.join(" ");
  }
}

window.addEventListener('load', function(){
	initAdvancedSearch();
}, false);

}());