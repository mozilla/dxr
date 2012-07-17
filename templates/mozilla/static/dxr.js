
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
        window.scroll(0, findPos(elems[0]) - window.innerHeight / 4.0);
      }
    } 
  }
  window.onhashchange();
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

function findPos(obj) {
  var top = 0;
  do{
    top += obj.offsetTop;
  }while(obj = obj.offsetParent);
  return top;
}


