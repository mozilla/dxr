/* jshint devel:true */
/* globals nunjucks: true, $ */

var htmlEscape;
$(function() {
    'use strict';

    var constants = $('#data');
    var dxr = {},
        docElem = document.documentElement;

    dxr.wwwRoot = constants.data('root');
    dxr.baseUrl = location.protocol + '//' + location.host;
    dxr.searchUrl = constants.data('search');
    dxr.linesUrl = constants.data('lines');
    dxr.tree = constants.data('tree');

    var timeouts = {};
    timeouts.scroll = 500;
    timeouts.search = 300;
    // We start the history timeout after the search updates (i.e., after
    // timeouts.search has elapsed).
    timeouts.history = 2000 - timeouts.search;

    // Tell nunjucks our base location for template files.
    var nunjucksEnv = nunjucks.configure('dxr/templates',
                                         {autoescape: true});
    htmlEscape = nunjucksEnv.getFilter('escape');

    // Return the maximum number of pixels the document can be scrolled.
    function getMaxScrollY() {
        // window.scrollMaxY is a non standard implementation in
        // Gecko(Firefox) based browsers. If this is thus available,
        // simply return it, else return the calculated value above.
        // @see https://developer.mozilla.org/en-US/docs/Web/API/Window.scrollMaxY
        return window.scrollMaxY || (docElem.scrollHeight - window.innerHeight);
    }

    /**
     * Because we have a fixed header and often link to anchors inside pages, we can
     * run into the situation where the highled anchor is hidden behind the header.
     * This ensures that the highlighted anchor will always be in view.
     * @param {string} id = The id of the highlighted table row
     */
    function scrollIntoView(id) {
        var lineElement = document.getElementById(id);

        if (lineElement === null)  // There is no line #1. Empty file.
            return;

        if ((getMaxScrollY() - lineElement.offsetTop) > 100) {
            window.scroll(0, window.scrollY - 150);
        }
    }

    // Check if the currently loaded page has a hash in the URL
    if (window.location.hash) {
        scrollIntoView(window.location.hash.substr(1));
    }

    // We also need to cater for the above scenario when a user clicks on in page links.
    window.onhashchange = function() {
        if (window.location.hash) {
            scrollIntoView(window.location.hash.substr(1));
        }
    };

    /**
     * Hang an advisory message off the search field.
     * @param {string} level - The seriousness: 'info', 'warning', or 'error'
     * @param {string} html - The HTML message to be displayed
     */
    function showBubble(level, html) {
        // If hideBubble() was already called, abort the hide animation:
        $('.bubble').stop();

        $('.bubble').html(html)
                    .removeClass('error warning info')
                    .addClass(level)
                    .show();
    }

    function hideBubble() {
        $('.bubble').fadeOut(300);
    }

    /**
     * Represents the path line displayed next to the file path label on individual document pages.
     * Also handles population of the path lines template in the correct format.
     *
     * @param {string} fullPath - The full path of the currently displayed file.
     * @param {string} tree - The tree which was searched and in which this file can be found.
     * @param {string} icon - The icon string returned in the JSON payload.
     */
    function buildResultHead(fullPath, tree, icon) {
        var pathLines = '',
            pathRoot = '/' + tree + '/source/',
            paths = fullPath.split('/'),
            splitPathLength = paths.length,
            dataPath = [],
            iconClass = icon.substring(icon.indexOf('/') + 1);

        for (var pathIndex in paths) {
            var index = parseInt(pathIndex),
                isFirstOrOnly = index === 0 || splitPathLength === 1,
                isLastOrOnly = (splitPathLength - 1) === index || splitPathLength === 1;

            dataPath.push(paths[pathIndex]);

            // Render the path segment and trim white space so copying the
            // path will not insert spaces.
            pathLines += nunjucks.render('path_line.html', {
                'data_path': dataPath.join('/'),
                'display_path': paths[pathIndex],
                'url': pathRoot + dataPath.join('/'),
                'is_first_or_only': isFirstOrOnly,
                'is_dir': !isLastOrOnly
            }).trim();
        }

        return [iconClass, pathLines];
    }

    var searchForm = $('#basic_search'),
        queryField = $('#query'),
        query = null,
        contentContainer = $('#content'),
        waiter = null,
        historyWaiter = null,
        nextRequestNumber = 1, // A monotonically increasing int that keeps old AJAX requests in flight from overwriting the results of newer ones, in case more than one is in flight simultaneously and they arrive out of order.
        requestsInFlight = 0,  // Number of search requests in flight, so we know whether to hide the activity indicator
        displayedRequestNumber = 0,
        didScroll = false,
        resultsLineCount = 0,
        dataOffset = 0,
        previousDataLimit = 0,
        defaultDataLimit = 100,
        lastURLWasSearch = false;  // Remember if the previous history URL was for a search (for popState).

    $(window).scroll(function() {
        didScroll = true;
    });

    /**
     * Return the full Ajax URL for search.
     *
     * @param {string} query - The query string
     * @param {int} limit - The number of results to return.
     * @param {int} offset - The cursor position
     * @param {bool} redirect - Whether to redirect.
     */
    function buildAjaxURL(query, limit, offset, redirect) {
        var search = dxr.searchUrl;
        var params = {};
        params.q = query;
        params.redirect = redirect;
        params.limit = limit;
        params.offset = offset;

        return search + '?' + $.param(params);
    }

    var scrollPoll = null;

    /**
     * Starts or restarts the scroll position poller.
     */
    function pollScrollPosition() {
        clearInterval(scrollPoll);
        scrollPoll = setInterval(infiniteScroll, 250);
    }

    function infiniteScroll() {
        if (didScroll) {

            didScroll = false;

            var maxScrollY = getMaxScrollY(),
                currentScrollPos = window.scrollY,
                threshold = window.innerHeight + 500;

            // Has the user reached the scrolling threshold and are there more results?
            // If the returned number of results is greater or equal to the previous limit
            // requested, then we ask the server for more.
            if ((maxScrollY - currentScrollPos) < threshold && previousDataLimit <= resultsLineCount) {
                clearInterval(scrollPoll);

                // If a user hits enter on the landing page and there was no direct result,
                // we get redirected to the search page and lose the query so, if query is null,
                // get the query from the input field.
                query = query ? query : $.trim(queryField.val());

                dataOffset += previousDataLimit;
                previousDataLimit = defaultDataLimit;

                // Resubmit query for the next set of results, making sure redirect is turned off.
                var requestUrl = buildAjaxURL(query, defaultDataLimit, dataOffset, false);
                doQuery(false, requestUrl, true);
            }
        }
    }

    /**
     * Given a list of results from the search endpoint, return the total number of results.
     * If the results are line-based, then count the number of lines returned.
     * Otherwise, count the number of results.
     */
    function countLines(results) {
        var total = 0;
        for (var k = 0; k < results.length; k++) {
            // If this is a FILE result, then it does not have lines attached,
            // but we still want to count it as a result.
            total += Math.max(results[k].lines.length, 1);
        }
        return total;
    }

    /**
     * Clears any existing query timer and sets a new one to query in a moment.
     */
    function querySoon() {
        clearTimeout(waiter);
        clearTimeout(historyWaiter);
        function doQueryPushHistory() {
            doQuery(false, '', false, true);
        }
        waiter = setTimeout(doQueryPushHistory, timeouts.search);
    }

    /**
     * Clears any existing query timer and queries immediately.
     */
    function queryNow(redirect) {
        clearTimeout(waiter);
        doQuery(redirect, '', false, true);
    }

    /**
     * Add click listeners to the context buttons to load more contexts.
     */
    function withContextListeners(renderedResults) {
        var toJquery = $(renderedResults);

        // AJAX query as context lines after given row if after is true,
        // otherwise before given row.
        function getContextLines(row, query, after) {
            $.ajax({
                dataType: "json",
                url: query,
                success: function(data) {
                    var result;
                    if (data.lines.length > 0) {
                        result = nunjucks.render('context_lines.html', {
                            www_root: dxr.wwwRoot,
                            tree: dxr.tree,
                            result: data
                        });
                        if (after) {
                            row.after(withContextListeners(result));
                        } else {
                            row.before(withContextListeners(result));
                        }
                        // Call cleanup after adding to remove unnecessary
                        // buttons and duplicated result rows.
                        cleanupResults(row.parent());
                    }
                }
            });
        }

        // Before attaching the listeners call cleanup, since that may change
        // or remove buttons.
        toJquery.find(".result").each(function() {
            cleanupResults($(this));
        });
        // Attach event listeners to each of the context spans, given by
        // {klass, start offset, end offset}
        [{klass: ".ctx_full", start: -3, end: 3, after: true},
         {klass: ".ctx_up", start: -4, end: -1, after: false},
         {klass: ".ctx_down", start: 1, end: 4, after: true}].forEach(
                function(ctx) {
                    var c = ctx;
                    $(c.klass, toJquery).on('click', function() {
                        var $this = $(this),
                            path = $this.parents('.result').data('path'),
                            line = parseInt($this.parents(".result_line").data('line')),
                            queryString = (dxr.linesUrl + '?' +
                                           $.param({path: path,
                                                    start: line + c.start,
                                                    end: line + c.end}));
                        getContextLines($this.parents(".result_line"), queryString, c.after);
                    });
                });
        return toJquery;
    }

    /**
     * Visit the result lines in result and remove duplicated lines and redundant context buttons.
     */
    function cleanupResults(result) {
        // Construct {line: {contextEl, resultEl}}
        var lineMap = {};
        var spaces, text, resultCode, lineNode, ctxSpan;
        // Visit the lines and remove duplicates.
        result.children('.result_line').each(function() {
            var $this = $(this);
            var line = parseInt($this.data("line"));
            lineMap[line] = lineMap[line] || {};
            if (this.classList.contains("ctx_row")) {
                if (lineMap[line].contextEl) {
                    // Then this is duplicate, remove it.
                    $this.remove();
                } else {
                    lineMap[line].contextEl = this;
                }
            } else {
                if (lineMap[line].resultEl) {
                    // Then this is duplicate, remove it.
                    $this.remove();
                } else {
                    lineMap[line].resultEl = this;
                }
            }
        });
        // Now go through and fix some things.
        for (var line in lineMap) {
            if (!lineMap.hasOwnProperty(line)) continue;
            // If some line has both context and result, then replace context line by result line.
            // But since result strips trailing whitespace where context has it,
            // we must bring that from the context line.
            if (lineMap[line].contextEl && lineMap[line].resultEl) {
                text = lineMap[line].contextEl.querySelector("code").textContent;
                resultCode = lineMap[line].resultEl.querySelector("code");
                spaces = "";
                for (var i = 0; i < text.length && /\s/.test(text[i]); i++) {
                    spaces += text[i];
                }
                resultCode.innerHTML = spaces + resultCode.innerHTML;
                $(lineMap[line].contextEl).replaceWith(lineMap[line].resultEl);
            }
            lineNode = lineMap[line].resultEl || lineMap[line].contextEl;
            ctxSpan = lineNode.querySelector(".leftmost-column > span");
            line = parseInt(line);
            // If previous line exists, remove ctx_up. If below line exists, remove ctx_down.
            // If surrounded, remove ctx_full.
            if (ctxSpan && ((lineMap[line - 1] && ctxSpan.classList.contains("ctx_up")) ||
                        (lineMap[line + 1] && ctxSpan.classList.contains("ctx_down")) ||
                        (lineMap[line + 1] && lineMap[line - 1] &&
                         ctxSpan.classList.contains("ctx_full")))) {
                $(ctxSpan).remove();
            }
            // But if it's a ctx_full and either top or bottom exists, convert it to an arrow.
            if (ctxSpan && ctxSpan.classList.contains("ctx_full")) {
                if (lineMap[line + 1]) {
                    ctxSpan.classList.add("ctx_up");
                    ctxSpan.classList.remove("ctx_full");
                    ctxSpan.textContent = "△";
                } else if (lineMap[line - 1]) {
                    ctxSpan.classList.add("ctx_down");
                    ctxSpan.classList.remove("ctx_full");
                    ctxSpan.textContent = "▽";
                }
            }
        }
    }


    /**
     * Populates the results template.
     * @param {object} data - The data returned from the query
     * @param {bool} append - Should the content be appended or overwrite
     */
    function populateResults(data, append) {
        var renderedData;
        var params = {
            q: data.query
        };

        data.www_root = dxr.wwwRoot;
        data.tree = dxr.tree;
        data.top_of_tree = dxr.wwwRoot + '/' + data.tree + '/source/';
        data.query_string = $.param(params);

        // If no data is returned, inform the user.
        if (!data.results.length) {
            resultsLineCount = 0;
            if (!append) {
                renderResultsNav(data);
                contentContainer
                    .empty()
                    .append(nunjucks.render('results_container.html', data));
            }
        } else {
            var results = data.results;
            resultsLineCount = countLines(results);

            for (var result in results) {
                var icon = results[result].icon;
                var resultHead = buildResultHead(results[result].path, data.tree, icon);
                results[result].iconClass = resultHead[0];
                results[result].pathLine = resultHead[1];
            }

            if (!append) {
                renderedData = nunjucks.render('results_container.html', data);
                contentContainer.empty().append(withContextListeners(renderedData));
                renderResultsNav(data);
            } else {
                var resultsList = contentContainer.find('.results');

                // If the first result is already on the page (meaning we showed
                // some of its lines but just fetched more), add new lines to
                // it instead of adding a new result section.
                var firstResult = data.results[0];
                var domFirstResult = resultsList.find(
                    '.result[data-path="' + firstResult.path + '"]');
                if (domFirstResult.length) {
                    data.results = data.results.splice(1);
                    var renderedLines = nunjucks.render('result_lines.html', {
                        www_root: dxr.wwwRoot,
                        tree: dxr.tree,
                        result: firstResult
                    });
                    domFirstResult.append(withContextListeners(renderedLines));
                }

                // Don't render if there was only the first result and it was rendered.
                if (data.results.length) {
                    renderedData = nunjucks.render('results.html', data);
                    resultsList.append(withContextListeners(renderedData));
                    renderResultsNav(data);
                }
            }
        }

        if (!append) {
            document.title = data.query + " - DXR Search";
        }
    }

    /**
     * Renders/updates the nav bar for a set of search results
     */
    function renderResultsNav(data) {
        var renderedNav = nunjucks.render('results_nav.html', data);
        $('.current-tree-nav').empty().append(renderedNav);
    }

    /**
     * Queries and populates the results templates with the returned data.
     *
     * @param {bool} [redirect] - Whether to redirect if we hit a direct or unique result.  Default is false.
     * @param {string} [queryString] - The url to which to send the request. If left out,
     * queryString will be constructed from the contents of the query field.
     * @param {bool} [appendResults] - Append new results to the current list if true,
     * otherwise replace.  Default is false.
     * @param {bool} [addToHistory] - Whether to add this query to the browser history.  Default is false.
     */
    function doQuery(redirect, queryString, appendResults, addToHistory) {
        query = $.trim(queryField.val());
        var myRequestNumber = nextRequestNumber, limit, match, lineHeight;

        // Turn into a boolean if it was undefined.
        redirect = !!redirect;
        appendResults = !!appendResults;
        addToHistory = !!addToHistory;
        if (queryString) {
            // Normally there will be no explicit limit set in this case, but
            // there's nothing stopping a user from setting it by hand in the
            // url, so I guess we should check:
            match = /[?&]limit=([0-9]+)/.exec(queryString);
            limit = match ? match[1] : defaultDataLimit;
        } else {
            lineHeight = parseInt(contentContainer.css('line-height'), 10);
            limit = Math.floor((window.innerHeight / lineHeight) + 25);
            queryString = buildAjaxURL(query, limit, 0, redirect);
        }
        function oneMoreRequest() {
            if (requestsInFlight === 0) {
                $('#search-box').addClass('in-progress');
            }
            requestsInFlight += 1;
        }

        function oneFewerRequest() {
            requestsInFlight -= 1;
            if (requestsInFlight === 0) {
                $('#search-box').removeClass('in-progress');
            }
        }

        if (!appendResults)
            clearTimeout(historyWaiter);

        if (query.length === 0) {
            hideBubble();  // Don't complain when I delete what I typed. You didn't complain when it was empty before I typed anything.
            return;
        } else if (query.length < 3) {
            showBubble('info', 'Enter at least 3 characters to do a search.');
            return;
        }

        hideBubble();
        nextRequestNumber += 1;
        oneMoreRequest();
        $.ajax({
            dataType: "json",
            url: queryString,
            // We need to disable caching of this result because otherwise we break the undo close
            // tab feature on search pages (Chrome and Firefox).
            cache: appendResults,
            success: function (data) {
                // Check whether to redirect to a direct or single hit.
                if (data.redirect) {
                    window.location.href = data.redirect;
                    lastURLWasSearch = false;
                    return;
                }
                data.query = query;
                // New results, display them.
                if (myRequestNumber > displayedRequestNumber) {
                    displayedRequestNumber = myRequestNumber;
                    populateResults(data, appendResults);
                    if (addToHistory) {
                        var pushHistory = function () {
                            // Strip off offset= and limit= when updating.
                            var displayURL = removeParams(queryString, ['offset', 'limit']);
                            history.pushState({}, '', displayURL);
                            lastURLWasSearch = true;
                        };
                        if (redirect)
                            // Then the enter key was pressed and we want to update history state now.
                            pushHistory();
                        else if (!appendResults)
                            // Update the history state if we're not appending: this is a new search.
                            historyWaiter = setTimeout(pushHistory, timeouts.history);
                    }
                    if (!appendResults) {
                        previousDataLimit = limit;
                        dataOffset = 0;
                    }
                    // If there were no results this time then we shouldn't turn
                    // infinite scroll (back) on (otherwise if the number of
                    // results exactly equals the limit we can end up sending a
                    // query returning 0 results everytime we scroll).
                    if (resultsLineCount)
                        pollScrollPosition();
                }

                oneFewerRequest();
            }
        })
        .fail(function(jqxhr) {
            oneFewerRequest();

            // A newer response already arrived and is displayed. Don't bother complaining about this old one.
            if (myRequestNumber < displayedRequestNumber)
                return;

            if (jqxhr.responseJSON)
                showBubble(jqxhr.responseJSON.error_level, jqxhr.responseJSON.error_html);
            else
                showBubble('error', 'An error occurred. Please try again.');
        });
    }

    // Do a search every time you pause typing for 300ms:
    queryField.on('input', querySoon);

    // Intercept the form submission and perform an AJAX query instead.
    searchForm.on('submit', function(event) {
        event.preventDefault();
        queryNow(true);
    });

    // Toggle the help box when the help icon is clicked, and hide it when
    // anything outside of the box is clicked.

    $(document.documentElement)
        .on('click', '.help-icon', function(e) {
            if ($(e.target).is(':not(.help-icon *)')) {
                var helpIcon = $('.help-icon'),
                    helpMsg = helpIcon.find('.help-msg');

                helpIcon.toggleClass('open');
                helpMsg.toggle();
            }
        })
        .on('mousedown', function(e) {
            if ($(e.target).is(':not(.help-icon, .help-icon *)')) {
                hideHelp();
            }
        });


    /**
     * Adds a leading 0 to numbers less than 10 and greater than 0
     *
     * @param {int} number The number to test against
     *
     * return Either the original number or the number prefixed with 0
     */
    function addLeadingZero(number) {
        return (number <= 9) || (number === 0) ? "0" + number : number;
    }

    /**
     * Converts string to new Date and returns a formatted date in the
     * format YYYY-MM-DD h:m
     * @param {string} dateString A date in string form.
     *
     */
    function formatDate(dateString) {
        var fullDateTime = new Date(dateString),
            date = fullDateTime.getFullYear() + '-' + (fullDateTime.getMonth() + 1) + '-' + addLeadingZero(fullDateTime.getDate()),
            time = fullDateTime.getHours() + ':' + addLeadingZero(fullDateTime.getMinutes());

        return date + ' ' + time;
    }

    var prettyDate = $('.pretty-date');
    prettyDate.each(function() {
        $(this).text(formatDate($(this).data('datetime')));
    });

    function locationIsSearch() {
        return /search$/.test(window.location.pathname) && window.location.search !== '';
    }

    // Expose the DXR Object to the global object.
    window.dxr = dxr;

    // Thanks to bug 63040 in Chrome, onpopstate is fired when the page reloads.
    // That means that if we naively set onpopstate, we would get into an
    // infinite loop of reloading whenever onpopstate is triggered. Therefore,
    // we have to only add our onpopstate handler once the page has loaded.
    window.addEventListener('load', function() {
        setTimeout(function() {
            window.addEventListener('popstate', popStateHandler);
        }, 0);
    });

    // Reload the page when we go back or forward.
    function popStateHandler(event) {
        if (locationIsSearch() ||  // If new location is a search, or...
            lastURLWasSearch) {  // if we switched from search to file view:
            window.onpopstate = null;
            window.location.reload();
        }
        lastURLWasSearch = locationIsSearch();
    }

    /**
     * Replace 'source' with 'raw' in href, and set that to the background-image
     */
    function setBackgroundImageFromLink(anchorElement) {
        var href = anchorElement.getAttribute('href');
        // note: breaks if the tree's name is "source"
        var bg_src = href.replace('source', 'raw');
        anchorElement.style.backgroundImage = 'url(' + bg_src + ')';
    }
    window.addEventListener('load', function() {
        $(".image").not('.too_fat').each(function() {
            setBackgroundImageFromLink(this);
        });
    });

    // If on load of the search endpoint we have a query string then we need to
    // load the results of the query and activate infinite scroll.
    window.addEventListener('load', function() {
        var savedURL, noRedirectURL;
        lastURLWasSearch = locationIsSearch();
        if (lastURLWasSearch) {
            savedURL = window.location.href;
            if (/[&?]redirect=true/.test(window.location.href)) {
                noRedirectURL = removeParams(window.location.href, ['redirect']);
                history.replaceState({}, '', noRedirectURL);
            }
            doQuery(false, savedURL);
        }
    });
});
