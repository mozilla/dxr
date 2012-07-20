
function toggle_panel(){
  var panel_toggle = document.getElementById("panel-toggle");
  var sections = document.querySelectorAll(".section");
  if(panel_toggle.innerHTML == "Hide Navigation"){
    panel_toggle.innerHTML = "Show Navigation";
    for(var i = 0; i < sections.length; i++){
      sections[i].style.display = "none";
    }
  }else{
    panel_toggle.innerHTML = "Hide Navigation";
    for(var i = 0; i < sections.length; i++){
      sections[i].style.display = "block";
    }
  }
}

function init(){
  window.onhashchange = function(e){
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
  window.onhashchange();
  init_menu();
}

//TODO use findLine to update log, blame, diff, raw links...

var pattern = /^#l[0-9]+$/;
function findLine(){
  var result;
  if((result = pattern.exec(window.location.hash)) != null){
    return parseInt(result[0].substr(2));
  }
  return -1;
}

function findPosTop(obj) {
  var top = 0;
  do{
    top += obj.offsetTop;
  }while(obj = obj.offsetParent);
  return top;
}

function findPosLeft(obj) {
  var left = 0;
  do{
    left += obj.offsetLeft;
  }while(obj = obj.offsetParent);
  return left;
}

function init_menu(){
  //TODO Cleanup this, use add eventlistener, and clean popup on mouseup on window
  var m = document.getElementById("inline-menu");
  var as = document.querySelectorAll(".file-lines a");
  for(var i = 0; i < as.length; i++){
    var a = as[i];
    var menu = a.dataset["menu"];
    if(menu){
      a.onclick = function(e){
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
    }
  }
  document.body.onmouseup = function(){
    m.style.display = "none";
  }
}
