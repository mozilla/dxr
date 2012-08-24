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

/** Initialize the context menu */
function init_menu(){
  var as = document.querySelectorAll(".file-lines a");
  // Show menu when link is clicked
  function showMenu(e){
    var links = JSON.parse(e.target.dataset.menu);
    // Populate and launch menu
    menu.populate(links);
    menu.launch(e.target);
    // Stop event propagation
    e.preventDefault();
    e.stopPropagation();
  }
  // Add event listener to all relevant links
  for(var i = 0; i < as.length; i++){
    if(as[i].dataset["menu"])
      as[i].addEventListener('click', showMenu, false);
  }
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

/** Find object position from the left */
function findPosLeft(obj) {
  var left = 0;
  do{
    left += obj.offsetLeft;
  }while(obj = obj.offsetParent);
  return left;
}

/** Initialize search tips */
function init_tip(){
  // Parse querystring for from=
  var query = null
  var items = window.location.search.substr(1).split("&");
  for(var i = 0; i < items.length; i++){
    var keyvalue = items[i].split("=");
    if(keyvalue[0] == "from")
      query = keyvalue[1];
  }
  if(query){
    // Set a nice search tip, so people can go the results
    var url = wwwroot + "/search?tree=" + tree + "&q=" + query + "&redirect=false";
    text = ("You've been taken to a direct result " +
                     "<a href='{{url}}'>click here</a>" + 
                     " to see all search results").replace("{{url}}", url);
    dxr.setTip(text);
    // Insert the query into the search field
    var q = document.getElementById("query");
    q.value = query;
    // Make search field redirect = false, untill user types a different query
    var redirect = document.getElementById("redirect");
    redirect.value = "false";
    q.focus();
    q.addEventListener('keyup', function(){
      if(q.value != query)
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
  init_tip();
  init_menu();
  hijackBlame();
  hashchanged();
}, false);

}());
