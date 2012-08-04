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
    var a = as[i];
    if(a.dataset["menu"]){
      a.addEventListener('click', showMenu, false);
    }
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

/** Initialize everything */
window.addEventListener('load', function (){
  window.addEventListener('hashchange', hashchanged, false);
  init_menu();
  hashchanged();
}, false);

}());
