var dxr = (function (){
var dxr = {};

//TODO use findLine to update log, blame, diff, raw links...

/** Set search tip provided to user */
dxr.setTip = function(text){
  var tip = document.getElementById("tip");
  tip.innerHTML = text;
  var query = document.getElementById("query");
  if (query)
    query.style.backgroundImage = "url(" + wwwroot + "/static/icons/page_white_find.png)";
}

/** Set search tip as error message */
dxr.setErrorTip = function(text){
  dxr.setTip("<b>" + text + "</b>");
  var query = document.getElementById("query");
  if (query)
    query.style.backgroundImage = "url(" + wwwroot + "/static/icons/warning.png)";
}

/** Prettify Date an 822 date */
dxr.prettyDate = function(datetime){
  var d  = new Date(Date.parse(datetime));
  var ds = ((new Date()).getTime() - d.getTime()) / 1000;
  var dd = ds / (60 * 60 * 24);
  // If something is wrong return unformatted stirng
  if(isNaN(dd))
    return datetime;
  if(ds < 0)    return "at " + d.toLocaleDateString();
  if(ds < 60)   return "just now";
  if(ds < 120)  return "1 minute ago";
  if(ds < 3600) return Math.floor(ds / 60) + " minutes ago";
  if(ds < 7200) return "1 hour ago";
  if(dd < 1)    return Math.floor(ds / 3600) + " hours ago";
  if(dd < 2)    return "Yesterday";
  if(dd < 7)    return Math.floor(dd) + " days ago";
  if(dd < 31)   return Math.ceil(dd / 7) + " weeks ago";
  return d.toLocaleDateString();
}

/** Write a pretty form of created date */
function prettifyDates(){
  // Prettify all dates as I desire
  // - If only one could this IRL :)
  var dates = document.querySelectorAll(".pretty-date");
  for(var i = 0; i < dates.length; i++){
    var date = dates[i];
    if(date.dataset["datetime"])
      date.innerHTML = dxr.prettyDate(date.dataset["datetime"]);
  }
}

/** Get current tree */
dxr.tree = function(){
  return document.getElementById("tree").value;
}

/** Initialize everything */
window.addEventListener('load', function (){
  prettifyDates();
}, false);
window.addEventListener('pageshow', function (){
  prettifyDates();
}, false);

/** Export dxr as defined here */
return dxr;
}());
