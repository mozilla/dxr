/** Add auxiliary string method for indexOf using regexp
 * Credits to: http://stackoverflow.com/a/274094
 */
String.prototype.regexIndexOf = function(regex, startpos) {
    var indexOf = this.substring(startpos || 0).search(regex);
    return (indexOf >= 0) ? (indexOf + (startpos || 0)) : indexOf;
}

/** Add auxiliary string method for LastIndexOf using regexp
 * Credits to: http://stackoverflow.com/a/274094
 */
String.prototype.regexLastIndexOf = function(regex, startpos) {

    if (!regex.global) {
      var flags = "g" + (regex.ignoreCase ? "i" : "") + (regex.multiLine ? "m" : "");
      regex = new RegExp(regex.source, flags);
    }

    if (typeof (startpos) == "undefined") {
        startpos = this.length;
    } else if (startpos < 0) {
        startpos = 0;
    }

    var stringToWorkWith = this.substring(0, startpos + 1);
    var lastIndexOf = -1;
    var nextStop = 0;

    while((result = regex.exec(stringToWorkWith)) != null) {
        lastIndexOf = result.index;
        regex.lastIndex = ++nextStop;
    }
    return lastIndexOf;
}
