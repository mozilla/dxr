(function (){

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
    q.addEventListener('keyup', function(){
      if(q.value != query)
        redirect.value = "true";
      else
        redirect.value = "false";
    }, false);
  }
}

/** Initialize everything */
window.addEventListener('load', function (){
  window.addEventListener('hashchange', hashchanged, false);
  init_tip();
  init_menu();
  hashchanged();
}, false);

}());
