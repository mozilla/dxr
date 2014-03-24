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
    var container = $('#line-numbers'),
        lastModifierKey = null, // use this as a sort of canary/state indicator showing the last user action
        singleLinesArray = [], //track single highlighted lines here
        rangesArray = []; // track ranges of highlighted lines here 

    //populate the single click array with lines if they are not already in it
    function populateSingleLinesArray(clickedNum, self) {
        var inArray = singleLinesArray.indexOf(clickedNum);
        console.log('Classes: ' + self.classList);

        if (inArray === -1 && (self.classList.contains('highlighted') || self.classList.contains('multihighlight'))) {
            //add the line to the array
            singleLinesArray.push(clickedNum);
        } else if (inArray === -1 && !(self.classList.contains('highlighted') || self.classList.contains('multihighlight'))) {
            if (rangesArray.length) {
                //check if the line splits up an existing range
                splitRangesArray(clickedNum);
            }
        } else if (inArray !== -1) {
            //this is a toggle, since the line is in the array, so remove it
            singleLinesArray.splice(inArray, 1);
        }        
        singleLinesArray = singleLinesArray.sort(sortAsc);
        console.log('Single lines: ' + singleLinesArray);
    }

    //split up a range if a single line exists in it at any point inside a range
    function splitRangesArray(clickedNum) {
        var rangeMin = null,
            rangeMax = null,
            inArray = singleLinesArray.indexOf(clickedNum);

        //don't want the clickedNum in singleLinesArray since it is being deselected
        //singleLinesArray.splice(inArray, 1);

        for (var s = 0; s < rangesArray.length; s++) {
            //get each pair of values from rangesArray
            rangeMin = rangesArray[s][0];
            rangeMax = rangesArray[s][1];

            //should this be a switch/case?
            //split something like 20-21 at 20 into 21
            if (clickedNum === rangeMin && clickedNum === rangeMax-1) {
                rangesArray.splice(s, 1);
                singleLinesArray.push(rangeMax);
                break;

            //split something like 20-21 at 21 into 20
            } else if (clickedNum === rangeMin+1 && clickedNum === rangeMax) {
                rangesArray.splice(s, 1);
                singleLinesArray.push(rangeMin);
                break;

            //split something like 20-22 at 20 into 21-22
            } else if (clickedNum === rangeMin && clickedNum < rangeMax) {
                rangesArray[s][0]++; // = clickedNum+1;
                break;

            //split something like 20-22 at 22 into 20-21
            } else if (clickedNum > rangeMin && clickedNum === rangeMax) {
                rangesArray[s][1] --; //clickedNum-1;
                break;

            //split something like 20-22 at 21 into 20, 22 single lines
            } else if (clickedNum === rangeMin+1 && clickedNum === rangeMax-1) {
                rangesArray.splice(s, 1);
                singleLinesArray.push(rangeMin);
                singleLinesArray.push(rangeMax);
                break;

            //split something like 20-23 at 21 into 20, 22-23
            } else if (clickedNum === rangeMin+1 && clickedNum < rangeMax) {
                rangesArray.splice(s, 1);
                singleLinesArray.push(rangeMin);
                rangesArray.push([clickedNum+1, rangeMax]);
                break;

            //split something like 20-23 at 22 into 20-21, 23
            } else if (clickedNum > rangeMin && clickedNum === rangeMax-1) {
                rangesArray.splice(s, 1);
                singleLinesArray.push(rangeMax);
                rangesArray.push([rangeMin, clickedNum-1]);
                break;

            //split something like 20-30 at 25 into 20-24, 26-30
            //ensure that there are at least 2 lines on either side of clickedNum
            } else if (clickedNum > rangeMin+1 && clickedNum < rangeMax-1) {
                //if comparison, splice rangeArray
                rangesArray.splice(s, 1);
                //push two new arrays of ranges on each side of clickedNum
                rangesArray.push([rangeMin, clickedNum-1]);
                rangesArray.push([clickedNum+1, rangeMax]);
                break;
            }

        }
        //then remove singleLinesArray[s] since it is deselected?
    }

    //populate rangesArray with sets of highlighted lines
    function populateRangesArray(clickedNum, lastSelectedNum) {
        /* 1.  populate ranges
         * 2.  for each range in ranges:
         * 2a.   for each line in single line, check if in range
         * 2b.   if line in range:           
         * 3.      remove detected single lines from single lines array
         */

        var linesToRemove = [],
            range = [];

        //detect order of range and push to the rangesArray
        if (clickedNum < lastSelectedNum) {
            range = [clickedNum, lastSelectedNum];
        } else if (clickedNum > lastSelectedNum){
            range = [lastSelectedNum, clickedNum];
        }
        rangesArray.push(range);

        //iterate over array of ranges to remove single lines if they
        //are captured by any existing highlighted range
        //this is important because it tidies the url and is less confusing
        //e.g the same number does not show up twice: foo#1,4,4-8 cf. foo#1,4-8
        for (var i = 0; i < rangesArray.length; i++) {
            var rangeMin = rangesArray[i][0],
                rangeMax = rangesArray[i][1];

            //make a list of single lines to remove from singleLinesArray
            //if they are part of a range of selected lines
            for (var j = 0; j < singleLinesArray.length; j++) {
                if (singleLinesArray[j] >= rangeMin && singleLinesArray[j] <= rangeMax) {
                    linesToRemove.push(j);
                }
            }
            //remove the corresponding single line from the linesToRemove list
            //using the pop value as the splice position in singleLinesArray
            linesToRemove = linesToRemove.sort(sortAsc);
            while (linesToRemove.length > 0) {
                singleLinesArray.splice(linesToRemove.pop(), 1);
            }
        }
    }

    //sort a one dimensional array in Ascending order
    function sortAsc(a, b) {
        return a - b;
    }

    //sort a one dimensional array in Descending order
    function sortDesc(a, b) {
        return b - a;
    }

    //generate the window.location.hash based on singleLinesArray and rangesArray
    function setWindowHash() {
        var singles = null,
            ranges = [],
            windowHash = null,
            reCleanup = /(^#?,|,$)/;

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
        windowHash = windowHash.replace(reCleanup, '');
        history.replaceState(null, '', windowHash);
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
        //set the hash to a tidied version
        setWindowHash();
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
        if (event.shiftKey && lastModifierKey !== 'shift') {
            var classToAdd = null,
                classesToRemove = null;
            if (lastModifierKey === 'shift' || lastModifierKey === null) {
                classToAdd = 'highlighted';
            } else if (lastModifierKey === 'singleSelectKey') {
                classToAdd = 'multihighlight';
            }
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
                // on last element add last-selected class
                if (lastModifierKey === 'shift') {
                    $('.line-number').removeClass('highlighted multihighlight');
                }
            } else if (lastSelectedNum > clickedNum) {
                //shiftclick ascending up the page
                if (lastModifierKey === 'singleSelectKey') {
                    //remove clicked so that the selector doesn't get confused later in this else if stanza
                    classesToRemove = 'clicked';
                } else if (lastModifierKey === 'shift') {
                    classesToRemove = 'multihighlight highlighted clicked';
                }
                $('.line-number').removeClass(classesToRemove);
                line.addClass('clicked');
                selected = $('.clicked').nextUntil($('.last-selected'));
            }
            selected.each(function () {
                selected.addClass(classToAdd);
            });
            //set the last used modifier key
            lastModifierKey = 'shift';
            // since all highlighed items are stripped, add one back
            lastSelected.addClass(classToAdd);
            line.addClass(classToAdd);
            populateRangesArray(clickedNum, lastSelectedNum);

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
            //for every click, add the line to the singleLinesArray
            populateSingleLinesArray(clickedNum, self);

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
                //put a single line back into the array of single lines
                populateSingleLinesArray(clickedNum, self);
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
        }
    });

});
