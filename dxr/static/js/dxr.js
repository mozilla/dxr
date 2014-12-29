/* jshint devel:true, esnext: true */
/* globals nunjucks: true, $ */

var htmlEscape;

$(function() {
    'use strict';

    var constants = $('#data');
    var stateConstants = $('#state');
    var dxr = {},
        docElem = document.documentElement;

    dxr.wwwroot = constants.data('root');
    dxr.baseUrl = location.protocol + '//' + location.host;
    dxr.icons = dxr.wwwroot + '/static/icons/';
    dxr.views = dxr.wwwroot + '/static/templates';
    dxr.searchUrl = constants.data('search');
    dxr.tree = constants.data('tree');

    var timeouts = {};
    timeouts.scroll = 500;
    timeouts.search = 300;
    // We start the history timeout after the search updates (i.e., after
    // timeouts.search has elapsed).
    timeouts.history = 2000 - timeouts.search;

    // Tell nunjucks our base location for template files.
    var nunjucksEnv = nunjucks.configure('dxr/static/templates/',
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

            pathLines += nunjucks.render('path_line.html', {
                'data_path': dataPath.join('/'),
                'display_path': paths[pathIndex],
                'url': pathRoot + dataPath.join('/'),
                'is_first_or_only': isFirstOrOnly,
                'is_dir': !isLastOrOnly
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
        resultCount = 0,
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

        $('#query').val(decodeURIComponent(fromQuery[1]));
        showBubble('info', viewResultsTxt.replace('{{ url }}', searchUrl));
    }

    $(window).scroll(function() {
        didScroll = true;
    });

    /**
     * Returns the full Ajax URL for search and explicitly sets
     * redirect to false and format to json to ensure we never
     * get a HTML response or redirect from an Ajax call, even
     * when using the back button.
     *
     * @param {string} query - The query string
     * @param {bool} isCaseSensitive - Whether the query should be case-sensitive
     * @param {int} limit - The number of results to return.
     * @param [int] offset - The cursor position
     */
    function buildAjaxURL(query, isCaseSensitive, limit, offset) {
        var search = dxr.searchUrl;
        var params = {};
        params.q = query;
        params.redirect = false;
        params.format = 'json';
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
        scrollPoll = setInterval(infiniteScroll, 250);
    }

    // On document ready start the scroll pos poller.
    pollScrollPosition();

    /**
     * Updates the window's history entry to not break the back button with
     * infinite scroll.
     * @param {int} offset - The offset to store in the URL
     */
    function setHistoryState(offset) {
        var state = {},
            re = /offset=\d+/,
            locationSearch = '';

        if (location.search.indexOf('offset') > -1) {
            locationSearch = location.search.replace(re, 'offset=' + offset);
        } else {
            locationSearch = location.search ? location.search + '&offset=' + offset : '?offset=' + offset;
        }

        var url = dxr.baseUrl + location.pathname + locationSearch + location.hash;

        history.replaceState(state, '', url);
    }

    /**
     * Add an entry into the history stack whenever we do a new search.
     */
    function pushHistoryState(data) {
        var searchUrl = constants.data('search') + '?' + data.query_string;
        history.pushState({}, '', searchUrl);
    }

    function infiniteScroll() {
        if (didScroll) {

            didScroll = false;

            // If the previousDataLimit is 0 we are on the search.html page and doQuery
            // has not yet been called, get the previousDataLimit and resultCount from
            // the page constants.
            if (previousDataLimit === 0) {
                previousDataLimit = stateConstants.data('limit');
                resultCount = stateConstants.data('result-count');
            }

            var maxScrollY = getMaxScrollY(),
                currentScrollPos = window.scrollY,
                threshold = window.innerHeight + 500;

            // Has the user reached the scrolling threshold and are there more results?
            if ((maxScrollY - currentScrollPos) < threshold && previousDataLimit === resultCount) {
                clearInterval(scrollPoll);

                // If a user hits enter on the landing page and there was no direct result,
                // we get redirected to the search page and lose the query so, if query is null,
                // get the query from the input field.
                query = query ? query : $.trim(queryField.val());

                dataOffset += previousDataLimit;
                previousDataLimit = defaultDataLimit;

                //Resubmit query for the next set of results.
                $.getJSON(buildAjaxURL(query, caseSensitiveBox.prop('checked'), defaultDataLimit, dataOffset), function(data) {
                    if (data.results.length > 0) {
                        var state = {};

                        // Update result count
                        resultCount = data.results.length;
                        // Use the results.html partial so we do not inject the entire container again.
                        populateResults('partial/results.html', data, true);
                        // update URL with new offset
                        setHistoryState(dataOffset);
                        // start the scrolling poller
                        pollScrollPosition();
                    }
                })
                .fail(function() {
                    // Should we fail silently here or notify the user?
                    console.log('query failed');
                });
            }
        }
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
    function queryNow() {
        clearTimeout(waiter);
        doQuery();
    }

    /**
     * Populates the results template.
     * @param {object} tmpl - The template to use to render results.
     * @param {object} data - The data returned from the query
     * @param {bool} append - Should the content be appended or overwrite
     */
    function populateResults(tmpl, data, append) {
        data.wwwroot = dxr.wwwroot;
        data.tree = dxr.tree;
        data.top_of_tree = dxr.wwwroot + '/' + data.tree + '/source/';
        data.trees = data.trees;

        var params = {
            q: data.query,
            case: data.is_case_sensitive
        };
        data.query_string = $.param(params);

        // If no data is returned, inform the user.
        if (!data.results.length) {
            data.user_message = contentContainer.data('no-results');
            contentContainer.empty().append(nunjucks.render(tmpl, data));
        } else {

            var results = data.results;
            resultCount = results.length;

            for (var result in results) {
                var icon = results[result].icon;
                var resultHead = buildResultHead(results[result].path, data.tree, icon);
                results[result].iconClass = resultHead[0];
                results[result].pathLine = resultHead[1];
            }

            var container = append ? contentContainer : contentContainer.empty();
            container.append(nunjucks.render(tmpl, data));
        }

        if (!append) {
            document.title = data.query + "- DXR Search";
        }
    }

    /**
     * Queries and populates the results templates with the returned data.
     */
    function doQuery() {

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

        query = $.trim(queryField.val());
        var myRequestNumber = nextRequestNumber,
            lineHeight = parseInt(contentContainer.css('line-height'), 10),
            limit = previousDataLimit = parseInt((window.innerHeight / lineHeight) + 25);

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
        $.getJSON(buildAjaxURL(query, caseSensitiveBox.prop('checked'), limit), function(data) {
            // New results, overwrite
            if (myRequestNumber > displayedRequestNumber) {
                displayedRequestNumber = myRequestNumber;
                populateResults('results_container.html', data, false);
                historyWaiter = setTimeout(pushHistoryState, timeouts.history, data);
            }
            oneFewerRequest();
        })
        .fail(function(jqxhr, textStatus, error) {
            var errorMessage = 'An error occurred. Please try again.';

            oneFewerRequest();

            // A newer response already arrived and is displayed. Don't both complaining about this old one.
            if (myRequestNumber < displayedRequestNumber)
                return;

            if (error)
                errorMessage += '(' + error + ')';
            showBubble('error', errorMessage);
        });
    }

    // Do a search every time you pause typing for 300ms:
    queryField.on('input', querySoon);

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
    var helpIcon = $('.help-icon'),
        helpMsg = helpIcon.find('.help-msg');

    $(document.documentElement).on('click', '.help-icon', function(e) {
        if ($(e.target).is(':not(.help-icon *)')) {
            helpIcon.toggleClass('open');
            helpMsg.toggle();
        }
    });

    $(document.documentElement).on('click', function(e) {
        if ($(e.target).is(':not(.help-icon, .help-icon *)')) {
            helpIcon.removeClass('open');
            helpMsg.hide();
        }
    });


    /**
     * Adds aleading 0 to numbers less than 10 and greater that 0
     *
     * @param int number The number to test against
     *
     * return Either the original number or the number prefixed with 0
     */
    function addLeadingZero(number) {
        return (number <= 9) || (number === 0) ? "0" + number : number;
    }

    /**
     * Converts string to new Date and returns a formatted date in the
     * format YYYY-MM-DD h:m
     * @param String dateString A date in string form.
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
    // we have to only add out onpopstate handler once the page has loaded.
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
});
