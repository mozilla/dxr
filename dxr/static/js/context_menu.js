$(function() {
    // Get the file content container
    var fileContainer = $('#file');

    // Listen and handle clicks to close the context menu. There will only
    // ever be one, so this is safe.
    fileContainer.on('click', '#close-ctx-menu', function(event) {
        event.preventDefault();
        $(this).parents('.context-menu').remove();
        // Move focus back to the code row
        $(this).parent('code').focus();
    });

    // Listen and handle click events, but only if on
    // a code element.
    fileContainer.on('click', 'code', function(event) {
        event.preventDefault();
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
                text: 'Search for documents with the substring <strong>' + word + '</strong>',
                href: dxr.wwwroot + "/" + encodeURIComponent(dxr.tree) + "/search?q=" + encodeURIComponent(word)
            }

            var currentNodeTagName = $(node).parent()[0].tagName;
            // Only check for the menu data attribute if the current nodes parent is and anchor link.
            if (currentNodeTagName === 'A') {
                contextMenu.menuItems = $(node).parent().data('menu');
            }

            fileContainer.append(tmpl.render(contextMenu));

            // Immediatly after appending the context menu, position it.
            $('#context-menu').css({
                top: top,
                left: left
            });
            // Move focus to the context menu
            $('#context-menu').focus();
        }
    });
});
