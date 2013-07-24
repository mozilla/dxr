(function (){

/** Scroll to current line when hash changes */
function hashchanged(){
  var line, name, elems;
  if((line = findLine()) != -1){
    if(elem = document.getElementById("line-" + line)){
      // Remove highlighted from everything
      var highligted = document.querySelectorAll(".highlight");
      for(var i = 0; i < highligted.length; i++)
        highligted[i].classList.remove("highlight");
      // Highlight the line
      elem.parentNode.classList.add("highlight");
      // Highlight the annotation set for the line
      var aset = document.getElementById("aset-" + line);
      aset.classList.add("highlight");
      window.scroll(0, findPosTop(elem) - window.innerHeight / 4.0);
    }
  } 
}

/** Add auxiliary string method for indexOf using regexp
 * Credits to: http://stackoverflow.com/a/274094
 */
String.prototype.regexIndexOf = function(regex, startpos){
  var indexOf = this.substring(startpos || 0).search(regex);
  return (indexOf >= 0) ? (indexOf + (startpos || 0)) : indexOf;
}

/** Add auxiliary string method for LastIndexOf using regexp
 * Credits to: http://stackoverflow.com/a/274094
 */
String.prototype.regexLastIndexOf = function(regex, startpos){
  if(!regex.global){
    var flags = "g" + (regex.ignoreCase ? "i" : "") + (regex.multiLine ? "m" : "");
    regex = new RegExp(regex.source, flags);
  }
  if(typeof (startpos) == "undefined") {
      startpos = this.length;
  } else if(startpos < 0) {
      startpos = 0;
  }
  var stringToWorkWith = this.substring(0, startpos + 1);
  var lastIndexOf = -1;
  var nextStop = 0;
  while((result = regex.exec(stringToWorkWith)) != null) {
      lastIndexOf = result.index;
      regex.lastIndex = ++nextStop;
  }
  return lastIndexOf;
}

/** Initialize the context menu */
function initMenu(){
  var pre = document.querySelector(".file-lines pre");
  // Show menu when text is clicked
  pre.addEventListener('click', function(e){
    // Abort if the target isn't a code node underneath
    if(e.target == pre) return;
    var links = []
    // Find the word clicked
    var s = window.getSelection();
    // If there's a selection, we don't show menu, so users can copy/paste things
    if(!s.isCollapsed) return;
    var offset = s.focusOffset;
    var text  = s.anchorNode.nodeValue;
    var start = text.regexLastIndexOf(/[^A-Z0-9_]/i, offset) + 1;
    var end   = text.regexIndexOf(/[^A-Z0-9_]/i, offset);
    if(start == -1) start = 0;
    if(end   == -1) end   = text.length;
    var word = text.substr(start, end - start);
    // Make work link
    if(word.length > 0){
      links.push({
        icon:   'search', 
        text:   "Search for \"" + htmlEntities(word) + "\"",
        title:  "Search for documents with the substring \"" + htmlEntities(word) + "\"", 
        href:   wwwroot + "/" + encodeURIComponent(dxr.tree()) + "/search?q=" + encodeURIComponent(word)
      });
    }
    // Append menu from target, if any
    if(e.target.dataset.menu){
      links = [].concat(links, JSON.parse(e.target.dataset.menu));
    }
    if(links.length == 0) return;
    // Populate and launch menu
    menu.populate(links);
    if(e.target.dataset.menu){
      menu.launch(e.target);
    }else{
      // Create a text range, and use it to get a bounding box
      // Our range will never cross elements, because we create it from
      // carat position, and when there's an actual non-empty selection
      // well, we can't really get the position of the click as text offset.
      var range = document.createRange();
      range.setStart(s.anchorNode, start);
      range.setEnd(s.anchorNode, end);
      var left = range.getBoundingClientRect().left;
      menu.launchAt(left, menu.posTop(e.target) + e.target.offsetHeight);
    }
    // Stop event propagation
    e.preventDefault();
    e.stopPropagation();
  }, false);
}

var pattern = /^#l[0-9]+$/;
/** Find line by anchor */
function findLine(){
  var result;
  if((result = pattern.exec(window.location.hash)) != null){
    return parseInt(result[0].substr(2));
  }
  return -1;
}

/** Find object position from the top */
function findPosTop(obj) {
  var top = 0;
  do{
    top += obj.offsetTop;
  }while(obj = obj.offsetParent);
  return top;
}

/** Initialize search tips */
function initTip(){
  // Parse querystring for from=
  var query = null;
  var items = window.location.search.substr(1).split("&");
  for(var i = 0; i < items.length; i++){
    var keyvalue = items[i].split("=");
    if(keyvalue[0] == "from")
      query = decodeURIComponent(keyvalue[1]);
  }
  if(query){
    // Set a nice search tip, so people can go the results
    var url = wwwroot + "/" + encodeURIComponent(dxr.tree()) + "/search?q=" + encodeURIComponent(query) + "&redirect=false";
    text = ("You've been taken to a direct result " +
                     "<a href='{{url}}'>click here</a>" + 
                     " to see all search results").replace("{{url}}", url);
    dxr.setTip(text);
    // Insert the query into the search field
    var q = document.getElementById("query");
    q.value     = query;
    state.query = query;
    // Make search field redirect = false, untill user types a different query
    var redirect = document.getElementById("redirect");
    redirect.value = "false";
    q.focus();
    window.addEventListener('dxr-state-changed', function(){
      if(state.query != query)
        redirect.value = "true";
      else
        redirect.value = "false";
    }, false);
  }
}

/** Escape HTML Entitites */
function htmlEntities(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Hijack the blame link, to toggle blame annotations */
function hijackBlame(){
  var pc = document.getElementById("panel-content");
  var annos = document.getElementById("annotations");
  var blaming = false;
  // Helper for toggling the blame annotations
  function toggleBlame(){
    if(blaming)
      annos.classList.remove('blame');
    else
      annos.classList.add('blame');
    blaming = !blaming;
  }
  // Hijack click we think are hitting the blame link
  pc.addEventListener('click', function(e){
    // If the name is 'Blame'
    if(e.target.innerHTML != "Blame")
      return;
    // And it links to some sort of annotate
    var href = e.target.getAttribute('href');
    if(href.indexOf("/annotate/") == -1)
      return;
    // And it has the blame icon
    if(e.target.style.backgroundImage.indexOf("blame") == -1)
      return;
    // It's probably the blame link and we hijack it :)
    // I know this ugly, but short of allowing plugins to define
    // javascript and other bad things, there's no other way to integrate
    // tightly. Besides all the ugly stuff is in the template in javascript
    // and javascript can't be pretty anyway.
    // NOTE: While this is an ugly hack, the plugin and template interfaces
    // are fully respected, if we remove the blame specific things the
    // annotations still work, they just can't be toggled.
    e.preventDefault();
    e.stopPropagation();
    toggleBlame();
  }, true);

  // Get the info box
  var infobox = document.getElementById("info-box");

  // Handle clicks on note-blame annotations
  annos.addEventListener('click', function(e){
    if(e.target.classList.contains("note-blame")){
      // Stop what you're doing we've got a info-box to show
      e.preventDefault();
      e.stopPropagation();
      var data = e.target.dataset;
      var html = ""
       + "<img src='" + data.hgImg + "'>"
       + "<b>" + htmlEntities(data.hgUser) + "</b><br>"
       + "<i>" + dxr.prettyDate(data.hgDate) + "</i><br>"
       + e.target.getAttribute("title");
      infobox.innerHTML = html;
      infobox.style.display = 'block';
      infobox.style.top     = (menu.posTop(e.target) + e.target.offsetHeight) + "px";
      infobox.style.left    = menu.posLeft(e.target) + "px";
    }
  }, false);
  
  // Stop event to reaching window
  infobox.addEventListener('mousedown', function(e){
    e.stopPropagation();
  }, false);

  // Hide info when something is clicked
  window.addEventListener('mousedown', function(e){
    infobox.style.display = 'none';
  }, false);
}

/** Initialize everything */
window.addEventListener('load', function (){
  window.addEventListener('hashchange', hashchanged, false);
  initTip();
  initMenu();
  hijackBlame();
  setTimeout(hashchanged, 0);
}, false);

}());
