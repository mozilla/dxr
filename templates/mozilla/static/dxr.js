(function (){

var panel_visible = true;
var panel_title = "";
/** Toggle the panel visiblity (save state to cookie) */
function toggle_panel(){
  var content = document.getElementById("panel-content");
  if(panel_visible){
    content.style.display = "none";
  }else{
    content.style.display = "block";
  }
  panel_visible = !panel_visible;
  createCookie("panel-state" + panel_title, (panel_visible ? "true" : "false"), 42);
}

/** Scroll to current line when hash changes */
function hashchanged(){
  var line, name, elems;
  if((line = findLine()) != -1){
    if((elems = document.getElementsByName("l" + line)).length > 0){
      var highligted = document.querySelector(".highlight");
      if(highligted)
        highligted.classList.remove("highlight");
      elems[0].parentNode.classList.add("highlight");
      window.scroll(0, findPosTop(elems[0]) - window.innerHeight / 4.0);
    }
  } 
}

/** Initialize everything */
window.addEventListener('load', function (){
  window.addEventListener('hashchange', hashchanged, false);
  init_menu();
  hashchanged();
  init_tip();

  var panel_toggle = document.getElementById("panel-toggle");
  panel_title = panel_toggle.innerHTML;
  var val = readCookie("panel-state" + panel_title);
  if(val != null){
    // Read and flip it
    panel_visible = !(val == "true" ? true : false);
    // Make toggle it back to what we read
    toggle_panel();
  }
  panel_toggle.addEventListener('click', toggle_panel, false);
}, false);

//TODO use findLine to update log, blame, diff, raw links...

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

/** Initialize the context menu */
function init_menu(){
  var m = document.getElementById("inline-menu");
  var as = document.querySelectorAll(".file-lines a");
  // Show menu when link is clicked
  function showMenu(e){
    var rows = e.target.dataset.menu.split("!");
    var links = "";
    for(var j = 0; j < rows.length; j++){
      var row = rows[j];
      var args = row.split("|")
      links += "<a href='" + args[1] + "'>" + args[0] + "</a>";
    }
    m.innerHTML = links;
    m.style.display = "block";
    m.style.top = findPosTop(e.target) + "px";
    m.style.left = findPosLeft(e.target) + "px";
    e.preventDefault();
    e.stopPropagation();
  }
  // Add event listener to all relevant links
  for(var i = 0; i < as.length; i++){
    var a = as[i];
    if(a.dataset["menu"]){
      a.addEventListener('click', showMenu, false);
    }
  }
  // On mouse down, anywhere clear  the popop
  window.addEventListener('mousedown', function(){
    m.style.display = "none";
  }, false);
  // Stop mousedown propagation before, it hit's window and we hide menu
  m.addEventListener('mousedown', function(e){ e.stopPropagation(); }, false);
}

/** Create cookie, credits to quirksmode.org */
function createCookie(name, value, days){
  if(days){
    var date = new Date();
    date.setTime(date.getTime()+(days * 24 * 60 * 60 * 1000));
    var expires = "; expires="+date.toGMTString();
	}
  else
    var expires = "";
  document.cookie = name + "=" + value + expires + "; path=/";
}

/** Read cookie, credits to quirksmode.org */
function readCookie(name){
  var nameEQ = name + "=";
  var ca = document.cookie.split(';');
  for(var i = 0; i < ca.length; i++){
    var c = ca[i];
    while(c.charAt(0) == ' ')
      c = c.substring(1, c.length);
    if(c.indexOf(nameEQ) == 0)
      return c.substring(nameEQ.length, c.length);
  }
  return null;
}

/** Initialize search tips */
function init_tip(){
  var tip = document.getElementById("tip");
  // Parse querystring for from=
  var query = null
  var items = window.location.search.substr(1).split("&");
  for(var i = 0; i < items.length; i++){
    var keyvalue = items[i].split("=");
    if(keyvalue[0] == "from")
      query = keyvalue[1];
  }
  if(query){
    var url = wwwroot + "/search?tree=" + tree + "&q=" + query + "&redirect=false";
    tip.innerHTML = ("You've been taken to a direct result " +
                     "<a href='{{url}}'>click here</a>" + 
                     " to see all search results").replace("{{url}}", url);
    var q = document.getElementById("query");
    q.value = query;
  }
}

}());
