/* jshint devel:true */
/* globals nunjucks: true, $ */

/**
 * This file consists of four major pieces of functionality for a file view:
 * 0) Any combination of 1) and 2)
 * 1) Multi-select highlight lines with shift key and update window.location.hash
 * 2) Multi-select highlight lines with command/control key and update window.location.hash
 * 3) Highlight lines when page loads, if window.location.hash exists
 * In addition, we update the permalink and other nav links to keep them
 * synchronized with window.location.
 */

$(function () {
    'use strict';
    var container = $('#line-numbers'),
        navlinks = $('.panel a'), // whenever we update window.location, maybe update these too
        permalink = $('.permalink'), // a subset of navlinks, but it has more specific update rules
        lastModifierKey = null, // use this as a sort of canary/state indicator showing the last user action
        singleLinesArray = [], //track single highlighted lines here
        rangesArray = []; // track ranges of highlighted lines here

    //sort a one dimensional array in Ascending order
    function sortAsc(a, b) {
        return a - b;
    }
    function stringToRange(a) {
        a = a.split('-');
        a[0] = parseInt(a[0],10);
        a[1] = parseInt(a[1],10);
        return a;
    }
    function sortRangeAsc(a, b) {
        // tweak in order to account for inverted ranges like 150-120
        return Math.min(a[0],a[1]) - Math.min(b[0],b[1]);
    }
    function generateSelectedArrays() {
        var line = null,
            rangeMax = null,
            lines = [],
            rangesArray = [],
            singleLinesArray = [];

        var multiSelected = $('.line-number.multihighlight');
        var singleSelected = $('.line-number.highlighted');

        function generateLines(selected, lines) {
            for (var i = 0; i < selected.length; i++) {
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
        //return sorted arrays
        return [singleLinesArray.sort(sortAsc), rangesArray.sort(sortRangeAsc)];
    }

    //generate the window.location.hash based on singleLinesArray and rangesArray
    function setWindowHash() {
        var windowHash = null,
            s = null,
            r = null,
            reCleanup = /(^#?,|,$)/;
        var selectedArray = generateSelectedArrays(); // generates sorted arrays
        var singleLinesArray = selectedArray[0];
        var rangesArray = selectedArray[1];
        var firstNumber;
        // eliminate duplication
        for (s = 0; s < singleLinesArray.length; s++) {
            for (r = 0; r < rangesArray.length; r++) {
                if (s >= rangesArray[r][0] && s <= rangesArray[r][1]) {
                    singleLinesArray.splice(s,1);
                    s--;
                }
            }
        }
        if (singleLinesArray.length || rangesArray.length) {
            windowHash = '#';
        }
        for (s = 0, r = 0; s < singleLinesArray.length || r < rangesArray.length;) {
            // if no ranges left or singleLine < range add singleLine to hash
            // if no singleLines left or range < singleLine add range to hash
            if ((r == rangesArray.length) || (singleLinesArray[s] < rangesArray[r][0])) {
                windowHash += singleLinesArray[s] + ',';
                if (!firstNumber) {
                    firstNumber = singleLinesArray[s];
                }
                s++;
            } else if (( s == singleLinesArray.length) || (rangesArray[r][0] < singleLinesArray[s])) {
                windowHash += rangesArray[r][0] + '-' + rangesArray[r][1] + ',';
                if (!firstNumber) {
                    firstNumber = rangesArray[r][0];
                }
                r++;
            }
        }
        if (windowHash) {
            windowHash = windowHash.replace(reCleanup, '');
            updateHash(windowHash, firstNumber);
        }
    }

    //update places where hash location is used: window, permalink, other nav links
    function updateHash(hash, lineNumber) {
        if (permalink.length > 0)
            updatePermalink(hash);
        updateNavLinks(lineNumber);
        history.replaceState(null, '', hash);
    }

    //update the permalink href based on the windowHash.
    function updatePermalink(windowHash) {
        var permalink_href = permalink.attr('href'),
            hash_loc = permalink_href.indexOf('#');
        // If the link already has #, then cut that it off.
        if (hash_loc >= 0)
            permalink_href = permalink_href.substring(0, hash_loc);
        permalink.attr('href', permalink_href + windowHash);
    }

    //replace any occurrence of {{line}} in hrefs with the last-selected line.
    //unless the last-selected line is undefined, then remove {{line}} from the
    //displayed url.
    function updateNavLinks(lineNumber) {
        navlinks.each(function() {
            var $this = $(this);
            if ($this.data('template')) {
                $this.attr('href', $this.data('template').replace(/{{line}}/g, lineNumber || ''));
            }
        });
    }

    //parse window.location.hash on new requests into two arrays
    //one of single lines and one multilines
    //use with singleLinesArray and rangesArray for adding/changing new highlights
    function getSortedHashLines() {
        var highlights = window.location.hash.substring(1),
            lineStart = null,
            reRanges = /[0-9]+-[0-9]+/g,
            reCleanup = /[^0-9,]/g,
            ranges = null,
            firstRange = null;
        highlights = highlights.replace(/ /g,''); // clean whitespace
        ranges = highlights.match(reRanges);
        if (ranges !== null) {
            ranges = ranges.map(stringToRange).sort(sortRangeAsc);
            //strip out multiline items like 12-15, so that all that is left are single lines
            //populate rangesArray for reuse if a user selects more ranges later
            for (var i = 0; i < ranges.length; i++) {
                highlights = highlights.replace(ranges[i].join('-'), '');
                ranges[i].sort(sortAsc);
            }
            // add the ordered ranges to the rangesArray
            rangesArray = rangesArray.concat(ranges);
            firstRange = rangesArray[0];
            highlights = highlights.replace(reCleanup ,''); // clean anything other than digits and commas
            highlights = highlights.replace(/,,+/g, ','); // clean multiple commas
            highlights = highlights.replace(/^,|,$/g, ''); // clean leading and tailing comas
        }

        if (highlights.length) {
            //make an array of integers and sort it for the remaining single lines
            highlights = highlights.split(',');
            for (var h = 0; h < highlights.length; h++) {
                highlights[h] = parseInt(highlights[h], 10);
                //in case some unwanted string snuck by remove it
                if (isNaN(highlights[h])) {
                    highlights.splice(h,1);
                    h--;
                }
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
        if (firstRange !== null && highlights !== null) {
            if (highlights[0] < firstRange[0]) {
                lineStart = highlights[0];
            } else if (highlights[0] > firstRange[0]) {
                lineStart = firstRange[0];
            }
        } else if (firstRange !== null && highlights === null) {
            lineStart = firstRange[0];
        } else if (firstRange === null && highlights !== null) {
            lineStart = highlights[0];
        } else {
            lineStart = null;
        }

        return {'lineStart':lineStart, 'highlights':singleLinesArray, 'ranges':rangesArray};
    }

    //first bind to all .line-number click events only
    container.on('click', '.line-number', function (event) {
        var clickedNum = parseInt($(this).attr('id'), 10), // get the clicked line number
            line = $('#' + clickedNum + ', #line-' + clickedNum), // get line-number and code
            lastSelectedLine = $('.line-number.last-selected, code.last-selected'),
            lastSelectedNum = parseInt($('.line-number.last-selected').attr('id'), 10), // get last selected line number as integer
            selectedLineNums = null, // used for selecting elements with class .line-number
            selectedLineCode = null, // used for selecting code elements in .code class
            self = this;

        //multiselect on shiftkey modifier combined with click
        if (event.shiftKey) {
            var classToAdd = 'multihighlight';
            // on shift, find last-selected code element
            // if lastSelectedNum less than clickedNum go back
            // else if lastSelectedNum greater than line id, go forward
            if (isNaN(lastSelectedNum)) {
                //shiftclick with no previous lastSelectedNum
                line.addClass('clicked');
                selectedLineNums = $('.line-number.clicked');
                selectedLineCode = $('code.clicked');
                line.addClass(classToAdd);
                line.addClass('last-selected');
            }
            else if (lastSelectedNum === clickedNum) {
                //toggle a single previously shiftclicked line
                line.removeClass('last-selected highlighted clicked multihighlight');
                updateHash('#');
            } else if (lastSelectedNum < clickedNum) {
                //shiftclick descending down the page - .last-selected to .clicked
                line.addClass('clicked');
                selectedLineNums = $('.line-number.last-selected').nextUntil($('.line-number.clicked'));
                selectedLineCode = $('code.last-selected').nextUntil($('code.clicked'));
                $('.last-selected').removeClass('clicked');
                //mark new last-selected
                lastSelectedLine.addClass(classToAdd)
                                .removeClass('last-selected highlighted');
                line.addClass(classToAdd);
                line.addClass('last-selected');
            } else if (lastSelectedNum > clickedNum) {
                //shiftclick ascending up the page - .clicked to .last-selected
                $('.line-number, code').removeClass('clicked');
                line.addClass('clicked');
                selectedLineNums = $('.line-number.clicked').nextUntil($('.line-number.last-selected'));
                selectedLineCode = $('code.clicked').nextUntil($('code.last-selected'));
                //mark new last-selected
                lastSelectedLine.addClass(classToAdd)
                                .removeClass('last-selected highlighted');
                line.addClass(classToAdd);
                line.addClass('last-selected');
            }
            if (selectedLineNums) {
                selectedLineNums.addClass(classToAdd);
                selectedLineCode.addClass(classToAdd);
            }

            //set the last used modifier key
            lastModifierKey = 'shift';

        } else if (event.shiftKey && lastModifierKey === 'singleSelectKey') {
            //if ctrl/command was last pressed, add multihighlight class to new lines
            $('.line-number, .code code').removeClass('clicked');
            line.addClass('clicked');
            selectedLineNums = $('.line-number.last-selected').nextUntil($('.line-number.clicked'));
            selectedLineNums.addClass('multihighlight')
                            .removeClass('highlighted');
            selectedLineCode = $('code.last-selected').nextUntil($('code.clicked'));
            selectedLineCode.addClass('multihighlight')
                            .removeClass('highlighted');
            line.addClass('multihighlight');

        } else if (event.ctrlKey || event.metaKey) {
            //a single click with ctrl/command highlights one line and preserves existing highlights
            lastModifierKey = 'singleSelectKey';
            $('.highlighted').addClass('multihighlight');
            $('.line-number, .code code').removeClass('last-selected clicked highlighted');
            if (lastSelectedNum !== clickedNum) {
                line.toggleClass('clicked last-selected multihighlight');
            } else {
                line.toggleClass('multihighlight');
                updateHash('#');
            }

        } else {
            removeAllHighlighting();
            //toggle highlighting on for any line that was not previously clicked
            if (lastSelectedNum !== clickedNum) {
                //With this we're one better than github, which doesn't allow toggling single lines
                line.toggleClass('last-selected highlighted');
            } else {
                updateHash('#');
            }
        }
        setWindowHash();
    });

    function removeAllHighlighting() {
        lastModifierKey = null;
        rangesArray = [];
        singleLinesArray = [];
        $('.line-number, .code code').removeClass('last-selected highlighted multihighlight clicked');
    }

    //highlight line(s) if someone visits a url with an #anchor
    function processHash() {
        if (window.location.hash.substring(1)) {
            var toHighlight = getSortedHashLines(),
                jumpPosition = $('#' + toHighlight.lineStart).offset(),
                highlights = toHighlight.highlights,
                ranges = toHighlight.ranges;

            if (highlights !== null) {
                //add single line highlights
                for (var i=0; i < highlights.length; i++) {
                    $('#' + highlights[i] + ', #line-' + highlights[i]).addClass('highlighted');
                }
            }

            if (ranges !== null) {
                //handle multiple sets of multi-line highlights from an incoming url
                for (var j=0; j < ranges.length; j++) {
                    //handle a single set of line ranges here; the c counter must be <= since it is a line id
                    for (var c = ranges[j][0]; c <= ranges[j][1]; c++) {
                        $('#' + c + ', #line-' + c).addClass('highlighted');
                    }
                }
            }

            //for directly linked line(s), scroll to the offset minus 150px for fixed search bar height
            //but only scrollTo if the offset is more than 150px in distance from the top of the page
            jumpPosition = parseInt(jumpPosition.top, 10) - 150;
            if (jumpPosition < 0) {
                jumpPosition = 0;
            }

            // Trying to scroll in the document ready handler doesn't work because some
            // browsers (e.g. Chrome) will reset the scroll position later.
            // Delaying the scroll with setTimeout works around this problem.
            window.setTimeout(function() {
                window.scrollTo(0, jumpPosition);
            }, 0);
            //tidy up an incoming url that might be typed in manually
            setWindowHash();
        }
    }

    // Highlight any lines specified by hash in either a direct page load or a history pop.
    $(document).ready(processHash);
    $(window).on('popstate', function() {
        removeAllHighlighting();
        processHash();
    });
});
