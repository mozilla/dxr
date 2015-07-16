/* jshint devel:true, esnext: true */
/* globals nunjucks: true, $ */

$(function() {
    'use strict';
    // Get the file content container
    var fileContainer = $('#file'),
        queryField = $('#query'),
        contentContainer = $('#content');

    /**
     * Highlight, or remove highlighting from, all symbols with the same class
     * as the current node.
     *
     * @param Object [optional] currentNode The current symbol node.
     */
    function toggleSymbolHighlights(currentNode) {
        // First remove all highlighting
        fileContainer.find('mark a').unwrap();

        // Only add highlights if the currentNode is not undefined or null and
        // is an anchor link, as symbols will always be links.
        if (currentNode && currentNode[0].tagName === 'A') {
            fileContainer.find('.' + currentNode.attr('class')).wrap('<mark />');
        }
    }

    /**
     * Populates the context menu template, positions and shows
     * the widget. Also attached required listeners.
     *
     * @param {object} target - The target container to which the menu will be attached.
     * @param {object} contextMenu - The context menu data object.
     * @param {object} event - The event object returned in the handler callback.
     */
    function setContextMenu(target, contextMenu, event) {
        // Mouse coordinates
        var top = event.clientY,
            left = event.clientX;

        // If we arrived at the page via a search result and there is a hash in the url,
        // or the document has been scrolled, incorporate the scrollY amount for the
        // top location of the context menu.
        if (window.location.href.indexOf('#') > -1 || window.scrollY > 0) {
            top += window.scrollY;
        }

        target.append(nunjucks.render('context_menu.html', contextMenu));
        var currentContextMenu = $('#context-menu');

        // Immediately after appending the context menu, position it.
        currentContextMenu.css({
            top: top,
            left: left
        });

        // Move focus to the context menu
        currentContextMenu[0].focus();

        currentContextMenu.on('mousedown', function(event) {
            // Prevent clicks on the menu to propagate
            // to the window, so that the menu is not
            // removed and links will be followed.
            event.stopPropagation();
        });
    }

    // Listen for clicks bubbling up from children of the content container,
    // but only act if the element was an anchor with a data-path attribute.
    contentContainer.on('click', 'a[data-path]', function(event) {
        event.preventDefault();

        var contextMenu = {},
            path = $(this).data('path'),
            baseSearchParams = '?limit=100&redirect=false&q=',
            query = $.trim(queryField.val()),
            browseUrl = dxr.wwwRoot + '/' + encodeURIComponent(dxr.tree) + '/source/' + path,
            limitSearchUrl = dxr.searchUrl + baseSearchParams + encodeURIComponent(query) + '%20path%3A' + path + '%2F',  // TODO: Escape path properly.
            excludeSearchUrl = dxr.searchUrl + baseSearchParams + encodeURIComponent(query) + '%20-path%3A' + path + '%2F';

        contextMenu.menuItems = [
                {
                    html: 'Browse folder contents',
                    href: browseUrl,
                    icon: 'goto-folder'
                },
                {
                    html: 'Limit search to folder',
                    href: limitSearchUrl,
                    icon: 'path-search'
                },
                {
                    html: 'Exclude folder from search',
                    href: excludeSearchUrl,
                    icon: 'exclude-path'
                }
            ];

        setContextMenu(contentContainer, contextMenu, event);
    });

    // Listen and handle click events, but only if on
    // a code element.
    fileContainer.on('click', 'code', function(event) {
        var selection = window.getSelection();

        // First remove any context menu that might already exist
        $('#context-menu').remove();

        // Only show the context menu if the user did not make
        // a text selection.
        if (selection.isCollapsed) {

            var offset = selection.focusOffset,
                node = selection.anchorNode,
                selectedTxtString = node.nodeValue,
                startIndex = selectedTxtString.regexLastIndexOf(/[^A-Z0-9_]/i, offset) + 1,
                endIndex = selectedTxtString.regexIndexOf(/[^A-Z0-9_]/i, offset),
                word = '';

            // If the regex did not find a start index, start from index 0
            if (startIndex === -1) {
                start = 0;
            }

            // If the regex did not find an end index, end at the position
            // equal to the length of the string.
            if (endIndex === -1) {
                endIndex = selectedTxtString.length;
            }

            // If the offset is beyond the last word, no word was clicked on.
            if (offset === endIndex) {
                return;
            }

            word = selectedTxtString.substr(startIndex, endIndex - startIndex);

            // No word was clicked on, nothing to search.
            if (word === '') {
                return;
            }

            // Build the Object needed for the context-menu template.
            var contextMenu = {},
                menuItems = [{
                    html: 'Search for the substring <strong>' + htmlEscape(word) + '</strong>',
                    href: dxr.wwwRoot + "/" + encodeURIComponent(dxr.tree) + "/search?q=" + encodeURIComponent(word) + "&case=true",
                    icon: 'search'
                }];

            var currentNode = $(node).closest('a');
            // Only check for the data-menu attribute if the current node has an
            // ancestor that is an anchor.
            if (currentNode.length) {
                toggleSymbolHighlights(currentNode);

                var currentNodeData = currentNode.data('menu');
                menuItems = menuItems.concat(currentNodeData);
            }

            contextMenu.menuItems = menuItems;
            setContextMenu(fileContainer, contextMenu, event);
        }
    });

    // Remove the menu when a user clicks outside it.
    window.addEventListener('mousedown', function() {
        toggleSymbolHighlights();
        $('#context-menu').remove();
    }, false);

    onEsc(function() {
        $('#context-menu').remove();
    });
});
