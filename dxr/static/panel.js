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

var panelVisible = true;
var panelTitle = "";
/** Toggle the panel visiblity (save state to cookie) */
function togglePanel(){
  var content = document.getElementById("panel-content");
  if(panelVisible){
    content.style.display = "none";
  }else{
    content.style.display = "block";
  }
  panelVisible = !panelVisible;
  createCookie("panel-state" + panelTitle, (panelVisible ? "true" : "false"), 42);
}

/** Initialize everything */
window.addEventListener('load', function (){
  var panelToggle = document.getElementById("panel-toggle");
  panelTitle = panelToggle.innerHTML;
  var val = readCookie("panel-state" + panelTitle);
  if(val != null){
    // Read and flip it
    panelVisible = !(val == "true" ? true : false);
    // Make toggle it back to what we read
    togglePanel();
  }
  panelToggle.addEventListener('click', togglePanel, false);
}, false);

}());
