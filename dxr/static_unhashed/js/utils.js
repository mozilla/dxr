/**
 * Handles Esc key events.
 * @param {function} func - The function to execute on esc
 */
function onEsc(func) {
    window.addEventListener('keyup', function (event) {
        // 'key' is the standard but has not been implemented in Gecko
        // yet, see https://bugzilla.mozilla.org/show_bug.cgi?id=680830
        // so, we check both.
        var keyPressed = event.key || event.keyCode;
        // esc key pressed.
        if (keyPressed === 27 || keyPressed === 'Escape' || keyPressed === 'Esc')
            func();
        else
            return true;
        });
}

/** Add auxiliary string method for indexOf using regexp
 * Credits to: http://stackoverflow.com/a/274094
 */
String.prototype.regexIndexOf = function(regex, startpos) {
    var indexOf = this.substring(startpos || 0).search(regex);
    return (indexOf >= 0) ? (indexOf + (startpos || 0)) : indexOf;
};

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

    while((result = regex.exec(stringToWorkWith)) !== null) {
        lastIndexOf = result.index;
        regex.lastIndex = ++nextStop;
    }
    return lastIndexOf;
};

/**
 * Hide the Help pop-up.
 */
function hideHelp() {

    var helpIcon = $('.help-icon'),
        helpMsg = helpIcon.find('.help-msg');

    helpIcon.removeClass('open');
    helpMsg.hide();
}

/**
 * Close options and help pop-ups.
 */
function hideOptionsAndHelp() {
    // Because the tree selector can be injected by a JS
    // template, we need to use the selector directly here,
    // as the element will not exist on DOM ready.
    $('.select-options, .sf-select-options').hide();
    hideHelp();
}

/**
 * Return the extension of the given path, or '' if no extension exists.
 */
function extension(path) {
    var file = path.substring(path.lastIndexOf('/') + 1),
        lastDotPos = file.lastIndexOf('.');
    if (lastDotPos === -1) {
        return '';
    }
    return file.substring(lastDotPos + 1);
}

/**
 * Remove each parameter name in the params array from url's query parameters.
 */
function removeParams(url, params) {
    var i, paramRegex;
    function dropAmp(fullMatch, ampOrQuestion) {
        // Keep a leading question mark, drop a leading ampersand.
        return (ampOrQuestion === '?') ? '?' : '';
    }
    for (i = 0; i < params.length; i++) {
        paramRegex = new RegExp('([&?])' + params[i] + '=[^&]+');
        url = url.replace(paramRegex, dropAmp);
    }
    return url.replace('?&', '?');
}
