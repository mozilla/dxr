/** Menu module for showing nice context menus */
var menu = (function (){
var menu = {};

/** Menu id */
var _menuId = 'inline-menu';

/** Escape HTML Entitites */
function htmlEntities(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Launch a menu under element el */
menu.launch = function(el){
  var x, y;
  x = menu.posLeft(el);
  y = menu.posTop(el) + el.offsetHeight;
  menu.launchAt(x, y);
};

/** Populate menu
 * links is a list of JSON objects with href, title, icon, text
 */
menu.populate = function(links){
  var content = ""
  for(var i = 0; i < links.length; i++){
    var link = links[i];
    var icon = wwwroot + "/static/icons/" + link.icon + ".png";
    content += "<a href=\"" + htmlEntities(link.href) + "\"";
    content += " title=\"" + htmlEntities(link.title) + "\"";
    content += " style=\"background-image: url('" + icon + "')\">";
    content += htmlEntities(link.text) + "</a>";
  }
  var m = document.getElementById(_menuId);
  m.innerHTML = content;
};

/** Launch menu at x, y */
menu.launchAt = function(x, y){
  var m = document.getElementById(_menuId);
  m.style.left    = x + "px";
  m.style.top     = y + "px";
  m.style.display = 'block';
};

/** Find position of el from top */
menu.posTop = function(el){
  var top = 0;
  do{
    top += el.offsetTop;
  }while(el = el.offsetParent);
  return top;
};

/** Find position of el from left */
menu.posLeft = function(el){
  var left = 0;
  do{
    left += el.offsetLeft;
  }while(el = el.offsetParent);
  return left;
};

/** Hide menu */
menu.hide = function(){
  var m = document.getElementById(_menuId);
  m.style.display = 'none';
};

/** Initialize module */
window.addEventListener('load', function(){
  // On mousedown we hide the menu
  window.addEventListener('mousedown', menu.hide, false);

  // Stop event from propergating to window
  var m = document.getElementById(_menuId);
  m.addEventListener('mousedown', function(e) {
    e.stopPropagation();
  }, false);
}, false);

// Export menu as defined here
return menu;
}());
