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
    var container = $('#line-numbers');

    //first bind to all .line-number click events only
    container.on('click', '.line-number', function (event) {
        var line = null,
            lastSelectedNum = null,
            //get the clicked line number
            clickedNum = parseInt($(this).attr('id'), 10),
            selected = null;

        //multiselect on shiftkey modifier combined with click
        if (event.shiftKey) {
            var lastSelected = $('.last-selected');
            // on shift, find last-selected code element
            // if lastSelectedNum less than clickedNum go back
            // else if lastSelectedNum greater than line id, go forward
            line = $('#' + clickedNum);
            lastSelectedNum = parseInt(lastSelected.attr('id'), 10);
            if (lastSelectedNum === clickedNum) {
                //toggle a single shiftclicked line
                line.removeClass('last-selected highlighted clicked');
            } else if (lastSelectedNum < clickedNum) {
                //shiftclick descending down the page
                line.addClass('clicked');
                selected = $('.last-selected').nextUntil($('.clicked'));
                // on last element add last-selected class
                $('.line-number').removeClass('clicked highlighted');
            } else if (lastSelectedNum > clickedNum) {
                //shiftclick ascending up the page
                $('.line-number').removeClass('highlighted clicked');
                line.addClass('clicked');
                selected = $('.clicked').nextUntil(lastSelected);
            }
            selected.each(function () {
                selected.addClass('highlighted');
            });

            // since all highlighed items are stripped, add one back
            lastSelected.addClass('highlighted');
            line.addClass('highlighted');
            setWindowHash(clickedNum, lastSelectedNum);

        //single non-shift modified click toggle here
        } else {
            var lastSelected = $('.last-selected'),
                highlightedLines = $('highlighted');
            line = $('#' + clickedNum);
            //Remove existing highlights.
            $('.highlighted').removeClass('last-selected highlighted clicked');
            //toggle highlighting on for any line that was not previously clicked
            if (parseInt(lastSelected.attr('id'), 10) !== clickedNum) {
                //With this we're one better than github, which doesn't allow toggling single lines
                line.toggleClass('last-selected highlighted');
                setWindowHash(clickedNum, false);
            } else {
                history.replaceState(null, '', '#');
            }
        }
    });

    //set the window.location.hash to the highlighted lines
    function setWindowHash(clickedNum, lastSelectedNum) {
        var windowHighlightedLines = null;
        //order of line numbers matters in the url so detect it here
        if (lastSelectedNum === false) {
            windowHighlightedLines = clickedNum;
        } else if (clickedNum < lastSelectedNum) {
            windowHighlightedLines = clickedNum + '-' + lastSelectedNum;
        } else {
            windowHighlightedLines = lastSelectedNum + '-' + clickedNum;
        }
        //window.location.hash causes scrolling, even with a method similar to dxr.js scrollIntoView.
        //history.replaceState accomplishes the same thing without any scrolling whatsoever.
        history.replaceState(null, '', '#' + windowHighlightedLines);
    }

    //highlight line(s) if someone visits a url directly with an #anchor
    $(document).ready(function () {
        var hash = window.location.hash.substring(1),
            lines = hash.split('-'),
            lineStart = '#' + lines[0],
            lineEnd = '#' + lines[1],
            jumpPosition = $(lineStart).offset();

        //check the anchor actually exists, otherwise do nothing
        if ($(lineStart).length) {
            //handle multi-line highlights
            if (lines.length > 1) {
                $(lineStart).addClass('highlighted');
                var selected = $(lineStart).nextUntil(lineEnd);
                selected.addClass('highlighted');
                $(lineEnd).addClass('highlighted');
            //handle a single line highlight
            } else {
                $(lineStart).addClass('last-selected highlighted');
            }
            //for directly linked line(s), scroll to the offset minus 150px for fixed search bar height
            window.scrollTo(0, jumpPosition.top - 150);
        }
    });

});
