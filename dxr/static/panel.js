(function() {

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

/** Initialize everything */
window.addEventListener('load', function (){
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

}());
