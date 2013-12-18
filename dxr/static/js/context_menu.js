$(function() {
    // Get the file content container
    var fileContainer = $('#file');

    /**
     * Highlight, or remove highlighting from, all symbols with the same class
     * as the current node.
     *
     * @param Object [optional] currentNode The current symbol node.
     */
    function toggleSymbolHighlights(currentNode) {
        // First remove all highlighting
        fileContainer.find('mark a').unwrap();

        // Only add highlights if the currentNode is not undefined or null and,
        // is an anchor link as synbols will always be links.
        if (currentNode && currentNode[0].tagName === 'A') {
            fileContainer.find('.' + currentNode.attr('class')).wrap('<mark />');
        }
    }

    // Listen and handle click events, but only if on
    // a code element.
    fileContainer.on('click', 'code', function(event) {
        var selection = window.getSelection();

        // First remove any context menu that might already exist
        $('#context-menu').remove();

        // Only show the context menu if the user did not make
        // a text selection.
        if (selection.isCollapsed) {
            // Mouse coordinates
            var top = event.clientY;
            var left = event.clientX;

            // If we arrived at the page via a search result and there is a hash in the url,
            // or the document has been scrolled, incorporate the scrollY amount for the
            // top location of the context menu.
            if (window.location.href.indexOf('#') > -1 || window.scrollY > 0) {
                top += window.scrollY;
            }

            var offset = selection.focusOffset;
            var node = selection.anchorNode;
            var selectedTxtString = node.nodeValue;
            var startIndex = selectedTxtString.regexLastIndexOf(/[^A-Z0-9_]/i, offset) + 1;
            var endIndex = selectedTxtString.regexIndexOf(/[^A-Z0-9_]/i, offset);
            var word = '';

            // If the regex did not find a start index, start from index 0
            if (startIndex === -1) {
                start = 0;
            }

            // If the regex did not find an end index, end at the position
            // equal to the length of the string.
            if (endIndex === -1) {
                endIndex = selectedTxtString.length;
            }

            word = selectedTxtString.substr(startIndex, endIndex - startIndex);

            if (!nunjucks.env) {
                nunjucks.env = new nunjucks.Environment(new nunjucks.HttpLoader(dxr.views));
            }

            var env = nunjucks.env,
                tmpl = env.getTemplate('context_menu.html');

            // Build the Object needed for the context-menu template.
            var contextMenu = {};
            contextMenu.searchLink = {
                text: 'Search for the substring <strong>' + word + '</strong>',
                href: dxr.wwwroot + "/" + encodeURIComponent(dxr.tree) + "/search?q=" + encodeURIComponent(word)
            }

            var currentNode = $(node).closest('a');
            // Only check for the data-menu attribute if the current node has an
            // ancestor that is an anchor.
            if (currentNode.length) {
                toggleSymbolHighlights(currentNode);
                contextMenu.menuItems = currentNode.data('menu');
            }

            fileContainer.append(tmpl.render(contextMenu));
            var currentContextMenu =  $('#context-menu');

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
            })

            // Remove the menu when a user clicks outside it.
            window.addEventListener('mousedown', function() {
                toggleSymbolHighlights();
                currentContextMenu.remove();
            }, false);
        }
    });
});
