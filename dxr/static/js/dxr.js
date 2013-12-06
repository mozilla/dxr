/* jshint devel:true, esnext: true */
/* globals nunjucks: true, $ */

$(function() {
    'use strict';

    /**
     * Disable and enable event on scroll begin and scroll end.
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

    var constants = $('#data'),
        wwwroot = constants.data('root'),
        icons = wwwroot + '/static/icons/',
        views = wwwroot + '/static/views';

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
                messageContainer.setAttribute('class', 'message info');
                break;
            case 'warn':
                messageContainer.setAttribute('class', 'message warn');
                break;
            case 'error':
                messageContainer.setAttribute('class', 'message error');
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
        nunjucks.env = new nunjucks.Environment(new nunjucks.HttpLoader(views));
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
     */
    function buildPathLine(fullPath, tree) {
        var pathLines = '',
            pathRoot = '/' + tree + '/source/',
            paths = fullPath.split('/'),
            splitPathLength = paths.length,
            dataPath = [];

        for (var pathIndex in paths) {
            var isFirstOrLast = false;

            if ((splitPathLength - 1) === pathIndex || splitPathLength === 1) {
                isFirstOrLast = true;
            }

            // Do not add a forward slash if there is only one item in the Array
            //or, if this is the last iteration.
            var displayPath = isFirstOrLast ? paths[pathIndex] : paths[pathIndex] + '/';

            dataPath.push(paths[pathIndex]);
            pathLines += pathLineTmpl.render({
                'data_path': dataPath.join('/'),
                'display_path': displayPath,
                'url': pathRoot + dataPath.join('/')
            });
        }

        return pathLines;
    }

    var searchForm = $('#basic_search'),
        queryField = $('#query'),
        contentContainer = $('#content');

    /**
     * Returns the full Ajax URL for search
     * @param {string} params - A serialized string of the form inputs.
     */
    function buildAjaxURL(params) {
        var search = constants.data('search');
        return search + '?' + params;
    }

    var waitr = null;
    /**
     * The poller used to track changes in the query input field value.
     * @param {string} previousQuery - The last query term that was sent.
     */
    function startQueryInputPoller(previousQuery) {

        (function poller() {
            var currentQuery = $.trim(queryField.val());

            if (previousQuery !== currentQuery && currentQuery.length > 2) {
                doQuery(currentQuery);
                previousQuery = currentQuery;
            } else {
                waitr = setTimeout(poller, 500);
            }
        })();
    }

    /**
     * Stops the QueryInputPoller
     */
    function stopQueryInputPoller() {
        // If a timer exists, clear it before continuing.
        if (waitr) {
            clearTimeout(waitr);
        }
    }

    /**
     * Executes queries and populates the results templates with the returned data.
     * @param {string} query - The query term sent when this function was called.
     */
    function doQuery(query) {

        var previousQuery = query ? query : previousQuery;

        $.getJSON(buildAjaxURL(searchForm.serialize()), function(data) {

            // If no data is returned, inform the user.
            if (!data.results.length) {
                contentContainer.empty();
                setUserMessage('info', contentContainer.data('no-results'), contentContainer);
            } else {
                var results = data.results;

                for (var result in results) {
                    results[result].pathLine = buildPathLine(results[result].path, data.tree);
                    results[result].iconPath = icons + results[result].icon;
                }

                contentContainer.empty().append(tmpl.render(data));
            }
        }).done(function() {
            var query = $.trim(queryField.val());

            if (previousQuery !== query && query.length > 2) {
                stopQueryInputPoller();
                doQuery(query);

                previousQuery = query;
            } else {
                // The query has not changed, start the poller.
                startQueryInputPoller(previousQuery);
            }
        }).fail(function(jqxhr, textStatus, error) {
            var errorMessage = searchForm.data('error');

            if (error) {
                errorMessage += ' Error: ' + error;
            }
            stopQueryInputPoller();
            setUserMessage('error', errorMessage, $('.text_search', searchForm));
        });
    }

    var previousQuery = '';

    // Start search as you type as soon as the field receives focus.
    queryField.on('focus', function() {
        var query = $.trim(queryField.val());

        if (query !== previousQuery && query.length > 2) {
            doQuery(query);
            // Because the search field might lose focus and regain
            // focus without the query text changing, we need to keep
            // track of previous queries here in order to avoid unnecessary
            // ajax calls.
            previousQuery = query;
        } else {
            // The query was either empty or there was less than
            // the mminimum three characters so, simply pass an
            // empty string as the previous query to the poller.
            startQueryInputPoller('');
        }
    });

    // Stop search as you type as soon as the field looses focus.
    queryField.on('blur', function() {
        stopQueryInputPoller();
    });

    searchForm.on('submit', function() {
        // Set redirect to true for direct results.
        $('#redirect').val('true');
        // Ensure JSON is not returned.
        $('#format').val('html');
    });

    /**
     * Adds aleading 0 to numbers less than 10 and greater that 0
     *
     * @param int number The number to test against
     *
     * return Either the original number or the number prefixed with 0
     */
    function addLeadingZero(number) {
        return (number < 9) || (number > 0) ? "0" + number : number;
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
});
