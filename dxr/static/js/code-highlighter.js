/* jshint devel:true, esnext: true */
/* globals nunjucks: true, $ */

/**
 * This file consists of four major pieces of functionality for a file view:
 * 0) Any combination of 1) and 2)
 * 1) Multi-select highlight lines with shift key and update window.location.hash
 * 2) Multi-select highlight lines with command/control key and update window.location.hash
 * 3) Highlight lines when page loads, if window.location.hash exists
 */

$(function () {
    'use strict';
    var container = $('#line-numbers'),
        lastModifierKey = null, // use this as a sort of canary/state indicator showing the last user action
        singleLinesArray = [], //track single highlighted lines here
        rangesArray = []; // track ranges of highlighted lines here 

    //sort a one dimensional array in Ascending order
    function sortAsc(a, b) {
        return a - b;
    }

    function generateSelectedArrays() {
        var line = null,
            rangeMax = null,
            lines = [],
            rangesArray = [],
            singleLinesArray = [];
        
        var multiSelected = document.getElementsByClassName('multihighlight');
        var singleSelected = document.getElementsByClassName('highlighted');

        function generateLines(selected, lines) {
            for (var i = 0; i < selected.length; i++ ) {
                lines.push(parseInt(selected[i].id, 10));
            }
            return lines;
        }

        lines = generateLines(multiSelected, lines);
        lines = generateLines(singleSelected, lines);

        // strip all single lines, e.g. those without an adjacent line+1 == nextLine
        for (var s = lines.length - 1; s >= 0; s--) {
            line = lines[s];
            // this presumes selected is sorted in asc order, if not it won't work
            if (line !== lines[s + 1] - 1 && line !== lines[s - 1] + 1) {
                singleLinesArray.push(line);
                lines.splice(s, 1);
            }
        }

        //this presumes selected is sorted in asc order after single lines have been removed
        while (lines.length > 0) {
            line = lines[0];
            var pos = 1;
            while (line === lines[pos] - pos) {
                rangeMax = lines[pos];
                pos++;
            }
            rangesArray.push([line, rangeMax]);
            lines.splice(0, pos);
        }

        return [singleLinesArray.sort(sortAsc), rangesArray];
    }

    //generate the window.location.hash based on singleLinesArray and rangesArray
    function setWindowHash() {
        var singles = null,
            ranges = [],
            windowHash = null,
            reCleanup = /(^#?,|,$)/;

        [singleLinesArray, rangesArray] = generateSelectedArrays();
        for (var r = 0; r < rangesArray.length; r++) {
            ranges.push(rangesArray[r].join('-'));
        }
        singles = singleLinesArray.join(',');
        ranges = ranges.sort().join(',');
        if (singles.length && ranges.length) {
            windowHash = '#' + singles + ',' + ranges;
        } else if (singles.length && ranges === '') {
            windowHash = '#' + singles;
        } else if (singles === '' && ranges.length) {
            windowHash = '#' + ranges;
        }

        if (windowHash) {
            windowHash = windowHash.replace(reCleanup, '');
            history.replaceState(null, '', windowHash);
        }
    }

    //parse windwow.location.hash on new requsts into two arrays
    //one of single lines and one multilines
    //use with singleLinesArray and rangesArray for adding/changing new highlights
    function getSortedHashLines() {
        var highlights = window.location.hash.substring(1),
            lineStart = null,
            reRanges = /[0-9]+-[0-9]+/g,
            reCleanup = /(#,|-|,$)/,
            range = null,
            ranges = null,
            firstRange = null;

        ranges = highlights.match(reRanges);
        if (ranges !== null) {
            ranges = ranges.sort();
            firstRange = ranges[0];
            //strip out multiline items like 12-15, so that all that is left are single lines
            //populate rangesArray for reuse if a user selects more ranges later
            for (var i=0; i < ranges.length; i++) {
                highlights = highlights.replace(ranges[i], '');
                highlights = highlights.replace(',,', ',');
                range = ranges[i].split('-');
                //make sure rangesArray is comprised of integers only
                rangesArray.push([parseInt(range[0], 10), parseInt(range[1], 10)]);
            }
            //strip leading, trailing commas, and stray dashes
            highlights = highlights.replace(reCleanup ,'');
            highlights = highlights.trim();
        }

        if (highlights.length) {
            //make an array of integers and sort it for the remaining single lines
            highlights = highlights.split(',');
            for (var h = 0; h < highlights.length; h++) {
                highlights[h] = parseInt(highlights[h], 10);
            }
            highlights = highlights.sort(sortAsc);
            //set the global singleLinesArry for reuse
            singleLinesArray = highlights;

        } else {
            //this happens if there is no single line in a url
            //without setting this the url gets an NaN element in it
            highlights = null;
        }

        //a url can look like foo#12,15,20-25 or foo#12-15,18,20-25 or foo#1,2,3 etc.
        //the lineStart should be the smallest integer in the single or highlighted ranges
        //this ensures a proper position to which to scroll once the page loads
        if (firstRange && highlights !== null) {
            if (highlights[0] < firstRange[0]) {
                lineStart = highlights[0];
            } else if (highlights[0] > firstRange[0]) {
                lineStart = firstRange[0];
            }
        } else if (firstRange && highlights === null) {
            lineStart = firstRange[0][0];
        } else if (firstRange === null && highlights) {
            lineStart = highlights[0];
        } else {
            lineStart = null;
        }

        return {'lineStart':lineStart, 'highlights':highlights, 'ranges':ranges};
    }

    //first bind to all .line-number click events only
    container.on('click', '.line-number', function (event) {
        var line = null,
            lastSelectedNum = null,
            lastSelected = $('.last-selected'),
            //get the clicked line number
            clickedNum = parseInt($(this).attr('id'), 10),
            selected = null,
            self = this;

        //multiselect on shiftkey modifier combined with click
        if (event.shiftKey) {
            var classToAdd = 'multihighlight';
            // on shift, find last-selected code element
            // if lastSelectedNum less than clickedNum go back
            // else if lastSelectedNum greater than line id, go forward
            line = $('#' + clickedNum);
            lastSelectedNum = parseInt(lastSelected.attr('id'), 10);
            if (lastSelectedNum === clickedNum) {
                //toggle a single shiftclicked line
                line.removeClass('last-selected highlighted clicked multihighlight');
            } else if (lastSelectedNum < clickedNum) {
                //shiftclick descending down the page
                line.addClass('clicked');
                selected = $('.last-selected').nextUntil($('.clicked'));
                $('.last-selected').removeClass('clicked');
            } else if (lastSelectedNum > clickedNum) {
                //shiftclick ascending up the page
                $('.line-number').removeClass('clicked');
                line.addClass('clicked');
                selected = $('.clicked').nextUntil($('.last-selected'));
            }
            selected.each(function () {
                selected.addClass(classToAdd);
            });
            //set the last used modifier key
            lastModifierKey = 'shift';
            // since all highlighed items are stripped, add one back, mark new last-selected
            lastSelected.addClass(classToAdd);
            lastSelected.removeClass('last-selected');
            line.addClass(classToAdd);
            line.addClass('last-selected');

        } else if (event.shiftKey && lastModifierKey === 'singleSelectKey') {
            //if ctrl/command was last pressed, add multihighlight class to new lines
            $('.line-number').removeClass('clicked');
            line = $('#' + clickedNum);
            line.addClass('clicked');
            selected = $('.last-selected').nextUntil($('.clicked'));
            selected.each(function () {
                selected.addClass('multihighlight');
            });
            line.addClass('multihighlight');

        } else if (event.ctrlKey || event.metaKey) {
            //a single click with ctrl/command highlights one line and preserves existing highlights
            lastModifierKey = 'singleSelectKey';
            line = $('#' + clickedNum);
            $('.highlighted').addClass('multihighlight');
            $('.line-number').removeClass('last-selected clicked highlighted');
            line.toggleClass('clicked last-selected multihighlight');

        } else {
            //set lastModifierKey ranges and single lines to null, then clear all highlights
            lastModifierKey = null;
            lastSelected = $('.last-selected');
            line = $('#' + clickedNum);
            //Remove existing highlights.
            $('.line-number').removeClass('last-selected highlighted multihighlight clicked');
            //empty out single lines and ranges arrays
            rangesArray = [];
            singleLinesArray = [];
            //toggle highlighting on for any line that was not previously clicked
            if (parseInt(lastSelected.attr('id'), 10) !== clickedNum) {
                //With this we're one better than github, which doesn't allow toggling single lines
                line.toggleClass('last-selected highlighted');
            } else {
                history.replaceState(null, '', '#');
            }
        }
        setWindowHash();
    });

    //highlight line(s) if someone visits a url directly with an #anchor
    $(document).ready(function () {
        if (window.location.hash.substring(1)) {
            var toHighlight = getSortedHashLines(),
                jumpPosition = $('#' + toHighlight.lineStart).offset(),
                highlights = toHighlight.highlights,
                ranges = toHighlight.ranges;

            if (highlights !== null) {
                //add single line highlights
                for (var i=0; i < highlights.length; i++) {
                    $('#' + highlights[i]).addClass('highlighted');
                }
            }

            if (ranges !== null) {
                //handle multiple sets of multi-line highlights from an incoming url
                for (var j=0; j < ranges.length; j++) {
                    var lines = ranges[j].split('-');
                    //handle a single set of line ranges here; the c counter must be <= since it is a line id
                    for (var c = lines[0]; c <= lines[1]; c++) {
                        $('#' + c).addClass('highlighted');
                    }
                }
            }

            //for directly linked line(s), scroll to the offset minus 150px for fixed search bar height
            //but only scrollTo if the offset is more than 150px in distance from the top of the page
            jumpPosition = parseInt(jumpPosition.top, 10) - 150;
            if (jumpPosition >= 0) {
                window.scrollTo(0, jumpPosition);
            } else {
                window.scrollTo(0, 0);
            }
            //tidy up an incoming url that might be typed in manually
            setWindowHash();
        }
    });

});