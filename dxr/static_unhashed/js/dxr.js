/* jshint devel:true, esnext: true */
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
        scrollIntoView(window.location.hash.substr(1));
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
     * If the `case` param is in the URL, returns its boolean value. Otherwise,
     * returns null.
     */
    function caseFromUrl() {
        var match = /[?&]?case=([^&]+)/.exec(location.search);
        return match ? (match[1] === 'true') : null;
    }

    /**
     * Represents the path line displayed next to the file path label on individual document pages.
     * Also handles population of the path lines template in the correct format.
     *
     * @param {string} fullPath - The full path of the currently displayed file.
     * @param {string} tree - The tree which was searched and in which this file can be found.
     * @param {string} icon - The icon string returned in the JSON payload.
     */
    function buildResultHead(fullPath, tree, icon, isBinary) {
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

            pathLines += nunjucks.render('path_line.html', {
                'data_path': dataPath.join('/'),
                'display_path': paths[pathIndex],
                'url': pathRoot + dataPath.join('/'),
                'is_first_or_only': isFirstOrOnly,
                'is_dir': !isLastOrOnly,
                'is_binary': isBinary
            });
        }

        return [iconClass, pathLines];
    }

    var searchForm = $('#basic_search'),
        queryField = $('#query'),
        query = null,
        caseSensitiveBox = $('#case'),
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
        defaultDataLimit = 100;

    // Has the user been redirected to a direct result?
    var fromQuery = /[?&]?from=([^&]+)/.exec(location.search);
    if (fromQuery !== null) {
        // Offer the user the option to see all the results instead.
        var viewResultsTxt = 'Showing a direct result. <a href="{{ url }}">Show all results instead.</a>',
            isCaseSensitive = caseFromUrl();

        var searchUrl = constants.data('search') + '?q=' + fromQuery[1];
        if (isCaseSensitive !== null) {
            searchUrl += '&case=' + isCaseSensitive;
        }

        queryField.val(decodeURIComponent(fromQuery[1]));
        showBubble('info', viewResultsTxt.replace('{{ url }}', searchUrl));
    }

    $(window).scroll(function() {
        didScroll = true;
    });

    /**
     * Return the full Ajax URL for search.
     *
     * @param {string} query - The query string
     * @param {bool} isCaseSensitive - Whether the query should be case-sensitive
     * @param {int} limit - The number of results to return.
     * @param {int} offset - The cursor position
     * @param {bool} redirect - Whether to redirect.
     */
    function buildAjaxURL(query, isCaseSensitive, limit, offset, redirect) {
        var search = dxr.searchUrl;
        var params = {};
        params.q = query;
        params.redirect = redirect;
        params['case'] = isCaseSensitive;
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
                var requestUrl = buildAjaxURL(query, caseSensitiveBox.prop('checked'), defaultDataLimit, dataOffset, false);
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
        waiter = setTimeout(doQuery, timeouts.search);
    }

    /**
     * Saves checkbox checked property to localStorage and invokes queryNow function.
     */
    function updateLocalStorageAndQueryNow(){
       localStorage.setItem('caseSensitive', $('#case').prop('checked'));
       queryNow();
    }

    /**
     * Clears any existing query timer and queries immediately.
     */
    function queryNow(redirect) {
        clearTimeout(waiter);
        doQuery(redirect);
    }

    /**
     * Populates the results template.
     * @param {object} data - The data returned from the query
     * @param {bool} append - Should the content be appended or overwrite
     */
    function populateResults(data, append) {
        data.www_root = dxr.wwwRoot;
        data.tree = dxr.tree;
        data.top_of_tree = dxr.wwwRoot + '/' + data.tree + '/source/';

        var params = {
            q: data.query,
            case: data.is_case_sensitive
        };
        data.query_string = $.param(params);

        // If no data is returned, inform the user.
        if (!data.results.length) {
            if (!append) {
                contentContainer
                    .empty()
                    .append(nunjucks.render('results_container.html', data));
            }
        } else {
            var results = data.results;
            resultsLineCount = countLines(results);

            for (var result in results) {
                var icon = results[result].icon;
                var resultHead = buildResultHead(results[result].path, data.tree, icon, results[result].is_binary);
                results[result].iconClass = resultHead[0];
                results[result].pathLine = resultHead[1];
            }

            if (!append) {
                contentContainer
                    .empty()
                    .append(nunjucks.render('results_container.html', data));
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
                    domFirstResult.append(nunjucks.render('result_lines.html', {
                        www_root: dxr.wwwRoot,
                        tree: dxr.tree,
                        result: firstResult
                    }));
                }

                // Don't render if there was only the first result and it was rendered.
                if (data.results.length) {
                    resultsList.append(nunjucks.render('results.html', data));
                }
            }
        }

        if (!append) {
            document.title = data.query + " - DXR Search";
        }
    }

    /**
     * Queries and populates the results templates with the returned data.
     *
     * @param {bool} [redirect] - Whether to redirect if we hit a direct result.
     * @param {string} [queryString] - The url to which to send the request. If left out,
     * queryString will be constructed from the contents of the query field.
     * @param {bool} [appendResults] - Whether to append new results to the current list,
     * otherwise replace.
     */
    function doQuery(redirect, queryString, appendResults) {
        query = $.trim(queryField.val());
        var myRequestNumber = nextRequestNumber,
            lineHeight = parseInt(contentContainer.css('line-height'), 10),
            limit = Math.floor((window.innerHeight / lineHeight) + 25);

        redirect = redirect || false;
        // Turn into a boolean if it was undefined.
        appendResults = !!appendResults;
        queryString = queryString || buildAjaxURL(query, caseSensitiveBox.prop('checked'), limit, 0, redirect);
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
                // Check whether to redirect to a direct hit.
                if (data.redirect) {
                    window.location.href = data.redirect;
                    return;
                }
                data.query = query;
                // New results, display them.
                if (myRequestNumber > displayedRequestNumber) {
                    displayedRequestNumber = myRequestNumber;
                    populateResults(data, appendResults);
                    var pushHistory = function () {
                        // Strip off offset= and limit= when updating.
                        var displayURL = queryString.replace(/[&?]offset=\d+/, '').replace(/[&?]limit=\d+/, '');
                        history.pushState({}, '', displayURL);
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

                // Start the scroll pos poller.
                pollScrollPosition();
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

    // Update the search when the case-sensitive box is toggled, canceling any pending query:
    caseSensitiveBox.on('change', updateLocalStorageAndQueryNow);


    var urlCaseSensitive = caseFromUrl();
    if (urlCaseSensitive !== null) {
        // Any case-sensitivity specification in the URL overrides what was in localStorage:
        localStorage.setItem('caseSensitive', urlCaseSensitive);
    } else {
        // Restore checkbox state from localStorage:
        caseSensitiveBox.prop('checked', 'true' === localStorage.getItem('caseSensitive'));
    }


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

    // Expose the DXR Object to the global object.
    window.dxr = dxr;

    // Thanks to bug 63040 in Chrome, onpopstate is fired when the page reloads.
    // That means that if we naively set onpopstate, we would get into an
    // infinite loop of reloading whenever onpopstate is triggered. Therefore,
    // we have to only add our onpopstate handler once the page has loaded.
    window.onload = function() {
        setTimeout(function() {
            window.onpopstate = popStateHandler;
        }, 0);
    };

    // Reload the page when we go back or forward.
    function popStateHandler(event) {
        // Check for event state first to avoid nasty complete page reloads on #anchors:
         if (event.state != null) {
            window.onpopstate = null;
            window.location.reload();
         }
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
        if (/search$/.test(window.location.pathname) && window.location.search) {
            // Set case-sensitive checkbox according to the URL, and make sure
            // the localstorage mirrors it.
            var urlIsCaseSensitive = caseFromUrl() === true;
            caseSensitiveBox.prop('checked', urlIsCaseSensitive);
            localStorage.setItem('caseSensitive', urlIsCaseSensitive);
            doQuery(false, window.location.href);
        }
    });
});
