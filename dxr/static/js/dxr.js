/* jshint devel:true, esnext: true */
/* globals nunjucks: true, $ */

$(function() {
    'use strict';

    var constants = $('#data');
    var dxr = {};

    dxr.wwwroot = constants.data('root');
    dxr.icons = dxr.wwwroot + '/static/icons/';
    dxr.views = dxr.wwwroot + '/static/views';
    dxr.tree = constants.data('tree');

    /**
     * Disable and enable pointer events on scroll begin and scroll end.
     * @see http://www.thecssninja.com/javascript/pointer-events-60fps
     */
    var root = document.documentElement;
    var timer;

    window.addEventListener('scroll', function() {
        // User scrolling so stop the timeout
        clearTimeout(timer);
        // Pointer events has not already been disabled.
        if (!root.style.pointerEvents) {
            root.style.pointerEvents = 'none';
        }

        timer = setTimeout(function() {
            root.style.pointerEvents = '';
        }, 500);
    }, false);

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

    if (!nunjucks.env) {
        nunjucks.env = new nunjucks.Environment(new nunjucks.HttpLoader(dxr.views));
    }

    var env = nunjucks.env,
        tmpl = env.getTemplate('results.html'),
        pathLineTmpl = env.getTemplate('path_line.html');

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
            var isFirstOrLast = (splitPathLength - 1) === pathIndex || splitPathLength === 1;

            // Do not add a forward slash if there is only one item in the Array
            // or if this is the last iteration.
            var displayPath = isFirstOrLast ? paths[pathIndex] : paths[pathIndex] + '/';

            dataPath.push(paths[pathIndex]);
            pathLines += pathLineTmpl.render({
                'data_path': dataPath.join('/'),
                'display_path': displayPath,
                'icon_class': iconClass,
                'url': pathRoot + dataPath.join('/')
            });
        }

        return pathLines;
    }

    var searchForm = $('#basic_search'),
        queryField = $('#query'),
        caseSensitiveBox = $('#case'),
        contentContainer = $('#content');

    /**
     * Returns the full Ajax URL for search and explicitly sets
     * redirect to false and format to json to ensure we never
     * get a HTML response or redirect from an Ajax call, even
     * when using the back button.
     *
     * @param {string} query - The query string
     * @param {bool} isCaseSensitive - Whether the query should be case-sensitive
     */
    function buildAjaxURL(query, isCaseSensitive) {
        var search = constants.data('search');
        var params = {};
        params.q = query;
        params.redirect = false;
        params.format = 'json';
        params['case'] = isCaseSensitive;

        return search + '?' + $.param(params);
    }

    var waiter = null,
        nextRequestNumber = 1,  // A monotonically increasing int that keeps old AJAX requests in flight from overwriting the results of newer ones, in case more than one is in flight simultaneously and they arrive out of order.
        displayedRequestNumber = 0;

    /**
     * Clears any existing query timer and sets a new one to query in a moment.
     */
    function querySoon() {
        clearTimeout(waiter);
        waiter = setTimeout(doQuery, 300);
    }

    /**
     * Clears any existing query timer and queries immediately.
     */
    function queryNow() {
        clearTimeout(waiter);
        doQuery();
    }

    /**
     * Queries and populates the results templates with the returned data.
     */
    function doQuery() {
        var query = $.trim(queryField.val()),
            myRequestNumber = nextRequestNumber;

        if (query.length < 3)
            return;

        nextRequestNumber += 1;
        $.getJSON(buildAjaxURL(query, caseSensitiveBox.prop('checked')), function(data) {
            // A newer response already arrived and is displayed. Don't overwrite it.
            if (myRequestNumber < displayedRequestNumber)
                return;

            displayedRequestNumber = myRequestNumber;

            data['wwwroot'] = dxr.wwwroot;
            data['tree'] = dxr.tree;
            data['top_of_tree'] = dxr.wwwroot + '/' + data['tree'] + '/source/';

            var params = {
                q: data.query,
                case: data.is_case_sensitive
            }
            data['query_string'] = $.param(params);

            // If no data is returned, inform the user.
            if (!data.results.length) {
                data['user_message'] = contentContainer.data('no-results');
                contentContainer.empty().append(tmpl.render(data));
            } else {

                var results = data.results;

                for (var result in results) {
                    var icon = results[result].icon;
                    results[result].pathLine = buildPathLine(results[result].path, data.tree, icon);
                }

                contentContainer.empty().append(tmpl.render(data));
            }
        })
        .fail(function(jqxhr, textStatus, error) {
            var errorMessage = searchForm.data('error');

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
        var fullDateTime = new Date(dateString);
        var date = fullDateTime.getFullYear() + '-' + (fullDateTime.getMonth() + 1) + '-' + addLeadingZero(fullDateTime.getDate());
        var time = fullDateTime.getHours() + ':' + addLeadingZero(fullDateTime.getMinutes());

        return date + ' ' + time;
    }

    var prettyDate = $('.pretty-date');
    prettyDate.each(function() {
        $(this).text(formatDate($(this).data('datetime')));
    });

    // Expose the DXR Object to the global object.
    window.dxr = dxr;
});
