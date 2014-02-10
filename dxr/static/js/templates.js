(function() {(window.nunjucksPrecompiled = window.nunjucksPrecompiled || {})["partial/results.html"] = (function() {function root(env, context, frame, runtime, cb) {
var lineno = null;
var colno = null;
var output = "";
try {
if(env.getFilter("length").call(context, runtime.contextOrFrameLookup(context, frame, "results")) > 0) {
output += "\n    ";
frame = frame.push();
var t_3 = runtime.contextOrFrameLookup(context, frame, "results");
if(t_3) {for(var t_1=0; t_1 < t_3.length; t_1++) {
var t_4 = t_3[t_1];
frame.set("result", t_4);
output += "\n    <div class=\"result\">\n        <div class=\"path\">\n            ";
output += runtime.suppressValue(runtime.memberLookup((t_4),"pathLine", env.autoesc), env.autoesc);
output += "\n        </div>\n        <table class=\"result_snippet\">\n            <caption class=\"visually-hidden\">Query matches in ";
output += runtime.suppressValue(runtime.memberLookup((t_4),"path", env.autoesc), env.autoesc);
output += "</caption>\n            <thead class=\"visually-hidden\">\n                <th scope=\"col\">Line</th>\n                <th scope=\"col\">Code Snippet</th>\n            </thead>\n            <tbody>\n            ";
frame = frame.push();
var t_7 = runtime.memberLookup((t_4),"lines", env.autoesc);
if(t_7) {for(var t_5=0; t_5 < t_7.length; t_5++) {
var t_8 = t_7[t_5];
frame.set("entry", t_8);
output += "\n                <tr>\n                    <td>";
output += runtime.suppressValue(runtime.memberLookup((t_8),"line_number", env.autoesc), env.autoesc);
output += "</td>\n                    <td>\n    <a href=\"";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "wwwroot"), env.autoesc);
output += "/";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "tree"), env.autoesc);
output += "/source/";
output += runtime.suppressValue(runtime.memberLookup((t_4),"path", env.autoesc), env.autoesc);
output += "#";
output += runtime.suppressValue(runtime.memberLookup((t_8),"line_number", env.autoesc), env.autoesc);
output += "\">\n    <code aria-labelledby=\"";
output += runtime.suppressValue(runtime.memberLookup((t_8),"line_number", env.autoesc), env.autoesc);
output += "\">";
output += runtime.suppressValue(runtime.memberLookup((t_8),"line", env.autoesc), env.autoesc);
output += "</code>\n    </a>\n                    </td>\n                </tr>\n            ";
;
}
}
frame = frame.pop();
output += "\n            </tbody>\n        </table>\n    </div>\n    ";
;
}
}
frame = frame.pop();
output += "\n";
;
}
else {
output += "\n    <p class=\"user-message info\">";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "user_message"), env.autoesc);
output += "</p>\n";
;
}
output += "\n";
cb(null, output);
;
} catch (e) {
  cb(runtime.handleError(e, lineno, colno));
}
}
return {
root: root
};
})();
})();
(function() {(window.nunjucksPrecompiled = window.nunjucksPrecompiled || {})["partial/switch_tree.html"] = (function() {function root(env, context, frame, runtime, cb) {
var lineno = null;
var colno = null;
var output = "";
try {
var macro_t_1 = runtime.makeMacro(
["tree_tuples", "selected_tree"], 
[], 
function (l_tree_tuples, l_selected_tree, kwargs) {
frame = frame.push();
kwargs = kwargs || {};
frame.set("tree_tuples", l_tree_tuples);
frame.set("selected_tree", l_selected_tree);
var output= "";
output += "\n  ";
if(env.getFilter("length").call(context, l_tree_tuples) > 1) {
output += "\n    <section id=\"tree-selector\" class=\"tree-selector\">\n      <button type=\"button\" class=\"ts-select-trigger\" aria-label=\"Switch Tree\">\n        <!-- arrow icon using icon font -->\n        <span aria-hidden=\"true\" data-icon-arrow=\"&#xe801;\" class=\"selector-arrow\">\n          <!-- tree icon using icon font -->\n          <span aria-hidden=\"true\" data-icon=\"&#xe800;\"></span>\n          <span class='current-tree'>Switch Tree</span>\n        </span>\n      </button>\n      <div class=\"select-options ts-modal\" aria-expanded=\"false\">\n        <form name=\"options-filter\" class=\"options-filter\" data-active=\"false\">\n          <label for=\"filter-txt\" class=\"visually-hidden\">Filter Trees</label>\n          <input type=\"text\" name=\"filter-txt\" id=\"filter-txt\" placeholder=\"Filter trees\" />\n          <input type=\"submit\" value=\"Filter\" class=\"visually-hidden\" />\n        </form>\n        <ul class=\"selector-options\" tabindex=\"-1\">\n          ";
frame = frame.push();
var t_4 = l_tree_tuples;
if(t_4) {var t_2;
if(runtime.isArray(t_4)) {
for(t_2=0; t_2 < t_4.length; t_2++) {
var t_5 = t_4[t_2][0]
frame.set("tree", t_4[t_2][0]);
var t_6 = t_4[t_2][1]
frame.set("url", t_4[t_2][1]);
var t_7 = t_4[t_2][2]
frame.set("description", t_4[t_2][2]);
output += "\n            <li>\n              <a href=\"";
output += runtime.suppressValue(t_6, env.autoesc);
output += "\" ";
if(t_5 == l_selected_tree) {
output += "class=\"selected\" aria-checked=\"true\"";
;
}
output += ">\n                <span class=\"selector-option-label\">";
output += runtime.suppressValue(t_5, env.autoesc);
output += "</span>\n                <span class=\"selector-option-description\">";
output += runtime.suppressValue(t_7, env.autoesc);
output += "</span>\n              </a>\n            </li>\n          ";
;
}
} else {
t_2 = -1;
for(var t_8 in t_4) {
t_2++;
var t_9 = t_4[t_8];
frame.set("tree", t_8);
frame.set("url", t_9);
output += "\n            <li>\n              <a href=\"";
output += runtime.suppressValue(t_9, env.autoesc);
output += "\" ";
if(t_8 == l_selected_tree) {
output += "class=\"selected\" aria-checked=\"true\"";
;
}
output += ">\n                <span class=\"selector-option-label\">";
output += runtime.suppressValue(t_8, env.autoesc);
output += "</span>\n                <span class=\"selector-option-description\">";
output += runtime.suppressValue(t_7, env.autoesc);
output += "</span>\n              </a>\n            </li>\n          ";
;
}
}
}
frame = frame.pop();
output += "\n        </ul>\n      </div>\n    </section>\n  ";
;
}
output += "\n";
frame = frame.pop();
return new runtime.SafeString(output);
});
context.addExport("tree_menu");
context.setVariable("tree_menu", macro_t_1);
output += "\n";
cb(null, output);
;
} catch (e) {
  cb(runtime.handleError(e, lineno, colno));
}
}
return {
root: root
};
})();
})();
(function() {(window.nunjucksPrecompiled = window.nunjucksPrecompiled || {})["context_menu.html"] = (function() {function root(env, context, frame, runtime, cb) {
var lineno = null;
var colno = null;
var output = "";
try {
output += "<ul id=\"context-menu\" class=\"context-menu\" tabindex=\"0\">\n    ";
frame = frame.push();
var t_3 = runtime.contextOrFrameLookup(context, frame, "menuItems");
if(t_3) {for(var t_1=0; t_1 < t_3.length; t_1++) {
var t_4 = t_3[t_1];
frame.set("item", t_4);
output += "\n        <li><a href=\"";
output += runtime.suppressValue(runtime.memberLookup((t_4),"href", env.autoesc), env.autoesc);
output += "\" class=\"";
output += runtime.suppressValue(runtime.memberLookup((t_4),"icon", env.autoesc), env.autoesc);
output += "\">";
output += runtime.suppressValue(runtime.memberLookup((t_4),"text", env.autoesc), env.autoesc);
output += "</a></li>\n    ";
;
}
}
frame = frame.pop();
output += "\n</ul>\n";
cb(null, output);
;
} catch (e) {
  cb(runtime.handleError(e, lineno, colno));
}
}
return {
root: root
};
})();
})();
(function() {(window.nunjucksPrecompiled = window.nunjucksPrecompiled || {})["path_line.html"] = (function() {function root(env, context, frame, runtime, cb) {
var lineno = null;
var colno = null;
var output = "";
try {
if(runtime.contextOrFrameLookup(context, frame, "is_first_or_only")) {
output += "<a class=\"";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "icon_class"), env.autoesc);
output += "\" ";
if(runtime.contextOrFrameLookup(context, frame, "is_dir")) {
output += "data-path=\"";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "data_path"), env.autoesc);
output += "\"";
;
}
output += " href=\"";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "url"), env.autoesc);
output += "\">";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "display_path"), env.autoesc);
output += "</a>";
;
}
else {
output += "<span class=\"path-separator\">/</span><a ";
if(runtime.contextOrFrameLookup(context, frame, "is_dir")) {
output += "data-path=\"";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "data_path"), env.autoesc);
output += "\"";
;
}
output += " href=\"";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "url"), env.autoesc);
output += "\">";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "display_path"), env.autoesc);
output += "</a>";
;
}
cb(null, output);
;
} catch (e) {
  cb(runtime.handleError(e, lineno, colno));
}
}
return {
root: root
};
})();
})();
(function() {(window.nunjucksPrecompiled = window.nunjucksPrecompiled || {})["results_container.html"] = (function() {function root(env, context, frame, runtime, cb) {
var lineno = null;
var colno = null;
var output = "";
try {
env.getTemplate("partial/switch_tree.html", function(t_2,t_1) {
if(t_2) { cb(t_2); return; }
t_1.getExported(function(t_3,t_1) {
if(t_3) { cb(t_3); return; }
if(t_1.hasOwnProperty("tree_menu")) {
var t_4 = t_1.tree_menu;
} else {
cb(new Error("cannot import 'tree_menu'")); return;
}
context.setVariable("tree_menu", t_4);
output += "\n<p class=\"top-of-tree\">Results from the <a href=\"";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "top_of_tree"), env.autoesc);
output += "\">";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "tree"), env.autoesc);
output += "</a> tree:</p>\n\n";
output += runtime.suppressValue((lineno = 3, colno = 10, runtime.callWrap(t_4, "tree_menu", [runtime.contextOrFrameLookup(context, frame, "tree_tuples"),runtime.contextOrFrameLookup(context, frame, "tree")])), env.autoesc);
output += "\n\n";
env.getTemplate("partial/results.html", function(t_7,t_5) {
if(t_7) { cb(t_7); return; }
t_5.render(context.getVariables(), frame.push(), function(t_8,t_6) {
if(t_8) { cb(t_8); return; }
output += t_6
output += "\n";
cb(null, output);
})})})});
} catch (e) {
  cb(runtime.handleError(e, lineno, colno));
}
}
return {
root: root
};
})();
})();
