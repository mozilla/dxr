/* jshint devel:true, esnext: true */
/* globals nunjucks: true, $ */

/**
 * This file consists of three major pieces of functionality for a file view:
 * 1) Multi-select highlight lines with shift key and set window.location.hash
 * 2) Toggle the .highlighted class for a single line and set window.location.hash
 * 3) Highlight lines when page loads, if a numbered window.location.hash exists
 */

$(function () {
    'use strict';
    var container = $("#line-numbers");

    //first bind to all .line-number click events only
    container.on("click", ".line-number", function (event) {
        var line = null,
            lastSelectedNum = null,
            //get the clicked line number
            clickedNum = parseInt($(this).attr('id'), 10),
            selected = null;

        //multiselect on shiftkey modifier combined with click
        if (event.shiftKey) {
            var lastSelected = $(".last-selected");
            // on shift, find last-selected code element
            // if lastSelectedNum less than clickedNum go back
            // else if lastSelectedNum greater than line id, go forward
            line = $("#" + clickedNum);
            lastSelectedNum = parseInt(lastSelected.attr('id'), 10);
            if (lastSelectedNum === clickedNum) {
                //toggle a single shiftclicked line
                line.removeClass("last-selected highlighted clicked");
            } else if (lastSelectedNum < clickedNum) {
                //shiftclick descending down the page
                line.addClass("clicked");
                selected = $(".last-selected").nextUntil($(".clicked"));
                // on last element add last-selected class
                $(".line-number").removeClass("clicked highlighted");
            } else if (lastSelectedNum > clickedNum) {
                //shiftclick ascending up the page
                $(".line-number").removeClass("highlighted clicked");
                line.addClass("clicked");
                selected = $(".clicked").nextUntil(lastSelected);
            }
            if (selected.length > 0) {
                selected.each(function () {
                    selected.addClass("highlighted");
                });
            }

            // since all highlighed items are stripped, add one back
            lastSelected.addClass("highlighted");
            line.addClass("highlighted");
            setWindowHash(clickedNum, lastSelectedNum);

        //single non-shift modified click toggle here
        } else {
            var lastSelected = $(".last-selected");
            line = $("#" + clickedNum);

            if (parseInt(lastSelected.attr('id'), 10) !== clickedNum) {
                $(".highlighted").removeClass("last-selected highlighted");
                line.toggleClass("last-selected highlighted");
                window.location.hash = line.attr('id');
            } else {
                $(".highlighted").removeClass("last-selected highlighted");
                window.location.hash = '';
            }
        }
    });

    //set the window.location.hash to the highlighted lines
    function setWindowHash(clickedNum, lastSelectedNum) {
        var windowHighlightedLines = null;
        //order of line numbers matters in the url, detect it here
        if (clickedNum < lastSelectedNum) {
            windowHighlightedLines = clickedNum + "-" + lastSelectedNum;
        } else {
            windowHighlightedLines = lastSelectedNum + "-" + clickedNum;
        }
        window.location.hash = windowHighlightedLines;
    }

    //highlight line(s) if someone visits a url directly with an #anchor
    $(document).ready(function () {
        var hash = window.location.hash.replace("#", ""),
            lines = hash.split("-");

        //handle multi-line highlights
        if (lines.length > 1) {
            for (var i = lines[0]; i <= lines[1]; ++i) {
                var line = document.getElementById(i);
                line.classList.add('highlighted');
            }
        //handle a single line highlight, 'lines' is one line number here
        } else {        
            document.getElementById(lines[0]).classList.add('highlighted');
        }
    });

});
