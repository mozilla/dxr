(function (){


/** Initialize everything */
window.addEventListener('load', function (){
  init_tip();
}, false);

//TODO use findLine to update log, blame, diff, raw links...


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
