/* jshint devel:true, esnext: true */
/* globals nunjucks: true, $ */

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

    /**
     * Disable and enable pointer events on scroll begin and scroll end to
     * avoid unnecessary paints and recalcs caused by hover effets.
     * @see http://www.thecssninja.com/javascript/pointer-events-60fps
     */
    var docElem = document.documentElement;

    // Tell nunjucks our base location for template files.
    nunjucks.configure('dxr/static/templates/');

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
        var elementPos = document.getElementById(id).offsetTop;

        if ((getMaxScrollY() - elementPos) > 100) {
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
    }

    /**
     * Presents the user with a notification message
     * @param {string} type - The type of notification to set, must be one of info, warn or error.
     * @param {string} message - The message to be displayed.
     * @param {Object} target - The element to use as the display target for the message.
     */
    function setUserMessage(type, message, target) {
        var messageContainer = document.createElement('p'),
            msg = document.createTextNode(message);

        messageContainer.appendChild(msg);

        switch(type) {
            case 'info':
                messageContainer.setAttribute('class', 'user-message info');
                break;
            case 'warn':
                messageContainer.setAttribute('class', 'user-message warn');
                break;
            case 'error':
                messageContainer.setAttribute('class', 'user-message error');
                break;
            default:
                console.log('Unrecognized message type. See function documentation for supported types.');
                return;
        }
        // If we are already showing a user message in the target, do not append again.
        if (!$('.message', target).length) {
            target.append(messageContainer);
        }
    }

    /**
     * Removes previously added notification message from target.
     * @param {Object} target - The element to use as the display target for the message.
     */
    function removeUserMessage(target) {
        var userMessage = $('.message', target);

        // If the user message container is found, remove it completely.
        if (userMessage.length) {
            userMessage.remove();
        }
    }

    /**
     * Represents the path line displayed next to the file path label on individual document pages.
     * Also handles population of the path lines template in the correct format.
     *
     * @param {string} fullPath - The full path of the currently displayed file.
     * @param {string} tree - The tree which was searched and in which this file can be found.
     * @param {string} icon - The icon string returned in the JSON payload.
     */
    function buildPathLine(fullPath, tree, icon) {
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
                'icon_class': isFirstOrOnly ? iconClass : '',
                'url': pathRoot + dataPath.join('/'),
                'is_first_or_only': isFirstOrOnly,
                'is_dir': !isLastOrOnly
            });
        }

        return pathLines;
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
    if (location.search.indexOf('from') > -1) {
        // Offer the user the option to see all the results instead.
        var viewResultsTxt = 'You have been taken to a direct result ' +
                             '<a href="{{ url }}">click here to view all search results.</a>',
            searchUrl = constants.data('search'),
            fromQuery = /[&?from]=(\w+)/.exec(location.search),
            isCaseSensitive = /case=(\w+)/.exec(location.search);

        searchUrl += '?q=' + fromQuery[1];

        if(isCaseSensitive) {
            searchUrl += '&case=' + isCaseSensitive[1];
        }

        var msgContainer = $('<p />', {
                'class': 'user-message simple',
                'html': viewResultsTxt.replace('{{ url }}', searchUrl)
            }),
            fileContainer = $('#file');

        fileContainer.before(msgContainer);
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
        params.offset = offset

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
        var searchUrl = constants.data('search') + '?' + data['query_string'];
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
                    if(data.results.length > 0) {
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
        data['wwwroot'] = dxr.wwwroot;
        data['tree'] = dxr.tree;
        data['top_of_tree'] = dxr.wwwroot + '/' + data['tree'] + '/source/';
        data['trees'] = data.trees;

        var params = {
            q: data.query,
            case: data.is_case_sensitive
        }
        data['query_string'] = $.param(params);

        // If no data is returned, inform the user.
        if (!data.results.length) {
            data['user_message'] = contentContainer.data('no-results');
            contentContainer.empty().append(nunjucks.render(tmpl, data));
        } else {

            var results = data.results;
            resultCount = results.length;

            for (var result in results) {
                var icon = results[result].icon;
                results[result].pathLine = buildPathLine(results[result].path, data.tree, icon);
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
            if (requestsInFlight == 0) {
                $('#search-box').addClass('in-progress');
            }
            requestsInFlight += 1;
        }

        function oneFewerRequest() {
            requestsInFlight -= 1;
            if (requestsInFlight == 0) {
                $('#search-box').removeClass('in-progress');
            }
        }

        clearTimeout(historyWaiter);

        query = $.trim(queryField.val());
        var myRequestNumber = nextRequestNumber,
            lineHeight = parseInt(contentContainer.css('line-height'), 10),
            limit = previousDataLimit = parseInt((window.innerHeight / lineHeight) + 25);

        if (query.length < 3) {
            return;
        }

        nextRequestNumber += 1;
        oneMoreRequest()
        $.getJSON(buildAjaxURL(query, caseSensitiveBox.prop('checked'), limit), function(data) {
            // New results, overwrite
            if (myRequestNumber > displayedRequestNumber) {
                displayedRequestNumber = myRequestNumber;
                populateResults('results_container.html', data, false);
                historyWaiter = setTimeout(pushHistoryState, timeouts.history, data);
            }
            oneFewerRequest()
        })
        .fail(function(jqxhr, textStatus, error) {
            var errorMessage = searchForm.data('error');

            oneFewerRequest()

            // A newer response already arrived and is displayed. Don't both complaining about this old one.
            if (myRequestNumber < displayedRequestNumber)
                return;

            if (error)
                errorMessage += ' Error: ' + error;
            setUserMessage('error', errorMessage, $('.text_search', searchForm));
        });
    }

    // Do a search every time you pause typing for 300ms:
    queryField.on('input', querySoon);

    // Update the search when the case-sensitive box is toggled, canceling any pending query:
    caseSensitiveBox.on('change', queryNow);

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
        window.onpopstate = null;
        window.location.reload();
    }
});
